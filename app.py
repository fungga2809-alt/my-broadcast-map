import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation

# [1] 앱 설정
st.set_page_config(page_title="중계소 통합 관리 PRO", layout="wide")

DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [데이터 로드 부분 생략하지 않고 포함]
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

st.markdown("## 📡 중계소 통합 관리 (레이어 선택)")

# [4] 사이드바 (GPS 및 등록)
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
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
    st.markdown("### 📍 중계소 등록")
    new_name = st.text_input("중계소 명칭")
    chs = {}
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        d_n, u_n = ST_LIST[i], ST_LIST[i+1]
        chs[d_n] = c1.text_input(d_n, key=f"in_{d_n}")
        chs[u_n] = c2.text_input(u_n, key=f"in_{u_n}")
    
    t_lat, t_lon = st.session_state.temp_lat, st.session_state.temp_lon
    m_lat, m_lon = st.session_state.map_center[0], st.session_state.map_center[1]
    flat = st.number_input("위도", value=float(t_lat if t_lat else m_lat), format="%.6f")
    flon = st.number_input("경도", value=float(t_lon if t_lon else m_lon), format="%.6f")
    
    if st.button("✅ 데이터 저장"):
        if new_name:
            new_val = [new_name] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_val], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.rerun()

# [5] 메인 지도 영역 (레이어 변경 핵심 부분)
m = folium.Map(location=st.session_state.map_center, zoom_start=14)

# 레이어 1: 순수 위성 사진 (글자/도로 없음 - CLEAN)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}',
    attr='Google',
    name='구글 위성 (깔끔하게)',
    overlay=False,
    control=True
).add_to(m)

# 레이어 2: 위성 + 도로/명칭 (HYBRID)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}',
    attr='Google',
    name='구글 위성 (도로명 포함)',
    overlay=False,
    control=True
).add_to(m)

# 레이어 선택 컨트롤 추가
folium.LayerControl(position='topright').add_to(m)

# 마커 표시 로직 (이전과 동일)
if my_pos:
    folium.Marker(my_pos, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist = f"<br>📏 거리: {round(geodesic(my_pos, p).km, 2)}km" if my_pos else ""
        dtv = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" not in s and str(r[s]).strip() != ""])
        uhd = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" in s and str(r[s]).strip() != ""])
        pop = f"<b>{r['이름']}</b><br><b>[DTV]</b> {dtv}<br><b>[UHD]</b> {uhd}{dist}"
        folium.Marker(p, popup=folium.Popup(pop, max_width=300), icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

output = st_folium(m, width="100%", height=500, key="broadcast_pro_v4")

if output and output.get('last_clicked'):
    clat, clon = round(output['last_clicked']['lat'], 6), round(output['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

st.dataframe(st.session_state.df, use_container_width=True)
