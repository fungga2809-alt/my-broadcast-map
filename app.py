import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 기본 설정
st.set_page_config(page_title="방송 관리 PRO", layout="wide")
DB = 'stations.csv'
ST_L = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
COLS = ['구분', '이름'] + ST_L + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# 세션 초기화
for k, v in {'map_center':[35.1796, 129.0756], 'temp_lat':None, 'temp_lon':None}.items():
    if k not in st.session_state: st.session_state[k] = v

def get_c(addr):
    g = Nominatim(user_agent="v32_mgr")
    try:
        l = g.geocode(addr)
        return (l.latitude, l.longitude) if l else None
    except: return None

st.markdown("## 📡 송신소/중계소 관리 (레이어 복구)")

# [3] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 도구")
    gps = get_geolocation()
    my_p = None
    if gps and 'coords' in gps:
        my_p = [gps['coords']['latitude'], gps['coords']['longitude']]
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로"):
            st.session_state.map_center = my_p
            st.rerun()

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        c = get_c(sq)
        if c:
            st.session_state.temp_lat, st.session_state.temp_lon = c
            st.session_state.map_center = [c[0], c[1]]
            st.rerun()

    st.divider()
    cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
    nm = st.text_input("시설 명칭")
    
    t_la = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    t_lo = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    fla = st.number_input("위도", value=float(t_la), format="%.6f")
    flo = st.number_input("경도", value=float(t_lo), format="%.6f")

    chs = {}
    for i in range(0, len(ST_L), 2):
        c1, c2 = st.columns(2)
        chs[ST_L[i]] = c1.text_input(ST_L[i], key=f"in_{ST_L[i]}")
        chs[ST_L[i+1]] = c2.text_input(ST_L[i+1], key=f"in_{ST_L[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in ST_L] + [fla, flo, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.rerun()

    if not st.session_state.df.empty:
        st.divider()
        st.markdown("### 🗑️ 삭제")
        tg = st.selectbox("대상 선택", st.session_state.df['이름'].tolist())
        if st.button("🚨 시설 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != tg]
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [4] 지도 레이어 설정
m = folium.Map(location=st.session_state.map_center, zoom_start=14)

# 레이어 1: 산/도로명 위성
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}',
    attr='G', name='위성 (산/도로명)', overlay=False, control=True
).add_to(m)

# 레이어 2: 순수 위성
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}',
    attr='G', name='순수 위성', overlay=False, control=True
).add_to(m)

# 레이어 컨트롤 추가
folium.LayerControl(position='topright').add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person',
