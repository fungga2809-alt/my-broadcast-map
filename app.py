import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation

# [1] 앱 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

DB = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 세션 상태 초기화
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

st.markdown("## 📡 중계소 통합 관리 시스템")

# [4] 사이드바: GPS 및 등록 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    
    # GPS 안정화 버전
    loc = get_geolocation()
    my_pos = None
    if loc:
        my_pos = [loc['coords']['latitude'], loc['coords']['longitude']]
        st.success(f"📍 내 위치 연결됨")
        if st.button("🎯 내 위치로 지도 이동"):
            st.session_state.map_center = my_pos
            st.rerun()
    else:
        st.warning("GPS 권한 허용이 필요합니다.")

    st.divider()
    st.markdown("### 📍 새 중계소 등록")
    name = st.text_input("중계소 이름")
    
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i%2==0 else c2).text_input(s)
    
    lat_v = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    lon_v = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    
    flat = st.number_input("위도", value=float(lat_v), format="%.6f")
    flon = st.number_input("경도", value=float(lon_v), format="%.6f")
    memo = st.text_area("메모")

    if st.button("✅ 데이터 저장"):
        if name:
            new_data = [name] + [chs[s] for s in ST_LIST] + [flat, flon, memo]
            new_df = pd.DataFrame([new_data], columns=COLS)
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [5] 메인 지도 (터치 등록 최적화)
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)

if my_pos:
    folium.Marker(my_pos, tooltip="내 위치", icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist_info = ""
        if my_pos:
            dist_info = f"<br>📏 거리: {round(geodesic(my_pos, p).km, 2)}km"
        
        popup_txt = f"<b>{r['이름']}</b><br>" + " | ".join([f"{s}:{r[s]}" for s in ST_LIST]) + dist_info
        folium.Marker(p, popup=popup_txt, icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

# 지도 터치/클릭 감지 (key 값을 바꿔서 새로고침 방지)
map_data = st_folium(m, width="100%", height=500, key="field_map_final_v1")

if map_data and map_data.get('last_clicked'):
    clat, clon = round(map_data['last_clicked']['lat'], 6), round(map_data['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# [6] 전체 목록
st.markdown("### 📋 등록된 중계소 목록")
st.dataframe(st.session_state.df, use_container_width=True)
