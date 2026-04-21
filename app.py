import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import os

# 1. 페이지 설정
st.set_page_config(page_title="중계소 관리 - 위성모드", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# 데이터 초기화 (오류 방지용)
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
            for s in STATIONS + ['위도', '경도', '메모']:
                if s not in st.session_state.df.columns:
                    st.session_state.df[s] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else:
        st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

# 상태 변수
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

def geocode(address):
    geolocator = Nominatim(user_agent="broadcasting_manager_v13")
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except: return None

st.title("📡 부산/울산 중계소 통합 관리 시스템")

# 2. 사이드바
with st.sidebar:
    st.header("🔍 검색")
    search_keyword = st.text_input("이름 또는 채널 검색")
    if search_keyword:
        mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_keyword, na=False)).any(axis=1)
        filtered = st.session_state.df[mask]
        if not filtered.empty:
            sel_name = st.selectbox("결과 선택", filtered['이름'].tolist())
            if st.button("📍 위치로 이동"):
                target = filtered[filtered['이름'] == sel_name].iloc[0]
                st.session_state.map_center = [target['위도'], target['경도']]
                st.rerun()

    st.divider()
    st.header("📍 신규 등록")
    addr = st.text_input("🏠 주소 검색")
    if st.button("주소 검색"):
        coords = geocode(addr)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = coords
            st.rerun()

    new_name = st.text_input("중계소 명칭")
    
    st.subheader("📺 방송사별 채널")
    ch_data = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(STATIONS):
        ch_data[s] = (c1 if i % 2 == 0 else c2).text_input(f"{s}")

    d_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    d_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    f_lat = st.number_input("위도", value=float(d_lat), format="%.6f")
    f_lon = st.number_input("경도", value=float(d_lon), format="%.6f")
    memo = st.text_area("메모")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 저장"):
            if new_name:
                row_data = [new_name] + [ch_data[s] for s in STATIONS] + [f_lat, f_lon, memo]
                new_row = pd.DataFrame([row_data], columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
                st.session_state.temp_lat = None
                st.success("저장 완료!")
                st.rerun()
    with col2:
        if st.button("❌ 취소"):
            st.session_state.temp_lat = None
            st.rerun()

    st.divider()
    if not st.session_state.df.empty:
        st.header("🗑️ 삭제")
        del_item = st.selectbox("삭제할 지점", st.session_state.df['이름'].tolist())
        if st.button("🚨 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != del_item]
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.rerun()

# 3. 메인 지도 영역
# 안정성을 위해 기본 타일을 지정해서 생성합니다.
m = folium.Map(location=st.session_state.map_center, zoom_start=14)

# 구글 위성 레이어 강제 추가
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google Satellite',
    name='Google Satellite',
    overlay=False,
    control=True
).add_to(m)

# 마커 추가 전 데이터 검사
for _, row in st.session_state.df.iterrows():
    try:
        lat, lon = float(row['위도']), float(row['경도'])
        ch_info = " | ".join([f"{s}:{row[s]}" for s in STATIONS if pd.notna(row[s]) and str(row[s]).strip() != ""])
        folium.Marker(
            [lat, lon],
            popup=f"{row['이름']}<br>{ch_info}",
            tooltip=f"{row['이름']} (채널 정보 포함)",
            icon=folium.Icon(color='blue', icon='tower-broadcast', prefix='fa')
        ).add_to(m)
    except: continue

if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='red')).add_to(m)

# 지도 출력
map_data = st_folium(m, width=1000, height=600, key="v13_stable_map")

if map_data and map_data.get('last_clicked'):
    clat, clon = round(map_data['last_clicked']['lat'], 6), round(map_data['last_clicked']['lng'], 6)
    if st.session_state.temp_lat is None or round(st.session_state.temp_lat, 6) != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# 4. 목록 표
st.subheader("📋 전체 중계소 목록")
st.dataframe(st.session_state.df, use_container_width=True)