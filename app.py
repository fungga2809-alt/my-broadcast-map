import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os, json
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 페이지 설정
st.set_page_config(page_title="중계소 관리 PRO (복구형)", layout="wide")

DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 세션 상태 변수 (충돌 방지 로직 포함)
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

# 주소 검색 함수
def geocode_addr(address):
    geolocator = Nominatim(user_agent="broadcast_busan_final_v26")
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except: return None

st.markdown("## 📡 중계소 통합 관리 (클린 위성 & 클릭 복구)")

# [4] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    # GPS 위치
    loc = get_geolocation()
    my_pos = None
    if loc and 'coords' in loc:
        try:
            my_pos = [loc['coords']['latitude'], loc['coords']['longitude']]
            st.success("📍 GPS 연결 성공")
            if st.button("🎯 내 위치로 이동"):
                st.session_state.map_center = my_pos
                st.rerun()
        except: pass

    st.divider()
    st.markdown("### 🔍 주소/지점 검색")
    search_q = st.text_input("주소 입력 (예: 녹산동 산2-27)", help="산번지는 검색이 안 될 수 있습니다.")
    if st.button("📍 주소로 이동"):
        coords = geocode_addr(search_q)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = [coords[0], coords[1]]
            st.success("검색된 위치로 이동했습니다. 지도를 클릭해 위치를 미세 조정하세요.")
            st.rerun()
        else:
            st.error("주소를 찾지 못했습니다. '녹산동'처럼 큰 지명으로 검색해 보세요.")

    st.divider()
    st.markdown("### 📍 새 중계소 등록")
    name = st.text_input("중계소 명칭")
    
    # 좌표 입력란 (세션 상태와 직접 연동)
    t_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    t_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    
    flat = st.number_input("위도", value=float(t_lat), format="%.6f", key="lat_input")
    flon = st.number_input("경도", value=float(t_lon), format="%.6f", key="lon_input")

    # 채널 입력
    chs = {}
    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        d_n, u_n = ST_LIST[i], ST_LIST[i+1]
        chs[d_n] = c1.text_input(d_n, key=f"in_{d_n}")
        chs[u_n] = c2.text_input(u_n, key=f"in_{u_n}")

    if st.button("✅ 저장"):
        if name:
            new_v = [name] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None # 저장 후 마커 초기화
            st
