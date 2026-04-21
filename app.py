import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# [1] 설정 및 데이터 로드
st.set_page_config(page_title="방송 관리 PRO", layout="wide")
DB = 'stations.csv'
ST_L = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
COLS = ['구분', '이름'] + ST_L + ['위도', '경도', '메모']

if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            if '구분' not in st.session_state.df.columns:
                st.session_state.df.insert(0, '구분', '중계소')
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# 초기 변수
for k, v in {'center':[35.1796, 129.0756], 't_la':None, 't_lo':None}.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown("## 📡 송신소/중계소 통합 관리")

# [2] 사이드바 도구
with st.sidebar:
    st.markdown("### ⚙️ 현장 도구")
    gps = get_geolocation()
    my_p = None
    if gps and 'coords' in gps:
        my_p = [gps['coords']['latitude'], gps['coords']['longitude']]
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로"):
            st.session_state.center = my_p
            st.rerun()

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        g = Nominatim(user_agent="v33_mgr")
        l = g.geocode(sq)
        if l:
            st.session_state.t_la, st.session_state.t_lo = l.latitude, l.longitude
            st.session_state.center = [l.latitude, l.longitude]
            st.rerun()

    st.divider()
    st.markdown("### 📍 시설 등록")
    cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
    nm = st.text_input("명칭")
    
    # 좌표 설정
    la_v = st.session_state.t_la if st.session_state.t_la else st.session_state.center[0]
    lo_v = st.session_state.t_lo if st.session_state.t_lo else st.session_state.center[1]
    fla, flo = st.number_input("위도", value=float(la_v)), st.number_input("경도", value=float(lo_v))

    chs = {}
    for i in range(0, len(ST_L), 2):
        c1, c2 = st.columns(2)
        chs[ST_L[i]] = c1.text_input(ST_L[i], key=f"i_{ST_L[i]}")
        chs[ST_L[i+1]] = c2.text_input(ST_L[i+1], key=f"i_{ST_L[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in ST_L] + [fla, flo, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([v], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.t_la = None
            st.rerun()

    if not st.session_state.df.empty:
        st.divider()
        tg = st.selectbox("삭제 대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 시설 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름'] != tg]
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [3] 지도 레이어
m = folium.Map(location=st.session_state.center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s,h&hl=ko&x={x}&y={y}&z={z}', 
                 attr='G', name='위성+도로', overlay=False).add_to(m)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}', 
                 attr='G', name='순수 위성', overlay=False).add_to(m)
folium.LayerControl().add_to(m)

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person', prefix='fa')).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        d = f"<br>📏 {round(geodesic(my_p, p).km, 2)}km" if my_p else ""
        dt = " | ".join([f"{s}:{r[s]}" for s in ST_L if "(U)" not in s and str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in ST_L if "(U)" in s and str(r[s]).strip() != ""])
        pop = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}{d}"
        folium.Marker(p, popup=folium.Popup(pop, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: continue

if st.session_state.t_la:
    folium.Marker([st.session_state.t_la, st.session_state.t_lo], icon=folium.Icon(color
