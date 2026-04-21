import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
import json
import streamlit.components.v1 as components

# 1. 초기 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")
DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + STATIONS + ['위도', '경도', '메모']

if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state: st.session_state.my_loc = None
if 'my_heading' not in st.session_state: st.session_state.my_heading = 0
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

def geocode(address):
    geolocator = Nominatim(user_agent="broadcasting_busan_v19")
    try:
        loc = geolocator.geocode(address)
        return (loc.latitude, loc.longitude) if loc else None
    except: return None

st.title("📡 부산/울산 중계소 통합 관리 (GPS/방향)")

# --- [시스템] 센서 제어 브릿지 ---
sensor_ui = """
<div style="padding:10px; background:#f0f2f6; border-radius:10px; border:1px solid #ddd; text-align:center;">
    <button id="s-btn" style="width:100%; padding:12px; background:#FF4B4B; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">
        🧭 나침반/GPS 센서 활성화
    </button>
    <p id="msg" style="font-size:11px; margin-top:8px; color:#666;">현장에서 방향을 보려면 위 버튼을 누르세요.</p>
</div>
<script>
const btn = document.getElementById('s-btn');
const msg = document.getElementById('msg');
btn.onclick = function() {
    navigator.geolocation.watchPosition((p) => {
        const d = {lat: p.coords.latitude, lon: p.coords.longitude, type: 'location'};
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(d)}, '*');
        msg.innerText = "📍 GPS 연결됨";
    }, (e) => {}, {enableHighAccuracy: true});
    if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        DeviceOrientationEvent.requestPermission().then(s => { if(s === 'granted') start(); });
    } else { start(); }
};
function start() {
    window.addEventListener('deviceorientationabsolute', (e) => {
        if (e.alpha !== null) {
            const d = {alpha: e.alpha, type: 'orientation'};
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(d)}, '*');
            msg.innerText = "🧭 방향 감지 중 (" + Math.round(e.alpha) + "°)";
        }
    }, true);
}
</script>
"""

# 2. 사이드바 기능
with st.sidebar:
    st.header("⚙️ 센서 제어")
    sd = components.html(sensor_ui, height=140)
    if sd:
        try:
            r = json.loads(sd)
            if r.get('type') == 'location': st.session_state.my_loc = [r['lat'], r['lon']]
            elif r.get('type') == 'orientation': st.session_state.my_heading = 360 - r['alpha']
        except: pass
    
    if st.session_state.my_loc and st.button("🎯 내 위치로 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("🔍 중계소 검색")
    sq = st.text_input("검색 (이름/채널)")
    if sq:
        f = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(sq, na=False)).any(axis=1)]
        if not f.empty:
            s_name = st.selectbox("결과", f['이름'].tolist())
            if st.button("📍 이동"):
                row = f[f['이름'] == s_name].iloc[0]
                st.session_state.map_center = [row['위도'], row['경도']]
                st.rerun()

    st.divider()
    st.header("📍 신규 등록")
    addr = st.text_input("🏠 주소로 찾기")
    if st.button("주소 검색"):
        c = geocode(addr)
        if c: st.session_state.temp_lat, st.session_state.temp_lon, st.session_state.map_center = c[0], c[1], c
        st.rerun()

    n_name = st.text_input("중계소 명칭")
    c_in = {}
    col_a, col_b = st.columns(2)
    for i, s in enumerate(STATIONS):
        c_in[s] = (col_a if i % 2 == 0 else col_b).text_input(f"{s} CH")

    def_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    def_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    f_lat = st.number_input("위도", value=float(def_lat), format="%.6f")
    f_lon = st.number_input("경도", value=float(def_lon), format="%.6f")
    memo = st.text_area("메모")

    if st.button("✅ 저장"):
        if n_name:
            new_data = [n_name] + [c_in[s] for s in STATIONS] + [f_lat, f_lon, memo]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 성공!")
            st.rerun()

    st.divider()
    if not st.session_state.df.empty:
        st.header("🗑️ 삭제")
        d_target = st.selectbox("대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 삭제 실행"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != d_target]
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.rerun()

# 3. 메인 지도
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='Google', name='위성 지도').add_to(m)

if st.session_state.my_loc:
    h = st.session_state.my_heading
    # 부채꼴 HTML을 한 줄로 결합하여 에러 원천 차단
    cone_html = f'<div style="position:relative;"><div style="width:0;height:0;border-left:50px solid transparent;border-right:50px solid transparent;border-bottom:100px solid rgba(0,150,255,0.4);position:absolute;top:-90px;left:-50px;transform-origin:50% 100%;transform:rotate({h}deg);pointer-events:none;"></div><div style="width:16px;height:16px;background:#007AFF;border:3px solid white;border-radius:50%;box-shadow:0 0 10px rgba(0,0,0,0.5);"></div></div>'
    folium.Marker(st.session_state.my_loc, icon=folium.DivIcon(html=cone_html)).add_to(m)

for _, row in st.session_state.df.iterrows():
    try:
        p = [float(row['위도']), float(row['경도'])]
        dist = f"<br>📏 거리: {round(geodesic(st.session_state.my_loc, p).km, 2)}km" if st.session_state.my_loc else ""
        ch = " | ".join([f"{s}:{row[s]}" for s in STATIONS if pd.notna(row[s]) and str(row[s]).strip() != ""])
        folium.Marker(p, popup=f"<b>{row['이름']}</b><br>{ch}{dist}", icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp
