import streamlit as st
import pandas as pd
import folium
import numpy as np

from folium.plugins import HeatMap, MeasureControl, MousePosition
from streamlit_folium import st_folium

st.set_page_config(layout="wide")

# ======================
# DATASET
# ======================

url="https://raw.githubusercontent.com/smartcampusutp/SmartCampus_UTP/main/Data/Tests/Tests_2026-03-16.csv"
df=pd.read_csv(url)

# ======================
# GATEWAYS
# ======================

gateways={

"ELII":{
"coords":[9.024833577337148,-79.53453540802003],
"color":"red",
"rssi_col":"gw1_rssi",
"snr_col":"gw1_snr"
},

"Facilidades":{
"coords":[9.023413708152264,-79.53220188617708],
"color":"blue",
"rssi_col":"gw2_rssi",
"snr_col":"gw2_snr"
}

}

# ======================
# LIMPIEZA
# ======================

for g in gateways:
    df[gateways[g]["rssi_col"]] = pd.to_numeric(df[gateways[g]["rssi_col"]], errors="coerce")
    df[gateways[g]["snr_col"]] = pd.to_numeric(df[gateways[g]["snr_col"]], errors="coerce")

# ======================
# DISTANCIA
# ======================

def haversine(lat1,lon1,lat2,lon2):

    R=6371000

    phi1=np.radians(lat1)
    phi2=np.radians(lat2)

    dphi=np.radians(lat2-lat1)
    dlambda=np.radians(lon2-lon1)

    a=np.sin(dphi/2)**2+np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    c=2*np.arctan2(np.sqrt(a),np.sqrt(1-a))

    return R*c

# ======================
# EXPANDIR RECEPCIONES
# ======================

records=[]

for _,row in df.iterrows():

    for gw,data in gateways.items():

        rssi=row[data["rssi_col"]]
        snr=row[data["snr_col"]]

        if pd.notna(rssi):

            d=haversine(
                row.latitude,
                row.longitude,
                data["coords"][0],
                data["coords"][1]
            )

            records.append({

                "lat":row.latitude,
                "lon":row.longitude,
                "gateway":gw,
                "rssi":rssi,
                "snr":snr,
                "distance":d

            })

data=pd.DataFrame(records)

# ======================
# SIDEBAR CONTROLES
# ======================

st.sidebar.title("Capas del mapa")

show_all=st.sidebar.checkbox("Mostrar todo",True)

controls={}

for gw in gateways:

    with st.sidebar.expander(f"Gateway {gw}",True):

        controls[gw]={

        "nodes":st.checkbox("Nodos",show_all,key=f"{gw}nodes"),
        "links":st.checkbox("Links",show_all,key=f"{gw}links"),
        "rings":st.checkbox("Rings",show_all,key=f"{gw}rings"),
        "heatmap":st.checkbox("RSSI Heatmap",False,key=f"{gw}heat")

        }

# ======================
# MAPA (MEJOR ZOOM)
# ======================

m=folium.Map(
location=[df.latitude.mean(),df.longitude.mean()],
zoom_start=18,
max_zoom=22,
tiles=None
)

# ======================
# CAPAS DE MAPA
# ======================

folium.TileLayer(
"cartodbpositron",
name="Mapa"
).add_to(m)

folium.TileLayer(
tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
attr="Google",
name="Satellite"
).add_to(m)

folium.LayerControl().add_to(m)

# ======================
# GATEWAYS
# ======================

for gw,data_gw in gateways.items():

    folium.Marker(
        data_gw["coords"],
        icon=folium.Icon(color=data_gw["color"],icon="signal"),
        popup=f"Gateway {gw}"
    ).add_to(m)

# ======================
# RINGS
# ======================

rings=[150,300,600,1000]

for gw,data_gw in gateways.items():

    if controls[gw]["rings"]:

        for r in rings:

            folium.Circle(
                data_gw["coords"],
                radius=r,
                color=data_gw["color"],
                weight=1,
                fill=False
            ).add_to(m)

# ======================
# NODOS Y LINKS
# ======================

heat_layers={}

for gw in gateways:
    heat_layers[gw]=[]

for _,row in data.iterrows():

    gw=row["gateway"]

    if controls[gw]["nodes"]:

        rssi=row["rssi"]

        if rssi>-85:
            color="green"
        elif rssi>-100:
            color="orange"
        else:
            color="red"

        folium.CircleMarker(
        [row["lat"],row["lon"]],
        radius=4+((rssi+120)/8),
        color=color,
        fill=True,
        fill_opacity=0.9,
        popup=f"""
        Gateway: {gw}<br>
        RSSI: {rssi} dBm<br>
        SNR: {row['snr']} dB<br>
        Distance: {round(row['distance'],1)} m
        """
        ).add_to(m)

    if controls[gw]["links"]:

        folium.PolyLine(
        [
        [row["lat"],row["lon"]],
        gateways[gw]["coords"]
        ],
        color=gateways[gw]["color"],
        weight=0.8,
        opacity=0.5
        ).add_to(m)

    heat_layers[gw].append([
        row["lat"],
        row["lon"],
        (row["rssi"]+120)/60
    ])

# ======================
# HEATMAP
# ======================

for gw in gateways:

    if controls[gw]["heatmap"]:

        HeatMap(
        heat_layers[gw],
        radius=25,
        blur=20
        ).add_to(m)

# ======================
# CONTROLES
# ======================

MeasureControl().add_to(m)
MousePosition().add_to(m)

# ======================
# MAPA
# ======================

st.title("LoRaWAN Coverage Map")

st_folium(m,width=1400,height=750)
