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
st.set_page_config(page_title="중계소 관리 PRO - 방향 복구", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# [데이터 초기화 및 상태 관리]
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try: st.session_state.df = pd.read_csv(DB_FILE)
        except: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

if 'my_loc' not in st.session_state: st.session_state.my_loc = None
if 'my_heading' not in st.session_state: st.session_state.my_heading = 0

st.title("📡 실시간 안테나 방향 가이드")

# --- [핵심] 센서 데이터 획득을 위한 자바스크립트 브릿지 ---
# 버튼을 클릭해야만 센서 권한을 요청할 수 있습니다.
st.sidebar.header("⚙️ 센서 제어")
sensor_script = """
<div id="sensor-ui" style="padding: 10px; background: #f0f2f6; border-radius: 10px;">
    <button id="btn-sensor" style="width: 100%; padding: 15px; background: #FF4B4B; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer;">
        🧭 나침반/GPS 센서 활성화
    </button>
    <p id="status" style="font-size: 12px; margin-top: 10px; color: #666;">버튼을 눌러 센서를 켜주세요.</p>
</div>

<script>
const btn = document.getElementById('btn-sensor');
const status = document.getElementById('status');

btn.onclick = function() {
    // 1. GPS 요청
    navigator.geolocation.watchPosition((pos) => {
        const data = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            type: 'location'
        };
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(data)}, '*');
        status.innerText = "📍 GPS 연결됨";
    }, (err) => { status.innerText = "❌ GPS 오류"; }, {enableHighAccuracy: true});

    // 2. 나침반(방향) 요청 (iOS 13+ 대응)
    if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        DeviceOrientationEvent.requestPermission()
            .then(permissionState => {
                if (permissionState === 'granted') {
                    startOrientation();
                }
            })
            .catch(console.error);
    } else {
        startOrientation();
    }
};

function startOrientation() {
    window.addEventListener('deviceorientationabsolute', (event) => {
        if (event.alpha !== null) {
            const data = { alpha: event.alpha, type: 'orientation' };
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(data)}, '*');
            status.innerText = "🧭 나침반/GPS 작동 중 (" + Math.round(event.alpha) + "°)";
        }
    }, true);
}
</script>
"""

with st.sidebar:
    # 자바스크립트 컴포넌트 실행
    sensor_data = components.html(sensor_script, height=150)
    
    # 데이터 수신 처리 (JSON 파싱)
    if sensor_data:
        try:
            res = json.loads(sensor_data)
            if res.get('type') == 'location':
                st.session_state.my_loc = [res['lat'], res['lon']]
            elif res.get('type') == 'orientation':
                # 기기 방향 보정 (N=0)
                st.session_state.my_heading = 360 - res['alpha']
        except: pass

    if st.button("🎯 내 위치로 지도 중심 이동"):
        if st.session_state.my_loc: st.session_state.map_center = st.session_state.my_loc

# 3. 지도 생성
m = folium.Map(location=st.session_state.my_loc if st.session_state.my_loc else [35.1796, 129.0756], zoom_start=16)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='Google', name='위성 지도').add_to(m)

# [부채꼴 아이콘 그리기]
if st.session_state.my_loc:
    # 회전 각도 적용
    heading = st.session_state.my_heading
    view_cone_html = f"""
    <div style="position: relative;">
        <div style="
            width: 0; height: 0; 
            border-left: 50px solid transparent; 
            border-right: 50px solid transparent; 
            border-bottom: 100px solid rgba(0, 150, 255, 0.4); 
            position: absolute; top: -90px; left: -50px;
            transform-origin: 50% 100%;
            transform: rotate({heading}deg);
            pointer-events: none;
        "></div>
        <div style="
            width: 16px; height: 16px; 
            background: #007AFF; border: 3px solid white; 
            border-radius: 50%; box-shadow: 0 0 10px rgba(0,0,0,0.5);
        "></div>
    </div>
    """
    folium.Marker(st.session_state.my_loc, icon=folium.DivIcon(html=view_cone_html)).add_to(m)

# 기존 중계소 마커 (거리 계산 포함)
for _, row in st.session_state.df.iterrows():
    try:
        st_pos = [float(row['위도']), float(row['경도'])]
        dist_info = f"<br>📏 거리: {round(geodesic(st.session_state.my_loc, st_pos).km, 2)}km" if st.session_state.my_loc else ""
        folium.Marker(st_pos, popup=f"<b>{row['이름']}</b>{dist_info}", icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

st_folium(m, width=1000, height=600, key="field_map_v16")

st.subheader("📋 중계소 목록")
st.dataframe(st.session_state.df, use_container_width=True)
