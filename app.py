import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
import json
import streamlit.components.v1 as components

# 1. 페이지 설정
st.set_page_config(page_title="중계소 통합 관리 - 전문가용", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# 데이터 초기화 및 로드
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for s in STATIONS + ['위도', '경도', '메모']:
                if s not in st.session_state.df.columns: st.session_state.df[s] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else:
        st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

# 상태 변수 설정
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state: st.session_state.my_loc = None
if 'my_heading' not in st.session_state: st.session_state.my_heading = 0
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

def geocode(address):
    geolocator = Nominatim(user_agent="broadcasting_manager_final")
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except: return None

st.title("📡 부산/울산 중계소 통합 관리 (실시간 GPS/방향)")

# --- [시스템] 센서 데이터 획득 브릿지 ---
sensor_script = """
<div id="sensor-ui" style="padding: 10px; background: #f0f2f6; border-radius: 10px; border: 1px solid #ddd;">
    <button id="btn-sensor" style="width: 100%; padding: 12px; background: #FF4B4B; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer;">
        🧭 나침반/GPS 센서 활성화
    </button>
    <p id="status" style="font-size: 11px; margin-top: 8px; color: #666; text-align:center;">현장에서 방향을 보려면 위 버튼을 누르세요.</p>
</div>
<script>
const btn = document.getElementById('btn-sensor');
const status = document.getElementById('status');
btn.onclick = function() {
    navigator.geolocation.watchPosition((pos) => {
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude, type: 'location'})}, '*');
        status.innerText = "📍 GPS 연결됨";
    }, (err) => {}, {enableHighAccuracy: true});
    if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        DeviceOrientationEvent.requestPermission().then(state => { if(state === 'granted') startOri(); });
    } else { startOri(); }
};
function startOri() {
    window.addEventListener('deviceorientationabsolute', (e) => {
        if (e.alpha !== null) {
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify({alpha: e.alpha, type: 'orientation'})}, '*');
            status.innerText = "🧭 방향 감지 중 (" + Math.round(e.alpha) + "°)";
        }
    }, true);
}
</script>
"""

# 2. 사이드바 (모든 기능 통합)
with st.sidebar:
    st.header("⚙️ 센서 및 도구")
    s_data = components.html(sensor_script, height=130)
    if s_data:
        try:
            res = json.loads(s_data)
            if res.get('type') == 'location': st.session_state.my_loc = [res['lat'], res['lon']]
            elif res.get('type') == 'orientation': st.session_state.my_heading = 360 - res['alpha']
        except: pass
    
    if st.session_state.my_loc and st.button("🎯 내 위치로 지도 중심 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("🔍 기존 중계소 검색")
    search_q = st.text_input("검색어 (이름/채널)")
    if search_q:
        mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_q, na=False)).any(axis=1)
        filtered = st.session_state.df[mask]
        if not filtered.empty:
            sel = st.selectbox("검색 결과", filtered['이름'].tolist())
            if st.button("📍 해당 위치 이동"):
                row = filtered[filtered['이름'] == sel].iloc[0]
                st.session_state.map_center = [row['위도'], row['경도']]
                st.rerun()

    st.divider()
    st.header("📍 신규 지점 등록")
    addr = st.text_input("🏠 주소로 찾기")
    if st.button("주소 검색"):
        coords = geocode(addr)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = coords
            st.rerun()

    new_name = st.text_input("중계소 명칭")
    st.write("📺 물리 채널")
    ch_inputs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(STATIONS):
        ch_inputs[s] = (c1 if i % 2 == 0 else c2).text_input(f"{s} 채널")

    # 좌표 입력
    def_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    def_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    f_lat = st.number_input("위도", value=float(def_lat), format="%.6f")
    f_lon = st.number_input("경도", value=float(def_lon), format="%.6f")
    memo = st.text_area("메모/특이사항")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("✅ 저장"):
            if new_name:
                row_data = [new_
