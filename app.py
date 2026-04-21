import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation

# [1] 앱 설정
st.set_page_config(page_title="중계소 통합 관리", layout="wide")

DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for c in COLS:
                if c not in st.session_state.df.columns:
                    st.session_state.df[c] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=COLS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 초기 변수 설정
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

st.markdown("## 📡 중계소 통합 관리 시스템")

# [4] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    
    # GPS 위치 가져오기
    loc = get_geolocation()
    my_pos = None
    if loc and 'coords' in loc:
        try:
            my_pos = [loc['coords']['latitude'], loc['coords']['longitude']]
            st.success("📍 GPS 연결 성공")
            if st.button("🎯 내 위치로 이동"):
                st.session_state.map_center = my_pos
                st.rerun()
        except:
            pass

    st.divider()
    st.markdown("### 📍 새 중계소 등록")
    new_name = st.text_input("중계소 이름")
    
    # 채널 입력
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i % 2 == 0 else c2).text_input(s)
    
    # [수정된 부분] 좌표를 변수에 나눠 담아 잘림 방지
    t_lat = st.session_state.temp_lat
    t_lon = st.session_state.temp_lon
    m_lat = st.session_state.map_center[0]
    m_lon = st.session_state.map_center[1]

    final_lat = st.number_input("위도", value=float(t_lat if t_lat else m_lat), format="%.6f")
    final_lon = st.number_input("경도", value=float(t_lon if t_lon else m_lon), format="%.6f")
    
    memo = st.text_area("메모")

    if st.button("✅ 데이터 저장"):
        if new_name:
            new_row = [new_name] + [chs[s] for s in ST_LIST] + [final_lat, final_lon, memo]
            new_df = pd.DataFrame([new_row], columns=COLS)
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [5] 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

# 마커 표시
if my_pos:
    folium.Marker(my_pos, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist = ""
        if my_pos:
            km = geodesic(my_pos, p).km
            dist = f"<br>📏 거리: {round(km, 2)}km"
        pop = f"<b>{r['이름']}</b><br>" + " | ".join([f"{s}:{r[s]}" for s in ST_LIST]) + dist
        folium.Marker(p, popup=pop, icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except:
        continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

output = st_folium(m, width="100%", height=500, key="broadcast_v25")

if output and output.get('last_clicked'):
    clat, clon = round(output['last_clicked']['lat'], 6), round(output['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# [6] 데이터 리스트
st.markdown("### 📋 중계소 관리 목록")
st.dataframe(st.session_state.df, use_container_width=True)
