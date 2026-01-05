import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import os
import time
import numpy as np

# =================== CONFIGURACIÓN GENERAL ===================
st.set_page_config(
    page_title="Monitoreo de Vibraciones",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Estado bomba de agua helada — SmartCampus UTP")

# Auto refresco cada 50 s
st_autorefresh(interval=50000, limit=None, key="refresh")

# =================== PARÁMETROS DEL SISTEMA ===================
FS = 10.0                  # Hz (muestreo)
RPM_MOTOR = 3555
FREQ_MEC = RPM_MOTOR / 60  # Hz ≈ 59.25

# Umbrales (aceleración RMS en m/s²)
RMS_ALERTA = 2.5
RMS_CRITICO = 4.0

# Umbrales IA (Edge Impulse)
IA_ALERTA = 3.0
IA_CRITICO = 4.0

# =================== CARGA DE DATOS ===================
@st.cache_data(ttl=60)
def load_daily_data(selected_date):
    filename = f"smartcampusudp_{selected_date}.csv"
    local_path = f"Data_udp/{filename}"
    github_url = f"https://raw.githubusercontent.com/smartcampusutp/SmartCampus_UTP/main/Data_udp/{filename}"

    try:
        if os.path.exists(local_path):
            df = pd.read_csv(local_path)
        else:
            df = pd.read_csv(github_url)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df

# =================== SIDEBAR ===================
st.sidebar.header("Filtros")

today = pd.Timestamp.now().date()
selected_date = st.sidebar.date_input(
    "Seleccionar día",
    value=today,
    max_value=today
)

df = load_daily_data(selected_date)

if df.empty:
    st.warning("No hay datos disponibles.")
    st.stop()

# Sensor
sensors = sorted(df["deviceName"].dropna().unique())
selected_sensor = st.sidebar.selectbox("Seleccionar sensor", sensors)

df_sensor = df[df["deviceName"] == selected_sensor].copy()

# Hora
available_hours = sorted(df_sensor["time"].dt.hour.unique())
selected_hour = st.sidebar.selectbox(
    "Seleccionar hora",
    available_hours,
    format_func=lambda h: f"{h:02d}:00 - {h:02d}:59"
)

df_sensor = df_sensor[df_sensor["time"].dt.hour == selected_hour]

if df_sensor.empty:
    st.warning("No hay datos para la hora seleccionada.")
    st.stop()

# =================== VALIDACIÓN DE MUESTREO ===================
dt = df_sensor["time"].diff().dt.total_seconds().dropna()
fs_real = 1 / dt.mean() if not dt.empty else 0

# =================== ANÁLISIS DE VIBRACIONES ===================

# RMS global vectorial (m/s²)
df_sensor["RMS_GLOBAL"] = np.sqrt(
    df_sensor["accXRMS"]**2 +
    df_sensor["accYRMS"]**2 +
    df_sensor["accZRMS"]**2
)

# IA: magnitud del anomaly score
df_sensor["anomaly_abs"] = df_sensor["anomaly"].abs()

# =================== DETECCIÓN DE ANOMALÍAS ===================
df_sensor["is_anomaly"] = 0
df_sensor["anomaly_level"] = "NORMAL"

df_sensor.loc[
    (df_sensor["RMS_GLOBAL"] >= RMS_ALERTA) |
    (df_sensor["anomaly_abs"] >= IA_ALERTA),
    ["is_anomaly", "anomaly_level"]
] = [1, "ANOMALÍA"]

df_sensor.loc[
    (df_sensor["RMS_GLOBAL"] >= RMS_CRITICO) |
    (df_sensor["anomaly_abs"] >= IA_CRITICO),
    ["is_anomaly", "anomaly_level"]
] = [2, "CRÍTICA"]

latest = df_sensor.iloc[-1]

# =================== KPIs ===================
st.markdown(f"""
### 📍 Sensor: **{selected_sensor}**

- **Motor:** {RPM_MOTOR} RPM  
- **Frecuencia mecánica:** {FREQ_MEC:.2f} Hz  
- **Frecuencia de muestreo real:** {fs_real:.2f} Hz
""")

c1, c2, c3, c4 = st.columns(4)

c1.metric("📈 RMS Global", f"{latest['RMS_GLOBAL']:.2f} m/s²")
c2.metric("🤖 IA Anomaly Score", f"{latest['anomaly']:.2f}")
c3.metric("⚙️ RPM", RPM_MOTOR)
c4.metric("⏱️ Muestreo", f"{fs_real:.2f} Hz")

# =================== ESTADO DEL MOTOR ===================
nivel = latest["anomaly_level"]

if nivel == "NORMAL":
    st.success("🟢 OPERACIÓN NORMAL — vibraciones dentro de límites")
elif nivel == "ANOMALÍA":
    st.warning("🟠 ANOMALÍA DETECTADA — incremento vibracional")
else:
    st.error("🔴 ANOMALÍA CRÍTICA — riesgo de falla mecánica")

st.divider()

# =================== GRÁFICOS ===================

# --- Gráfico RMS Global con anomalías ---
fig_rms = go.Figure()

fig_rms.add_trace(go.Scattergl(
    x=df_sensor["time"],
    y=df_sensor["RMS_GLOBAL"],
    mode="lines",
    name="RMS Global (m/s²)"
))

df_anom = df_sensor[df_sensor["is_anomaly"] > 0]

fig_rms.add_trace(go.Scattergl(
    x=df_anom["time"],
    y=df_anom["RMS_GLOBAL"],
    mode="markers",
    name="Anomalía",
    marker=dict(size=8, symbol="x")
))

fig_rms.update_layout(
    title="Análisis temporal de vibraciones — anomalías detectadas",
    xaxis_title="Tiempo",
    yaxis_title="Aceleración RMS (m/s²)",
    height=320
)

st.plotly_chart(fig_rms, use_container_width=True)

# --- Gráfico IA ---
fig_ia = go.Figure()

fig_ia.add_trace(go.Scattergl(
    x=df_sensor["time"],
    y=df_sensor["anomaly"],
    mode="lines",
    name="Anomaly Score (IA)"
))

fig_ia.update_layout(
    title="Modelo de IA — Score de anomalía",
    xaxis_title="Tiempo",
    yaxis_title="Score",
    height=300
)

st.plotly_chart(fig_ia, use_container_width=True)

# =================== TABLA DE DATOS ===================
with st.expander("📋 Últimos registros"):
    st.dataframe(
        df_sensor[[
            "time",
            "accXRMS",
            "accYRMS",
            "accZRMS",
            "RMS_GLOBAL",
            "anomaly",
            "anomaly_level"
        ]].tail(10)
    )
