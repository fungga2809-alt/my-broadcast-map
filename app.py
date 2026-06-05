import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import math
import re
from branca.element import Template, MacroElement
from streamlit_gsheets import GSheetsConnection 
import time

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v1031", layout="wide")

# [CSS 스타일]
st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; max-width: 100% !important; }
    [data-testid="stSidebar"] { background-color: #f1f3f5 !important; border-right: 1px solid #dee2e6 !important; }
    .analysis-box { background-color: #ffffff; border: 1px solid #ced4da; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

sd = st.session_state
DB = 'stations.csv'

# [채널 목록]
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL_DMB = ['DMB(SBS)', 'DMB(KBS)', 'DMB(MBC)']
SL_FM = ['KBS1-FM', 'KBS2-FM', 'KBS-Music', 'MBC-FM', 'MBC-AM', 'KNN-FM', 'EBS-FM', '교통방송', '국악방송', '불교방송', '평화방송', '기독교방송']
SL = SL_DTV + SL_UHD + SL_DMB + SL_FM
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [RF 및 도구 함수]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
    except: return default

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def parse_coord_input(q):
    try:
        if ',' in q and '°' not in q: return tuple(map(float, q.split(',')))
        if '°' in q:
            matches = re.findall(r"(\d+)[°\s]+(\d+)['\s]+([\d\.]+)(?:\"|''|\s)*([NSEW])", q.upper())
            if len(matches) == 2:
                c = []
                for m in matches:
                    dd = float(m[0]) + float(m[1])/60 + float(m[2])/3600
                    if m[3] in ['S', 'W']: dd *= -1
                    c.append(dd)
                return c[0], c[1]
    except: pass
    return None, None

def generate_popup_html(r):
    dtv_h = "".join(["<div style='display:flex; justify-content:space-between;'><span><b>" + str(s) + "</b></span><span>" + str(r.get(s, '')) + "</span></div>" for s in SL_DTV if r.get(s, '')])
    uhd_h = "".join(["<div style='display:flex; justify-content:space-between; color:#007bff;'><span><b>" + str(s) + "</b></span><span>" + str(r.get(s, '')) + "</span></div>" for s in SL_UHD if r.get(s, '')])
    dmb_h = "".join(["<div style='display:flex; justify-content:space-between;'><span><b>" + str(s).split('(')[1][:-1] + "</b></span><b>" + str(r.get(s, '')) + "</b></div>" for s in SL_DMB if r.get(s, '') and '(' in str(s)])
    fm_h = "".join(["<div style='display:flex; justify-content:space-between;'><span>" + str(s) + "</span><b>" + str(r.get(s, '')) + " MHz</b></div>" for s in SL_FM if r.get(s, '')])
    return f"""<div style='width:350px; font-family:sans-serif; font-size:14px;'>
        <div style='font-size:18px; font-weight:bold; border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:8px;'>[{r.get('구분','')}] {r.get('이름','')}</div>
        <div style='color:#666; margin-bottom:10px;'>{r.get('주소','')}</div>
        <div style='display:flex; justify-content:space-between; margin-bottom:10px;'><div style='width:48%;'><b>📡 DTV</b>{dtv_h}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:10px;'><b>✨ UHD</b>{uhd_h}</div></div>
    </div>"""

# 초기화
defaults = {'gs_sync_on': True, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "", 'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 310000, 'm_mode': "정보 수정", 'target_nm': None, 'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'prev_sel': [], 'temp_active': False, 'temp_lat': 0.0, 'temp_lon': 0.0, 'show_coverage': False, 'cov_radius': 10, 'show_los': True}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

def load_db():
    if sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).astype(str).fillna("")
            return df[CL]
        except: pass
    try: return pd.read_csv(DB, dtype=str, encoding='utf-8-sig').fillna("")[CL]
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df[CL].to_csv(DB, index=False, encoding='utf-8-sig') 
    if sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df[CL])
        except: pass

if 'df' not in sd: sd.df = load_db()

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 관제 및 분석")
    sd.gs_sync_on = st.toggle("🌐 클라우드 실시간 연동", value=sd.gs_sync_on)
    sd.map_layer = st.radio("🗺️ 지도 레이어", ["일반", "위성", "위성+이름", "특수지형도"], horizontal=True)
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + sorted(sd.df['지역'].unique().tolist()))
    
    with st.form("jump_form"):
        jump_q = st.text_input("🌍 공간 이동 (좌표/주소 엔터)")
        if st.form_submit_button("이동") and jump_q:
            lat_lon = parse_coord_input(jump_q)
            if lat_lon: sd.base_center = list(lat_lon); sd.crosshair_center = list(lat_lon); sd.map_key += 1; st.rerun()
            else:
                loc = Nominatim(user_agent="b_master").geocode(jump_q)
                if loc: sd.base_center = [loc.latitude, loc.longitude]; sd.crosshair_center = [loc.latitude, loc.longitude]; sd.map_key += 1; st.rerun()

    st.subheader("📝 시설 제원")
    if st.button("🎯 1. 위치 추출"):
        sd.in_t_la, sd.in_t_lo = sd.crosshair_center; sd.temp_active = True; sd.temp_lat, sd.temp_lon = sd.crosshair_center; st.rerun()

    t1, t2 = st.tabs(["기본 정보", "채널/주파수"])
    with t1:
        sd.in_reg_direct = st.text_input("지역", value=sd.in_reg_direct)
        sd.in_v_nm = st.text_input("시설명", value=sd.in_v_nm)
        sd.in_v_cat = st.radio("구분", ["송신소", "중계소"], index=0)
    with t2:
        for s in SL_DTV: sd[f"ch_{s}"] = st.text_input(s, value=sd.get(f"ch_{s}", ""))

    if st.button("✅ 2. 데이터 저장"):
        new_row = [sd.in_reg_direct, sd.in_v_cat, sd.in_v_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), ""]
        sd.df = pd.concat([sd.df, pd.DataFrame([new_row], columns=CL)], ignore_index=True)
        save_db(sd.df); sd.temp_active = False; st.rerun()

# --- 메인 화면 ---
res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=('http://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'), attr='Google')

# 조준경 삽입 수정 (호환성 문제 해결)
crosshair_html = """
<div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid red; border-radius: 50%; pointer-events: none; z-index: 1000;">
    <div style="position: absolute; top: 50%; left: -10px; width: 60px; height: 2px; background: red;"></div>
    <div style="position: absolute; top: -10px; left: 50%; width: 2px; height: 60px; background: red;"></div>
</div>
"""
m.get_root().html.add_child(folium.Element(crosshair_html))

for _, r in res_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat != 0: folium.Marker([lat, lon], popup=generate_popup_html(r)).add_to(m)

if sd.get('temp_active'): folium.Marker([sd.temp_lat, sd.temp_lon], icon=folium.Icon(color='gray')).add_to(m)

map_res = st_folium(m, use_container_width=True, height=700, key=f"map_{sd.map_key}")
if map_res and map_res.get("center"): sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]
