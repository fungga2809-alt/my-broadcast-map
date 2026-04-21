import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation

# [1] 앱 기본 설정
st.set_page_config(page_title="중계소 통합 관리", layout="wide")

DB_FILE = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 (파일이 없으면 새로 생성)
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

# [3] 세션 상태 변수 초기화
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

st.markdown("## 📡 중계소 통합 관리 시스템")

# [4] 사이드바: GPS 및 등록 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    
    # [에러 수정 지점] GPS 좌표 안전하게 가져오기
    loc = get_geolocation()
    my_pos = None
    if loc and 'coords' in loc:
        try:
            my_pos = [loc['coords']['latitude'], loc['coords']['longitude']]
            st.success("📍 GPS 연결 성공")
            if st.button("🎯 내 위치로 지도 이동"):
                st.session_state.map_center = my_pos
                st.rerun()
        except KeyError:
            st.warning("GPS 데이터를 읽는 중입니다...")
    else:
        st.info("GPS 권한을 허용해 주세요.")

    st.divider()
    st.markdown("### 📍 새 중계소 등록")
    new_name = st.text_input("중계소 이름")
    
    # 채널 입력란 2열 배치
    chs = {}
    col1, col2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (col1 if i % 2 == 0 else col2).text_input(s)
    
    # 지도 클릭 시 좌표가 자동으로 들어옴
    lat_val = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    lon_val = st.session_state.temp_lon if st.session_state.temp_lon else st.
