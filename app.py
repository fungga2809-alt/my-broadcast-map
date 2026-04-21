import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 페이지 설정
st.set_page_config(page_title="방송 시설물 관리 시스템", layout="wide")

DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
# '구분' 컬럼 추가
COLS = ['구분', '이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 및 보정
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            # 기존 데이터에 '구분' 컬럼이 없으면 생성
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
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
    geolocator = Nominatim(user_agent="broadcast_manager_v28")
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except: return None

st.markdown("## 📡 송신소/중계소 통합 관리")

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
    search_q = st.text_input("주소 입력")
    if st.button("📍 위치 찾기"):
        coords = geocode_addr(search_q)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = [coords[0], coords[1]]
            st.rerun()

    st.divider()
    st.markdown("### 📍 시설물 등록")
    # 구분 선택 추가
    category = st.radio("시설 구분", ["송신소", "중계소"], horizontal=True)
    name = st.text_input("시설 명칭")
    
    t_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    t_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    
    flat = st.number_input("위도", value=float(t_lat), format="%.6f")
    flon = st.number_input("경도", value=float(t_lon), format="%.6f")

    chs = {}
    st.write("📺 채널 입력")
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        chs[ST_LIST[i]] = c1.text_input(ST_LIST[i], key=f"in_{ST_LIST[i]}")
        chs[ST_LIST[i+1]] = c2.text_input(ST_LIST[i+1], key=f"in_{ST_LIST[i+1]}")

    if st.button("✅ 데이터 저장"):
        if name:
            new_v = [category, name] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [4] 메인 지도
m = folium.Map(location=st.session_state.map_center, zoom_start=14)

# 위성 레이어
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}',
    attr='Google', name='위성 (산/도로명)', overlay=False, control=True
).add_to(m)

if my_pos:
    folium.Marker(my_pos, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

# 마커 표시 (구분에 따른 색상 변경)
for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        # 송신소는 빨간색, 중계소는 파란색
        m_color = 'red' if r['구분'] == '송신소' else 'blue'
        
        dist = f"<br>📏 거리: {round(geodesic(my_pos, p).km, 2)}km" if my_pos else ""
        dtv = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" not in s and str(r[s]).strip() != ""])
        uhd = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" in s and str(r[s]).strip() != ""])
        
        pop = f"<b>[{r['구분']}] {r['이름']}</b><br><b>[DTV]</b> {dtv}<br><b>[UHD]</b> {uhd}{dist}"
        folium.Marker(p, popup=folium.Popup(pop, max_width=300), 
                      icon=folium.Icon(color=m_color, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

output = st_folium(m, width="100%", height=500, key="map_v28")

if output and output.get('last_clicked'):
    clat, clon = round(output['last_clicked']['lat'], 6), round(output['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# [5] 하단 목록
st.markdown("### 📋 시설물 관리 목록")
st.dataframe(st.session_state.df, use_container_width=True)
