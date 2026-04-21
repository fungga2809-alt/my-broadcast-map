import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 초기화
st.set_page_config(page_title="Broadcasting Master", layout="wide")
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
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=CL)
    else: st.session_state.df = pd.DataFrame(columns=CL)

sd = st.session_state
if 'center' not in sd: sd.center = [35.1796, 129.0756]
if 't_la' not in sd: sd.t_la = None
if 't_lo' not in sd: sd.t_lo = None

# 제목 변경
st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

# [2] 사이드바
with st.sidebar:
    st.header("⚙️ 도구")
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps else None
    if my_p:
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로"):
            sd.center = my_p
            st.rerun()

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        g = Nominatim(user_agent="v42_mgr")
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
    fla, flo = st.number_input("위도", value=float(la_v)), st.number_input("경도", value=float(lo_v))

    chs = {}
    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(SL), 2):
        c1, c2 = st.columns(2)
        chs[SL[i]] = c1.text_input(SL[i], key=f"i_{SL[i]}")
        chs[SL[i+1]] = c2.text_input(SL[i+1], key=f"i_{SL[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in SL] + [fla, flo, ""]
            sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
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

# [3] 지도 (800px 및 레이어 3종)
m = folium.Map(location=sd.center, zoom_start=14)
# 구글 레이어 주소
ly_y = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'
ly_s = 'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}'
ly_m = 'https://mt1.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}'

folium.TileLayer(tiles=ly_y, attr='G', name='위성+도로', overlay=False).add_to(m)
folium.TileLayer(tiles=ly_s, attr='G', name='순수 위성', overlay=False).add_to(m)
folium.TileLayer(tiles=ly_m, attr='G', name='일반 지도', overlay=False).add_to(m)
folium.LayerControl().add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        d = f"<br>📏 {round(geodesic(my_p, p).km, 2)}km" if my_p else ""
        dt = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" not in s and str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" in s and str(r[s]).strip() != ""])
        txt = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}{d}"
        folium.Marker(p, popup=folium.Popup(txt, max_width=300), 
                      icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green')).add_to(m)

# 800px 높이 출력
res = st_folium(m, width="100%", height=800, key="map_v42")

if res and res.get('last_clicked'):
    lc = res['last_clicked']
    la, lo = round(lc['lat'], 6), round(lc['lng'], 6)
    if sd.t_la != la:
        sd.t_la, sd.t_lo = la, lo
        st.rerun()

st.dataframe(sd.df, use_container_width=True)
