import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation

# [1] 페이지 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

DB_FILE = 'stations.csv'
# 채널 리스트 (DTV 및 UHD)
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 및 초기화
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLS)

# 세션 상태 변수
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

st.markdown("## 📡 중계소 통합 관리 (클린 위성 모드)")

# [3] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    # GPS 위치
    loc = get_geolocation()
    my_pos = None
    if loc and 'coords' in loc:
        try:
            my_pos = [loc['coords']['latitude'], loc['coords']['longitude']]
            st.success("📍 GPS 연결됨")
            if st.button("🎯 내 위치로 이동"):
                st.session_state.map_center = my_pos
                st.rerun()
        except: pass

    st.divider()
    st.markdown("### 📍 새 중계소 등록")
    name = st.text_input("중계소 명칭")
    
    # 채널 입력 (DTV/UHD 병렬 배치)
    chs = {}
    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        d_n, u_n = ST_LIST[i], ST_LIST[i+1]
        chs[d_n] = c1.text_input(d_n, key=f"in_{d_n}")
        chs[u_n] = c2.text_input(u_n, key=f"in_{u_n}")
    
    # 좌표 설정
    t_lat, t_lon = st.session_state.temp_lat, st.session_state.temp_lon
    m_lat, m_lon = st.session_state.map_center[0], st.session_state.map_center[1]
    flat = st.number_input("위도", value=float(t_lat if t_lat else m_lat), format="%.6f")
    flon = st.number_input("경도", value=float(t_lon if t_lon else m_lon), format="%.6f")
    memo = st.text_area("메모")

    if st.button("✅ 저장"):
        if name:
            new_val = [name] + [chs[s] for s in ST_LIST] + [flat, flon, memo]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_val], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [4] 메인 지도 영역 (레이어 정밀 설정)
m = folium.Map(location=st.session_state.map_center, zoom_start=14)

# 레이어 1: 전문가님 요청 - 산 이름/도로만 표시 (상업 마크 제외)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}',
    attr='Google', name='1. 위성 + 산/도로명 (상점 제외)', overlay=False, control=True
).add_to(m)

# 레이어 2: 완전 깔끔한 위성 (글자 아예 없음)
folium
