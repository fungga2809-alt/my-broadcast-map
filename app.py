import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
import json
import streamlit.components.v1 as components

# 1. 페이지 설정 및 데이터 초기화
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLUMNS = ['이름'] + STATIONS + ['위도', '경도', '메모']

if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for col in COLUMNS:
                if col not in st.session_state.df.columns:
                    st.session_state.df[col] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=COLUMNS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLUMNS)

if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state:
    st.session_state.my_loc = None
if 'my_heading' not in st.session_state:
    st.session_state.my_heading = 0
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

def geocode(address):
    geolocator = Nominatim(user_agent="broadcasting_manager_final_v18")
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
    <p id="status" style="font-size: 11px; margin-top: 8px; color: #666; text-align:center;">버튼 클릭 후 권한을 허용해 주세요.</p>
</div>
<script>
const btn = document.getElementById('btn-sensor');
const status = document.getElementById('status');
btn.onclick = function() {
    navigator.geolocation.watchPosition((pos) => {
        const locData = {lat: pos.coords.latitude, lon: pos.coords.longitude, type: 'location'};
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(locData)}, '*');
        status.innerText = "📍 GPS 연결됨";
    }, (err) => { status.innerText = "❌ GPS 권한 필요"; }, {enableHighAccuracy: true});
    
    if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        DeviceOrientationEvent.requestPermission().then(state => { if(state === 'granted') startOri(); });
    } else { startOri(); }
};
function startOri() {
    window.addEventListener('deviceorientationabsolute', (e) => {
        if (e.alpha !== null) {
            const oriData = {alpha: e.alpha, type: 'orientation'};
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: JSON.stringify(oriData)}, '*');
            status.innerText = "🧭 방향 감지 중 (" + Math.round(e.alpha) + "°)";
        }
    }, true);
}
</script>
"""

# 2. 사이드바 기능 통합
with st.sidebar:
    st.header("⚙️ 센서 및 도구")
    s_data = components.html(sensor_script, height=135)
    if s_data:
        try:
            res = json.loads(s_data)
            if res.get('type') == 'location': 
                st.session_state.my_loc = [res['lat'], res['lon']]
            elif res.get('type') == 'orientation': 
                st.session_state.my_heading = 360 - res['alpha']
        except: pass
    
    if st.session_state.my_loc and st.button("🎯 내 위치로 지도 중심 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("🔍 중계소 검색")
    search_q = st.text_input("이름 또는 채널 검색")
    if search_q:
        mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_q, na=False)).any(axis=1)
        filtered = st.session_state.df[mask]
        if not filtered.empty:
            sel = st.selectbox("결과 선택", filtered['이름'].tolist())
            if st.button("📍 위치 이동"):
                r = filtered[filtered['이름'] == sel].iloc[0]
                st.session_state.map_center = [r['위도'], r['경도']]
                st.rerun()

    st.divider()
    st.header("📍 신규 지점 등록")
    reg_name = st.text_input("중계소 명칭")
    
    st.write("📺 물리 채널")
    ch_inputs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(STATIONS):
        ch_inputs[s] = (c1 if i % 2 == 0 else c2).text_input(f"{s}")

    d_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    d_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    f_lat = st.number_input("위도", value=float(d_lat), format="%.6f")
    f_lon = st.number_input("경도", value=float(d_lon), format="%.6f")
    memo = st.text_area("특이사항")

    if st.button("✅ 저장하기"):
        if reg_name:
            # 리스트 생성을 안전하게 분할하여 에러 방지
            new_row_data = [reg_name]
            new_row_data.append(ch_inputs['SBS'])
            new_row_data.append(ch_inputs['KBS2'])
            new_row_data.append(ch_inputs['KBS1'])
            new_row_data.append(ch_inputs['EBS'])
            new_row_data.append(ch_inputs['MBC'])
            new_row_data.append(f_lat)
            new_row_data.append(f_lon)
            new_row_data.append(memo)
            
            new_df = pd.DataFrame([new_row_data], columns=COLUMNS)
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success(f"'{reg_name}' 등록 완료!")
            st.rerun()

    st.divider()
    if not st.session_state.df.empty:
        st.header("🗑️ 삭제")
        del_target = st.selectbox("삭제 대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 삭제 실행"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != del_target]
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.rerun()

# 3. 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}',
    attr='Google', name='위성 지도'
).add_to(m)

# 내 위치 + 부채꼴
if st.session_state.my_loc:
    h = st.session_state.my_heading
    v_cone = f"""
    <div style="position: relative;">
        <div style="width: 0; height: 0; border-left: 50px solid transparent; border-right: 50px solid transparent; 
                    border-bottom: 100px solid rgba(0, 150, 255, 0.4); position: absolute; top: -90px; left: -50px;
                    transform-origin: 50% 100%; transform: rotate({h}deg); pointer-events: none;"></div>
        <div style="width: 16px
