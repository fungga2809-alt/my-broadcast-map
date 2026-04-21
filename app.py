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
# 채널 리스트 확장 (UHD 추가)
ST_LIST = ['SBS', 'SBS(U)', 'KBS2', 'KBS2(U)', 'KBS1', 'KBS1(U)', 'EBS', 'EBS(U)', 'MBC', 'MBC(U)']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 및 누락 컬럼 보정
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

st.markdown("## 📡 중계소 통합 관리 (DTV/UHD)")

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
    st.markdown("### 📍 중계소 등록 (DTV/UHD)")
    new_name = st.text_input("중계소 명칭")
    
    # 채널 입력 (DTV와 UHD를 한 줄에 배치)
    chs = {}
    st.write("📺 물리 채널 (DTV | UHD)")
    for i in range(0, len(ST_LIST), 2):
        c1, c2 = st.columns(2)
        d_name, u_name = ST_LIST[i], ST_LIST[i+1]
        chs[d_name] = c1.text_input(d_name, key=f"in_{d_name}")
        chs[u_name] = c2.text_input(u_name, key=f"in_{u_name}")
    
    # 좌표 설정
    t_lat, t_lon = st.session_state.temp_lat, st.session_state.temp_lon
    m_lat, m_lon = st.session_state.map_center[0], st.session_state.map_center[1]

    flat = st.number_input("위도", value=float(t_lat if t_lat else m_lat), format="%.6f")
    flon = st.number_input("경도", value=float(t_lon if t_lon else m_lon), format="%.6f")
    memo = st.text_area("특이사항/메모")

    if st.button("✅ 데이터 저장"):
        if new_name:
            new_val = [new_name] + [chs[s] for s in ST_LIST] + [flat, flon, memo]
            new_df = pd.DataFrame([new_val], columns=COLS)
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [5] 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', 
                 attr='Google', name='Satellite').add_to(m)

if my_pos:
    folium.Marker(my_pos, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist = f"<br>📏 거리: {round(geodesic(my_pos, p).km, 2)}km" if my_pos else ""
        
        # 팝업 정보 구성 (DTV/UHD 구분)
        dtv_info = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" not in s and str(r[s]).strip() != ""])
        uhd_info = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if "(U)" in s and str(r[s]).strip() != ""])
        
        pop_txt = f"<b>{r['이름']}</b><br><b>[DTV]</b> {dtv_info}<br><b>[UHD]</b> {uhd_info}{dist}"
        folium.Marker(p, popup=folium.Popup(pop_txt, max_width=300), 
                      icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

output = st_folium(m, width="100%", height=500, key="broadcast_pro_v3")

if output and output.get('last_clicked'):
    clat, clon = round(output['last_clicked']['lat'], 6), round(output['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# [6] 하단 리스트
st.markdown("### 📋 전체 중계소 관리 리스트")
st.dataframe(st.session_state.df, use_container_width=True)
