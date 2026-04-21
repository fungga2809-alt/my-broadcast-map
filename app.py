import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 설정
st.set_page_config(page_title="방송 시설 관리 PRO", layout="wide")
DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
COLS = ['구분', '이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# 초기 변수
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

def geocode_addr(address):
    geo = Nominatim(user_agent="v30_manager")
    try:
        loc = geo.geocode(address)
        return (loc.latitude, loc.longitude) if loc else None
    except: return None

st.markdown("## 📡 송신소/중계소 통합 관리")

# [3] 사이드바
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    gps = get_geolocation()
    my_p = None
    if gps and 'coords' in gps:
        my_p = [gps['coords']['latitude'], gps['coords']['longitude']]
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로 이동"):
            st.session_state.map_center = my_p
            st.rerun()

    st.divider()
    st.markdown("### 🔍 주소 검색")
    sq = st.text_input("주소 입력")
    if st.button("📍 위치 찾기"):
        c = geocode_addr(sq)
        if c:
            st.session_state.temp_lat, st.session_state.temp_lon = c
            st.session_state.map_center = [c[0], c[1]]
            st.rerun()

    st.divider()
    st.markdown("### 📍 시설물 등록")
    cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
    nm = st.text_input("명칭")
    
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
        if nm:
            new_v = [cat, nm] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.rerun()

    # --- [삭제 기능: 사이드바 하단] ---
    if not st.session_state.df.empty:
        st.divider()
        st.markdown("### 🗑️ 데이터 삭제")
        target = st.selectbox("삭제 대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 선택 시설 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != target]
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.warning(f"'{target}' 삭제됨")
            st.rerun()

# [4] 지도
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}', 
                 attr='G', name='위성', overlay=False).add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        d = f"<br>📏 {round(geodesic(my_p, p).km, 2)}km" if my_p else ""
        dtv = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" not in s and str(r[s]).strip() != ""])
        uhd = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" in s and str(r[s]).strip() != ""])
        pop = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dtv}<br>UHD: {uhd}{d}"
        folium.Marker(p, popup=folium.Popup(pop, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

# 에러 났던 지점 수정 (따옴표 닫기 확인)
res = st_folium(m, width="100%", height=500, key="map_v30")

if res and res.get('last_clicked'):
    lat, lon = round(res['last_clicked']['lat
