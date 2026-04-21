import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 페이지 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

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

# 세션 상태 초기화
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

def geocode_addr(address):
    geolocator = Nominatim(user_agent="broadcast_manager_v27")
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except: return None

st.markdown("## 📡 중계소 통합 관리 (지도 복구 버전)")

# [3] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
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
    st.markdown("### 🔍 주소 검색")
    search_q = st.text_input("주소 입력 (예: 녹산동)")
    if st.button("📍 주소 찾기"):
        coords = geocode_addr(search_q)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = [coords[0], coords[1]]
            st.rerun()
        else:
            st.error("주소를 찾지 못했습니다.")

    st.divider()
    st.markdown("### 📍 중계소 등록")
    name = st.text_input("중계소 명칭")
    
    t_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    t_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    
    flat = st.number_input("위도", value=float(t_lat), format="%.6f")
    flon = st.number_input("경도", value=float(t_lon), format="%.6f")

    chs = {}
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        chs[ST_LIST[i]] = c1.text_input(ST_LIST[i], key=f"in_{ST_LIST[i]}")
        chs[ST_LIST[i+1]] = c2.text_input(ST_LIST[i+1], key=f"in_{ST_LIST[i+1]}")

    if st.button("✅ 저장"):
        if name:
            new_v = [name] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.rerun()

# [4] 메인 지도 (표시 문제 해결을 위해 넓이를 700으로 고정 시도)
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}',
    attr='Google', name='1. 위성 (산/도로명)', overlay=False, control=True
).add_to(m)

folium.LayerControl(position='topright').add_to(m)

if my_pos:
    folium.Marker(my_pos, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        pop = f"<b>{r['이름']}</b>"
        folium.Marker(p, popup=pop, icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

# 고유 키값을 바꿔서 지도를 강제로 새로 그리게 함
output = st_folium(m, width=700, height=500, key="map_reset_v27")

if output and output.get('last_clicked'):
    clat, clon = round(output['last_clicked']['lat'], 6), round(output['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

st.dataframe(st.session_state.df, use_container_width=True)
