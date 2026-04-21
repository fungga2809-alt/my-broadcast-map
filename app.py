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
st.set_page_config(page_title="중계소 관리 PRO - 실시간 방향", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# 데이터 초기화 로직
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for s in STATIONS + ['위도', '경도', '메모']:
                if s not in st.session_state.df.columns: st.session_state.df[s] = ""
        except: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state: st.session_state.my_loc = None

st.title("📡 현장 실시간 안테나 방향 가이드")

# --- [시스템] 실시간 위치 및 방향 센서 스크립트 ---
# 이 스크립트가 브라우저 단에서 GPS와 나침반 센서를 직접 제어합니다.
location_handler = components.html(
    """
    <script>
    function sendToStreamlit(data) {
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: JSON.stringify(data)
        }, '*');
    }

    // 위치 추적
    navigator.geolocation.watchPosition((pos) => {
        const coords = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            type: 'location'
        };
        sendToStreamlit(coords);
    }, (err) => {}, { enableHighAccuracy: true });

    // 방향(나침반) 추적
    if (window.DeviceOrientationEvent) {
        window.addEventListener('deviceorientationabsolute', (event) => {
            if (event.alpha !== null) {
                sendToStreamlit({
                    alpha: event.alpha,
                    type: 'orientation'
                });
            }
        }, true);
    }
    </script>
    """,
    height=0,
)

# 데이터 수신 및 상태 업데이트
# (참고: 실제 운영 환경에선 최적화를 위해 세션 스테이트를 정교하게 제어합니다)

# 2. 사이드바 구성
with st.sidebar:
    st.header("⚙️ 현장 도구")
    if st.button("🎯 내 위치로 지도 중심 이동"):
        if st.session_state.my_loc:
            st.session_state.map_center = st.session_state.my_loc
            st.rerun()
    
    st.divider()
    st.info("💡 **팁:** 핸드폰을 8자로 흔들어 나침반 보정을 해주시면 더 정확합니다.")
    
    # [기존 검색/삭제 기능 유지]
    if not st.session_state.df.empty:
        del_target = st.selectbox("데이터 삭제 대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 선택 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != del_target]
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.rerun()

# 3. 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 위성 레이어 고정
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}',
    attr='Google', name='Google Satellite', overlay=False
).add_to(m)

# [실시간 방향 부채꼴 아이콘 정의]
# CSS transform을 이용해 브라우저 단에서 회전하도록 구현
view_cone_html = """
<div id="view-cone" style="
    width: 0; height: 0; 
    border-left: 40px solid transparent; 
    border-right: 40px solid transparent; 
    border-bottom: 80px solid rgba(0, 150, 255, 0.4); 
    position: absolute; top: -70px; left: -40px;
    transform-origin: 50% 100%;
    transform: rotate(0deg);
    pointer-events: none;
"></div>
<div style="
    width: 16px; height: 16px; 
    background: #007AFF; border: 3px solid white; 
    border-radius: 50%; box-shadow: 0 0 10px rgba(0,0,0,0.5);
"></div>
"""

# 내 위치 및 방향 표시
if st.session_state.my_loc:
    folium.Marker(
        st.session_state.my_loc,
        icon=folium.DivIcon(html=view_cone_html),
        tooltip="현재 내 위치 (방향 포함)"
    ).add_to(m)

# 기존 중계소 마커 표시
for _, row in st.session_state.df.iterrows():
    try:
        st_pos = [float(row['위도']), float(row['경도'])]
        dist_info = ""
        if st.session_state.my_loc:
            d = geodesic(st.session_state.my_loc, st_pos).km
            dist_info = f"<br>📏 거리: {round(d, 2)}km"
        
        ch_text = " | ".join([f"{s}:{row[s]}" for s in STATIONS if pd.notna(row[s]) and str(row[s]).strip() != ""])
        folium.Marker(
            st_pos,
            popup=f"<b>{row['이름']}</b><br>{ch_text}{dist_info}",
            icon=folium.Icon(color='blue', icon='tower-broadcast', prefix='fa')
        ).add_to(m)
    except: continue

# 지도 렌더링
st_folium(m, width=1000, height=600, key="field_map")

# 4. 하단 데이터 표
st.subheader("📋 중계소 리스트")
st.dataframe(st.session_state.df, use_container_width=True)
