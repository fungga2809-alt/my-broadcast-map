import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import os

# 1. 페이지 설정
st.set_page_config(page_title="중계소 통합 관리 시스템", layout="wide")

DB_FILE = 'stations.csv'
STATIONS = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']

# 데이터 로드 및 초기화
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            st.session_state.df = pd.read_csv(DB_FILE)
        except:
            st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])
    else:
        st.session_state.df = pd.DataFrame(columns=['이름'] + STATIONS + ['위도', '경도', '메모'])

# 지도 중심 및 임시 좌표 상태 관리
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756] # 기본값: 부산시청
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

# 주소 -> 좌표 변환 함수
def geocode_address(address):
    geolocator = Nominatim(user_agent="my_broadcast_manager")
    try:
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

st.title("📡 부산/울산 중계소 통합 관리 시스템")

# 2. 사이드바 구성
with st.sidebar:
    st.header("📍 신규 지점 등록")
    
    # --- [추가된 주소 검색 기능] ---
    search_addr = st.text_input("🏠 주소 검색 (예: 부산 남구 전포동)")
    if st.button("주소로 위치 찾기"):
        coords = geocode_address(search_addr)
        if coords:
            st.session_state.temp_lat, st.session_state.temp_lon = coords
            st.session_state.map_center = [coords[0], coords[1]]
            st.success("위치를 찾았습니다! 지도를 확인하세요.")
            st.rerun()
        else:
            st.error("주소를 찾을 수 없습니다. 정확한 주소를 입력해 주세요.")
    
    st.divider()
    
    # 등록 정보 입력
    new_name = st.text_input("중계소 명칭")
    st.write("📺 물리 채널")
    ch_inputs = {}
    col1, col2 = st.columns(2)
    for i, s in enumerate(STATIONS):
        if i % 2 == 0:
            ch_inputs[s] = col1.text_input(s)
        else:
            ch_inputs[s] = col2.text_input(s)

    # 검색된 좌표나 클릭한 좌표가 있으면 자동으로 채워짐
    lat_val = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    lon_val = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    
    f_lat = st.number_input("위도", value=float(lat_val), format="%.6f")
    f_lon = st.number_input("경도", value=float(lon_val), format="%.6f")
    memo = st.text_area("메모/특이사항")

    if st.button("✅ 데이터 저장"):
        if new_name:
            new_row = [new_name] + [ch_inputs[s] for s in STATIONS] + [f_lat, f_lon, memo]
            st.session_state.df.loc[len(st.session_state.df)] = new_row
            st.session_state.df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None # 좌표 초기화
            st.success(f"{new_name} 저장 완료!")
            st.rerun()

# 3. 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
# 위성 지도 설정
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google',
    name='Google Satellite',
    overlay=False,
    control=True
).add_to(m)

# 기존 마커 표시
for index, row in st.session_state.df.iterrows():
    folium.Marker(
        [row['위도'], row['경도']],
        popup=f"<b>{row['이름']}</b><br>메모: {row['메모']}",
        tooltip=row['이름']
    ).add_to(m)

# 검색하거나 클릭한 위치에 임시 마커 표시
if st.session_state.temp_lat:
    folium.Marker(
        [st.session_state.temp_lat, st.session_state.temp_lon],
        icon=folium.Icon(color='red', icon='info-sign'),
        tooltip="검색된 위치"
    ).add_to(m)

# 지도 클릭 시 좌표 획득 기능
map_data = st_folium(m, width=1000, height=600)

if map_data['last_clicked']:
    st.session_state.temp_lat = map_data['last_clicked']['lat']
    st.session_state.temp_lon = map_data['last_clicked']['lng']
    st.rerun()

# 4. 하단 데이터 표
st.subheader("📋 전체 중계소 목록")
st.dataframe(st.session_state.df, use_container_width=True)
