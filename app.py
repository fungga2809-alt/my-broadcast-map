import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 설정
st.set_page_config(page_title="Broadcasting Master", layout="wide")
DB = 'stations.csv'
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

sd = st.session_state
if 'df' not in sd:
    if os.path.exists(DB):
        try:
            sd.df = pd.read_csv(DB)
            if '구분' not in sd.df.columns:
                sd.df.insert(0, '구분', '중계소')
            for c in CL:
                if c not in sd.df.columns: sd.df[c] = ""
        except: sd.df = pd.DataFrame(columns=CL)
    else: sd.df = pd.DataFrame(columns=CL)

if 'center' not in sd: sd.center = [35.1796, 129.0756]
if 't_la' not in sd: sd.t_la = None
if 't_lo' not in sd: sd.t_lo = None

st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

# [2] 사이드바
with st.sidebar:
    st.header("⚙️ 도구")
    gps = get_geolocation()
    my_p = None
    if gps and 'coords' in gps:
        my_p = [gps['coords']['latitude'], gps['coords']['longitude']]
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로"):
            sd.center = my_p
            st.rerun()

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        g = Nominatim(user_agent="v48_mgr")
        l = g.geocode(sq)
        if l:
            sd.t_la, sd.t_lo = l.latitude, l.longitude
            sd.center = [l.latitude, l.longitude]
            st.rerun()

    st.divider()
    st.markdown("### 📍 시설 등록")
    cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
    nm = st.text_input("시설 명칭")
    la_v = sd.t_la if sd.t_la else sd.center[0]
    lo_v = sd.t_lo if sd.t_lo else sd.center[1]
    fla = st.number_input("위도", value=float(la_v), format="%.6f")
    flo = st.number_input("경도", value=float(lo_v), format="%.6f")

    chs = {}
    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(SL), 2):
        c1, c2 = st.columns(2)
        chs[SL[i]] = c1.text_input(SL[i], key=f"i_{SL[i]}")
        chs[SL[i+1]] = c2.text_input(SL[i+1], key=f"i_{SL[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in SL] + [fla, flo, ""]
            new_df = pd.DataFrame([v], columns=CL)
            sd.df = pd.concat([sd.df, new_df], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la = None
            st.rerun()

    if not sd.df.empty:
        st.divider()
        tg = st.selectbox("삭제", sd.df['이름'].tolist())
        if st.button("🚨 삭제"):
            sd.df = sd.df[sd.df['이름'] != tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [3] 지도 레이어 완벽 고정 (show 속성 사용)
m = folium.Map(location=sd.center, zoom_start=14, tiles=None)

ly_y = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'
ly_s = 'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}'
ly_m = 'https://mt1.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}'

# 핵심: 위성+도로만 show=True 로 켜두고, 나머지는 show=False 로 꺼둡니다!
folium.TileLayer(tiles=ly_y, attr='
