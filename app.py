import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation
import os

st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# [데이터 초기화 로직은 이전과 동일]
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for s in STATIONS + ['위도', '경도', '메모']:
                if s not in st.session_state.df.columns: st.session_state.df[s] = ""
        except: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else: st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

st.title("📡 현장용 중계소 통합 관리 (GPS)")

# --- GPS 내 위치 파악 기능 ---
loc = get_geolocation()
my_pos = None
if loc:
    my_pos = (loc['coords']['latitude'], loc['coords']['longitude'])
    st.sidebar.success(f"📍 내 위치 확인됨: {round(my_pos[0],4)}, {round(my_pos[1],4)}")

# 2. 사이드바 (기존 기능 유지)
with st.sidebar:
    st.header("🔍 검색 및 도구")
    if my_pos and st.button("🎯 내 위치로 지도 이동"):
        st.session_state.map_center = [my_pos[0], my_pos[1]]
        st.rerun()
    
    st.divider()
    # [신규 등록 및 삭제 섹션은 이전과 동일하게 유지...]
    # (지면 관계상 핵심 로직 위주로 구성하며, 실제 파일에는 이전의 등록/삭제 코드를 그대로 붙여넣으시면 됩니다)

# 3. 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='위성 지도').add_to(m)
folium.LayerControl().add_to(m)

# 내 위치 표시 (오렌지색 마커)
if my_pos:
    folium.Marker(my_pos, tooltip="현재 내 위치", icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

# 중계소 마커 및 거리 계산
nearest_st = None
min_dist = float('inf')

for _, row in st.session_state.df.iterrows():
    try:
        st_pos = (float(row['위도']), float(row['경도']))
        dist_str = ""
        if my_pos:
            d = geodesic(my_pos, st_pos).km
            dist_str = f"<br>📏 거리: {round(d, 2)}km"
            if d < min_dist:
                min_dist = d
                nearest_st = row['이름']

        ch_info = " | ".join([f"{s}:{row[s]}" for s in STATIONS if pd.notna(row[s]) and str(row[s]).strip() != ""])
        folium.Marker(
            st_pos,
            popup=f"<b>{row['이름']}</b><br>{ch_info}{dist_str}",
            tooltip=f"{row['이름']} (클릭 시 상세정보)",
            icon=folium.Icon(color='blue', icon='tower-broadcast', prefix='fa')
        ).add_to(m)
    except: continue

if my_pos and nearest_st:
    st.info(f"🚩 현재 위치에서 가장 가까운 곳: **{nearest_st}** (약 {round(min_dist, 2)}km)")

map_data = st_folium(m, width=1000, height=600, key="gps_map")
# [클릭 이벤트 처리 로직 동일]

st.subheader("📋 전체 목록")
st.dataframe(st.session_state.df, use_container_width=True)
