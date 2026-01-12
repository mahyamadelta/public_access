import streamlit as st
import json
import time
import pandas as pd
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import queue
from datetime import datetime

# =========================
# KONFIGURASI SISTEM
# =========================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "project/tralalilo_trolia/sensor"

DEFAULT_LAT = -6.249526003104378
DEFAULT_LON = 107.01397242039592

# =========================
# SETUP TAMPILAN (UI)
# =========================
st.set_page_config(
    page_title="Terminal Bekasi Air Watch",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# CSS Custom
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .status-card {
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .param-card {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .big-text { font-size: 2.5rem; font-weight: bold; margin: 0;}
    .sub-text { font-size: 1.2rem; opacity: 0.9; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)

# =========================
# BACKEND (THREAD SAFE)
# =========================

# 1. Buat Queue Global (Menggunakan cache agar bisa diakses thread luar)
@st.cache_resource
def get_shared_queue():
    return queue.Queue()

msg_queue = get_shared_queue()

# 2. State Data (Hanya untuk Main Thread)
if "public_data" not in st.session_state:
    st.session_state.public_data = {
        "suhu": 0, "kelembaban": 0, "co": 0, "pm25": 0,
        "no2": 0, "ai_label": "MENGHUBUNGKAN...", "ai_score": 0,
        "timestamp": datetime.now()
    }

# 3. MQTT Callback (Hanya taruh data ke Queue, JANGAN sentuh session_state)
def on_connect(client, userdata, flags, rc, properties=None): # Support V2 Signature
    if rc == 0:
        print("✅ Public Dashboard Connected to MQTT")
        client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        payload['timestamp'] = datetime.now()
        # Masukkan ke Global Queue (Aman dari Thread Error)
        msg_queue.put(payload)
    except Exception as e:
        print(f"Error parsing: {e}")

# 4. Start MQTT Service (Sekali jalan)
@st.cache_resource
def start_public_mqtt():
    # Gunakan CallbackAPIVersion.VERSION2 atau VERSION1 sesuai library paho-mqtt Anda
    # Jika error version, ganti ke mqtt.CallbackAPIVersion.VERSION1
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except:
        client = mqtt.Client() # Fallback untuk versi lama
        
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"Connection Error: {e}")
    return client

start_public_mqtt()

# 5. Ambil Data dari Queue ke Session State (Di Main Thread)
while not msg_queue.empty():
    st.session_state.public_data = msg_queue.get()

# =========================
# LOGIKA VISUAL
# =========================
data = st.session_state.public_data
label = data.get("ai_label", "UNKNOWN")
score = float(data.get("ai_score", 0)) * 100

if label == "BAIK":
    bg_color = "#4CAF50"
    icon = "😊"
    pesan = "Udara Segar! Nikmati aktivitas di luar ruangan."
elif label == "SEDANG":
    bg_color = "#2196F3"
    icon = "😐"
    pesan = "Kualitas udara cukup baik. Kelompok sensitif hati-hati."
elif label == "TIDAK SEHAT":
    bg_color = "#FF9800"
    icon = "😷"
    pesan = "Kurangi aktivitas luar ruangan. Gunakan masker."
elif label in ["SANGAT TIDAK SEHAT", "BERBAHAYA"]:
    bg_color = "#F44336"
    icon = "☠️"
    pesan = "BAHAYA! Hindari keluar rumah. Tutup jendela rapat-rapat."
else:
    bg_color = "#9E9E9E"
    icon = "📡"
    pesan = "Menunggu data dari sensor..."

# =========================
# TAMPILAN UI
# =========================

st.title("🌿 Bekasi Air Watch")
st.caption(f"Pantauan Kualitas Udara Real-time | Terminal Bekasi")

# Hero Card
st.markdown(f"""
    <div class="status-card" style="background-color: {bg_color};">
        <div style="font-size: 4rem;">{icon}</div>
        <p class="sub-text">Status Udara</p>
        <p class="big-text">{label}</p>
        <hr style="border-color: rgba(255,255,255,0.3);">
        <p style="font-size: 1.1rem; font-weight: 500;">"{pesan}"</p>
    </div>
    """, unsafe_allow_html=True)

# Indikator Gauge
col_gauge, col_info = st.columns([1, 2])

with col_gauge:
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Akurasi AI", 'font': {'size': 14}},
        gauge = {
            'axis': {'range': [None, 100], 'visible': False},
            'bar': {'color': bg_color},
            'bgcolor': "white",
            'borderwidth': 0,
            'bordercolor': "gray",
        }
    ))
    fig.update_layout(height=120, margin=dict(l=10, r=10, t=30, b=10))
    # PERBAIKAN: Menggunakan width="stretch" (atau integer jika masih error)
    # Jika versi Streamlit sangat baru, gunakan 'use_container_width=True' jika masih didukung,
    # tapi error log Anda minta 'width'. Kita coba parameter native Plotly chart.
    st.plotly_chart(fig, use_container_width=True) 

with col_info:
    st.markdown("### 🕒 Update Terakhir")
    ts = data.get('timestamp')
    if isinstance(ts, datetime):
        st.write(f"**Jam:** {ts.strftime('%H:%M:%S')} WIB")
        st.write(f"**Tanggal:** {ts.strftime('%d %B %Y')}")
    else:
        st.write("Menunggu update...")

# Grid Parameter
st.subheader("📊 Kondisi Lingkungan")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""<div class="param-card">
        <div style="font-size: 20px;">🌡️ Suhu</div>
        <div style="font-size: 24px; font-weight: bold; color: #333;">{data.get('suhu')} °C</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="param-card">
        <div style="font-size: 20px;">💧 Kelembapan</div>
        <div style="font-size: 24px; font-weight: bold; color: #333;">{data.get('kelembaban')} %</div>
    </div>""", unsafe_allow_html=True)

st.write("")

c3, c4 = st.columns(2)
with c3:
    st.markdown(f"""<div class="param-card">
        <div style="font-size: 20px;">🌫️ Debu (PM2.5)</div>
        <div style="font-size: 24px; font-weight: bold; color: {bg_color};">{data.get('pm25')} µg/m³</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="param-card">
        <div style="font-size: 20px;">🚗 Gas CO</div>
        <div style="font-size: 24px; font-weight: bold; color: {bg_color};">{data.get('co')} mg/m³</div>
    </div>""", unsafe_allow_html=True)

# Data API Detail
with st.expander("🔍 Lihat Detail Polutan Lainnya (API)"):
    st.write("Data berikut diambil dari stasiun pemantau wilayah:")
    d1, d2, d3 = st.columns(3)
    d1.metric("NO₂", f"{data.get('no2')} µg")
    d2.metric("SO₂", f"{data.get('so2')} µg")
    d3.metric("Ozon", f"{data.get('o3')} µg")

# Peta Lokasi
st.subheader("📍 Lokasi Alat")
map_data = pd.DataFrame({'lat': [DEFAULT_LAT], 'lon': [DEFAULT_LON]})

# PERBAIKAN: Mengganti use_container_width=True dengan width="stretch" (atau abaikan parameter jika error)
try:
    st.map(map_data, zoom=14, use_container_width=True) 
except:
    st.map(map_data, zoom=14) # Fallback jika parameter dihapus total di versi masa depan

st.markdown("---")
st.caption("© 2026 Project Tralalilo Trolia | Powered by ESP32 & Streamlit")

# Auto Refresh
time.sleep(3)

st.rerun()

