import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import math
import numpy as np

# 1. 페이지 및 기본 설정
st.set_page_config(page_title="Broadcasting Master v960", layout="wide")
DB = 'stations.csv'
sd = st.session_state

# [도구함]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
    except: return default

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

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [데이터 로드/저장]
def load_db():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        df['이름'] = df['이름'].str.strip()
        return df
    except:
        return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    st.toast("💾 내 컴퓨터(stations.csv)에 저장 완료!")

# [세션 상태 초기화]
if 'df' not in sd: sd.df = load_db()
defaults = {
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None,
    'in_v_nm': "", 'in_reg_direct': "부산", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "",
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 100, 'ch_search': "", 'ref_loc': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL: 
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# ---------------------------------------------------------
# 좌측 사이드바 (관제 목록 및 입력)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 로컬 관제 설정")
    
    # 필터
    sd.sel_reg = st.selectbox("📍 관제 지역", ["전체"] + sorted(list(sd.df['지역'].unique())))
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], horizontal=True, index=2)
    sd.ch_search = st.text_input("🔍 채널 검색 (예: 14)", value=sd.ch_search)
    
    st.divider()

    # 입력창
    st.subheader(f"🛠️ {sd.m_mode}")
    
    if sd.m_mode == "정보 수정":
        if st.button("🆕 신규 등록 모드로 전환"):
            sd.m_mode, sd.target_nm = "신규 등록", None
            sd.in_v_nm, sd.in_v_addr = "", ""
            for s in SL: sd[f"ch_{s}"] = ""
            st.rerun()

    sd.in_v_nm = st.text_input("시설 이름", value=sd.in_v_nm)
    sd.in_reg_direct = st.text_input("지역 (직접입력)", value=sd.in_reg_direct)
    cat_list = ["송신소", "중계소", "간이중계소"]
    sd.in_v_cat = st.selectbox("구분", cat_list, index=cat_list.index(sd.in_v_cat) if sd.in_v_cat in cat_list else 0)
    
    c1, c2 = st.columns(2)
    with c1: 
        st.caption("📡 DTV")
        for s in SL_DTV: sd[f"ch_{s}"] = st.text_input(s, value=sd[f"ch_{s}"], key=f"inp_{s}")
    with c2: 
        st.caption("📺 UHD")
        for s in SL_UHD: sd[f"ch_{s}"] = st.text_input(s, value=sd[f"ch_{s}"], key=f"inp_{s}")

    sd.in_t_la = st.number_input("위도", value=sd.in_t_la, format="%.6f")
    sd.in_t_lo = st.number_input("경도", value=sd.in_t_lo, format="%.6f")
    sd.in_v_addr = st.text_area("주소", value=sd.in_v_addr)

    if st.button("🎯 지도 중심 좌표 가져오기", width='stretch'):
        if 'crosshair_center' in sd:
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center
            try:
                location = Nominatim(user_agent="geo").reverse(f"{sd.in_t_la}, {sd.in_t_lo}", timeout=3)
                if location: sd.in_v_addr = location.address
            except: pass
            st.rerun()

    save_btn_txt = "💾 수정 내용 저장" if sd.m_mode == "정보 수정" else "✅ 신규 등록 저장"
    if st.button(save_btn_txt, type="primary", width='stretch'):
        new_data = {
            '지역': sd.in_reg_direct, '구분': sd.in_v_cat, '이름': sd.in_v_nm,
            '위도': str(sd.in_t_la), '경도': str(sd.in_t_lo), '주소': sd.in_v_addr
        }
        for s in SL: new_data[s] = sd[f"ch_{s}"]
        
        if sd.m_mode == "정보 수정" and sd.target_nm:
            sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = pd.Series(new_data)
        else:
            sd.df = pd.concat([sd.df, pd.DataFrame([new_data])], ignore_index=True)
        
        save_db(sd.df)
        st.rerun()

# ---------------------------------------------------------
# 우측 본문 (지도 및 표)
# ---------------------------------------------------------
st.title(f"📡 방송 관제 센터 ({sd.sel_reg})")

# 필터링
view_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search:
    view_df = view_df[view_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

if sd.ref_loc:
    view_df['거리(km)'] = view_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
    view_df = view_df.sort_values('거리(km)')

with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    for _, r in view_df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        color = 'blue' if r['구분'] == '송신소' else 'green'
        folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=f"<b>{r['이름']}</b>").add_to(m)

    map_res = st_folium(m, width='stretch', height=600, key=f"map_{sd.map_key}")
    if map_res and map_res.get("center"):
        sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# 데이터 표 및 선택 이벤트
st.subheader("📊 시설 목록 (클릭 시 좌측 입력창에 자동 입력)")
event = st.dataframe(
    view_df, 
    on_select="rerun", 
    selection_mode="single-row", 
    hide_index=True, 
    width='content',
    key="table_select"
)

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel = view_df.iloc[idx]
    
    sd.m_mode, sd.target_nm = "정보 수정", sel['이름']
    sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
    sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), sel['주소']
    for s in SL: sd[f"ch_{s}"] = str(sel[s])
    sd.base_center = [sd.in_t_la, sd.in_t_lo]
    st.rerun()
