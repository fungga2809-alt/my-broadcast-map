import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 설정 및 데이터 로드
st.set_page_config(page_title="Broadcasting Mgr", layout="wide")
DB = 'stations.csv'
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
            for c in CL:
                if c not in st.session_state.df.columns:
                    st.session_state.df[c] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=CL)
    else:
        st.session_state.df = pd.DataFrame(columns=CL)

# 세션 변수 짧게 줄임
sd = st.session_state
if 'center' not in sd: sd.center = [35.1796, 129.0756]
if 't_la' not in sd: sd.t_la = None
if 't_lo' not in sd: sd.t_lo = None

st.title("📡 시설 관리 PRO (v34)")

# [2] 사이드바 도구
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
        g = Nominatim(user_agent="v34_mgr")
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
        if st.button("🚨 삭제 실행"):
            sd.df = sd.df[sd.df['이름'] != tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [3] 지도 설정 (레이어 조각내기)
m = folium.Map(location=sd.center, zoom_start=14)
ly1 = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'
ly2 = 'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}'
folium.TileLayer(tiles=ly1, attr='G', name='위성+도로').add_to(m)
folium.TileLayer(tiles=ly2, attr='G', name='순수 위성').add_to(m)
folium.LayerControl().add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        d_km = ""
        if my_p:
            km = round(geodesic(my_p, p).km, 2)
            d_km = f"<br>📏 {km}km"
        
        dt = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" not in s and str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" in s and str(r[s]).strip() != ""])
        txt = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}{d_km}"
        
        # 줄 잘림 방지를 위해 마커 설정을 조각냄
        pp = folium.Popup(txt, max_width=300)
        ic = folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')
        folium.Marker(p, popup=pp, icon=ic).add_to(m)
    except: pass

if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green')).add_to(m)

# [핵심] 지도 출력 및 클릭
