import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import math
import numpy as np
from branca.element import Template, MacroElement

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v950", layout="wide")
DB = 'stations.csv'
sd = st.session_state

# 구글 시트 라이브러리 체크
try:
    from streamlit_gsheets import GSheetsConnection
    HAS_GSHEETS = True
except:
    HAS_GSHEETS = False

# [도구함]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
    except: return default

def get_google_format(lat, lon):
    try:
        if not lat or not lon: return ""
        def to_dms(deg, is_lat):
            d = int(abs(float(deg)))
            m = int((abs(float(deg)) - d) * 60)
            s = round((abs(float(deg)) - d - m/60) * 3600, 2)
            suffix = (("N" if float(deg) >= 0 else "S") if is_lat else ("E" if float(deg) >= 0 else "W"))
            return f"{d}°{m}'{s}\"{suffix}"
        return f"{to_dms(lat, True)} {to_dms(lon, False)}"
    except: return ""

def get_dist_bearing(lat1, lon1, lat2, lon2):
    if lat1 == 0.0 or lat2 == 0.0: return 9999, ""
    R = 6371
    dLat, dLon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    dist = R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))
    y = math.sin(math.radians(lon2-lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2-lon1))
    brng = (math.degrees(math.atan2(y, x)) + 360) % 360
    dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return round(dist, 1), f"{dirs[int((brng + 22.5) // 45 % 8)]} ({int(brng)}°)"

def generate_kml(df):
    kml_pts = ""
    for _, r in df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        desc = f"DTV: {r['SBS']},{r['KBS2']},{r['KBS1']},{r['EBS']},{r['MBC']} | UHD: {r['SBS(U)']},{r['KBS2(U)']},{r['KBS1(U)']},{r['EBS(U)']},{r['MBC(U)']}"
        kml_pts += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><description>{desc}</description><Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{kml_pts}</Document></kml>'

# ☁️ 데이터 로드 및 저장
def load_db(use_gsheets):
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).fillna("")
            df['이름'] = df['이름'].astype(str).str.strip()
            return df
        except: st.error("구글 시트 로드 실패. 설정을 확인하세요.")
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        df['이름'] = df['이름'].str.strip()
        return df
    except: 
        cols = ['지역', '구분', '이름', 'SBS', 'KBS2', 'KBS1', 'EBS', 'MBC', 'SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)', '위도', '경도', '주소']
        return pd.DataFrame(columns=cols, dtype=str)

def save_db(df, use_gsheets):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df)
            st.toast("☁️ 클라우드 동기화 완료!")
        except Exception as e: st.error(f"구글 시트 저장 실패: {e}")

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# 세션 상태 초기화
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 300000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'ref_loc': None, 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': [], 'use_gsheets': False,
    'ant_h': 10, 'show_los': False, 'los_target': "" 
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

if 'df' not in sd: sd.df = load_db(sd.use_gsheets)

# 표 선택 이벤트
if 'main_table' in sd:
    curr_sel = sd.main_table.get("selection", {}).get("rows", [])
    if curr_sel != sd.prev_sel:
        sd.prev_sel = curr_sel
        if curr_sel:
            idx = curr_sel[0]
            temp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
            if sd.ch_search: temp_df = temp_df[temp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]
            if sd.ref_loc: 
                temp_df['거리'] = temp_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
                temp_df = temp_df.sort_values('거리')
            if idx < len(temp_df):
                sel = temp_df.iloc[idx]
                sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
                for s in SL: sd[f"ch_{s}"] = str(sel[s])
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), str(sel['주소'])
                sd.base_center = [sd.in_t_la, sd.in_t_lo]; sd.show_los = False 
        else: sd.target_nm, sd.m_mode, sd.show_los = None, "신규 등록", False
        sd.map_key += 1; st.rerun()

# ---------------------------------------------------------
# 사이드바 (필터 및 입력)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 설정")
    new_gs = st.toggle("☁️ 구글 시트 동기화", value=sd.use_gsheets)
    if new_gs != sd.use_gsheets:
        sd.use_gsheets = new_gs; sd.df = load_db(new_gs); st.rerun()
    
    st.divider()
    sd.sel_reg = st.selectbox("📍 관제 지역", ["전체"] + sorted(list(sd.df['지역'].unique())))
    sd.map_layer = st.radio("🗺️ 지도 레이어", ["일반", "위성", "위성+이름"], horizontal=True)
    sd.ch_search = st.text_input("🔍 채널 검색 (예: 14)", value=sd.ch_search)
    
    st.divider()
    st.subheader(f"🛠️ {sd.m_mode}")
    sd.in_v_nm = st.text_input("시설 이름", value=sd.target_nm if sd.target_nm else "")
    sd.in_reg_direct = st.text_input("지역 (직접입력)", value=sd.in_reg_direct if sd.target_nm else sd.sel_reg)
    sd.in_v_cat = st.selectbox("구분", ["송신소", "중계소", "간이중계소"], index=0)
    
    col1, col2 = st.columns(2)
    with col1: st.write("**📡 DTV**"); [st.text_input(s, key=f"ch_{s}") for s in SL_DTV]
    with col2: st.write("**📺 UHD**"); [st.text_input(s, key=f"ch_{s}") for s in SL_UHD]
    
    sd.in_t_la = st.number_input("위도", value=sd.in_t_la, format="%.6f")
    sd.in_t_lo = st.number_input("경도", value=sd.in_t_lo, format="%.6f")
    sd.in_v_addr = st.text_area("주소", value=sd.in_v_addr)
    
    if st.button("🎯 지도 중심 좌표 가져오기", width='stretch'):
        if 'crosshair_center' in sd:
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center
            geolocator = Nominatim(user_agent="geo_app")
            try:
                location = geolocator.reverse(f"{sd.in_t_la}, {sd.in_t_lo}", timeout=3)
                if location: sd.in_v_addr = location.address
            except: pass
            st.rerun()

    btn_txt = "💾 수정 내용 저장" if sd.m_mode == "정보 수정" else "✅ 신규 등록 저장"
    if st.button(btn_txt, type="primary", width='stretch'):
        new_row = {
            '지역': sd.in_reg_direct, '구분': sd.in_v_cat, '이름': sd.in_v_nm,
            '위도': str(sd.in_t_la), '경도': str(sd.in_t_lo), '주소': sd.in_v_addr
        }
        for s in SL: new_row[s] = sd[f"ch_{s}"]
        
        if sd.m_mode == "정보 수정":
            sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = pd.Series(new_row)
        else:
            sd.df = pd.concat([sd.df, pd.DataFrame([new_row])], ignore_index=True)
        
        save_db(sd.df, sd.use_gsheets); st.rerun()

# ---------------------------------------------------------
# 본문: 지도 및 데이터
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 관제 인프라")

# 필터링
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search:
    disp_df = disp_df[disp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

# 거리 계산
if sd.ref_loc:
    disp_df['거리(km)'] = disp_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
    disp_df = disp_df.sort_values('거리(km)')

# 지도 생성
with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    # 내 위치 마커
    if sd.ref_loc:
        folium.Marker(sd.ref_loc, icon=folium.Icon(color='red', icon='home'), popup="현재 측정 위치").add_to(m)
        folium.Circle(sd.ref_loc, radius=10000, color='red', fill=True, opacity=0.1).add_to(m)

    # 시설 마커
    for _, r in disp_df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        color = 'blue' if r['구분'] == '송신소' else 'green'
        dist_info = f"<br>📏 거리: {r['거리(km)']}km" if sd.ref_loc else ""
        popup_html = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {r['SBS']},{r['KBS2']},{r['KBS1']},{r['MBC']}{dist_info}"
        folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=folium.Popup(popup_html, max_width=300)).add_to(m)

    map_data = st_folium(m, width='stretch', height=700, key=f"map_{sd.map_key}")
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# 데이터 표
st.subheader("📊 데이터 현황")
if not disp_df.empty:
    cfg = {s: st.column_config.TextColumn(width="small") for s in SL}
    st.dataframe(disp_df, width='content', on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table", column_config=cfg)

# KML 다운로드
if st.button("📥 현재 리스트 KML 다운로드"):
    st.download_button("파일 받기", generate_kml(disp_df), "map_export.kml", "text/xml")
