import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 기본 설정
st.set_page_config(page_title="Broadcasting Map", layout="wide")
DB = 'stations.csv'
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
            for c in CL:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=CL)
    else: st.session_state.df = pd.DataFrame(columns=CL)

sd = st.session_state
if 'center' not in sd: sd.center = [35.1796, 129.0756]
if 't_la' not in sd: sd.t_la = None
if 't_lo' not in sd: sd.t_lo = None

st.title("📡 시설 관리 시스템 v35")

# [3] 사이드바 도구
with st.sidebar:
    st.header("⚙️ 도구")
    gps = get_geolocation()
    my_p = None
    if gps and 'coords' in gps:
        my_p = [gps['coords']['latitude'], gps['coords']['longitude']]
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로 이동"):
            sd.center = my_p
            st.rerun()

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        g = Nominatim(user_agent="v35_mgr")
        l = g.geocode(sq)
        if l:
            sd.t_la, sd.t_lo = l.latitude, l.longitude
            sd.center = [l.latitude, l.longitude]
            st.rerun()

    st.divider()
    cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
    nm = st.text_input("시설 명칭")
    la_v = sd.t_la if sd.t_la else sd.center[0]
    lo_v = sd.t_lo if sd.t_lo else sd.center[1]
    fla = st.number_input("위도", value=float(la_v), format="%.6f")
    flo = st.number_input("경도", value=float(lo_v), format="%.6f")

    chs = {}
    for s in SL:
        chs[s] = st.text_input(s, key=f"i_{s}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in SL] + [fla, flo, ""]
            sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la = None
            st.rerun()

    if not sd.df.empty:
        st.divider()
        tg = st.selectbox("삭제 대상", sd.df['이름'].tolist())
        if st.button("🚨 시설 삭제"):
            sd.df = sd.df[sd.df['이름'] != tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [4] 지도 설정
st.write("---")
# 지도가 로딩 중인지 확인하기 위한 메시지
st.info("💡 지도가 나타나지 않으면 화면을 아래로 당겨 새로고침 하세요.")

m = folium.Map(location=sd.center, zoom_start=14)
ly1 = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'
folium.TileLayer(tiles=ly1, attr='G', name='Satellite').add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        pop = f"<b>[{r['구분']}] {r['이름']}</b>"
        folium.Marker(p, popup=pop, icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green')).add_to(m)

# 지도 출력 (너비를 숫자로 고정하여 호환성 강화)
res = st_folium(m, width=700, height=500, key="map_rescue_v35")

if res and res.get('last_clicked'):
    lc = res['last_clicked']
    la, lo = round(lc['lat'], 6), round(lc['lng'], 6)
    if sd.t_la != la:
        sd.t_la, sd.t_lo = la, lo
        st.rerun()

st.subheader("📋 시설 목록")
st.dataframe(sd.df, use_container_width=True)
