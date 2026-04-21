import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
import re
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Master", layout="wide")
DB = 'stations.csv'
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

sd = st.session_state

# [1] 데이터 로드
if 'df' not in sd:
    try:
        sd.df = pd.read_csv(DB, dtype=str).fillna("")
        if '구분' not in sd.df.columns: sd.df.insert(0, '구분', '중계소')
        for c in CL:
            if c not in sd.df.columns: sd.df[c] = ""
    except:
        sd.df = pd.DataFrame(columns=CL, dtype=str)

defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'layer': "위성+도로", 'last_target': None, 'last_mode': "새로 등록", 'history': []}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"i_{s}" not in sd: sd[f"i_{s}"] = ""

def save_history():
    sd.history.append(sd.df.copy())
    if len(sd.history) > 10: sd.history.pop(0)

def parse_dms(dms_str):
    try:
        pattern = r"(\d+)°(\d+)'([\d.]+)\"([NSEW])"
        parts = re.findall(pattern, dms_str)
        if len(parts) != 2: return None, None
        results = []
        for d, m, s, h in parts:
            dd = float(d) + float(m)/60 + float(s)/3600
            if h in ['S', 'W']: dd = -dd
            results.append(round(dd, 6))
        return results[0], results[1]
    except: return None, None

st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

# [2] 사이드바 도구
with st.sidebar:
    st.header("⚙️ 도구")
    
    t_c1, t_c2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    
    if t_c1.button("🎯 내 위치로"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, None, None; st.rerun()
        
    if t_c2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop()
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.last_target = None, None, None; st.rerun()

    st.divider()
    sd.layer = st.radio("🗺️ 지도 모드", ["위성+도로", "순수 위성", "일반 지도"], horizontal=True)

    st.divider()
    sq = st.text_input("📍 주소/DMS 좌표 검색")
    if st.button("🔍 찾기"):
        d_la, d_lo = parse_dms(sq)
        if d_la and d_lo:
            sd.t_la, sd.t_lo, sd.center = d_la, d_lo, [d_la, d_lo]
            st.rerun()
        else:
            try:
                l = Nominatim(user_agent="v62_mgr").geocode(sq)
                if l:
                    sd.t_la, sd.t_lo, sd.center = l.latitude, l.longitude, [l.latitude, l.longitude]
                    st.
