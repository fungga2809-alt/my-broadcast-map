import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import math
import numpy as np

# 1. 페이지 및 기본 설정
st.set_page_config(page_title="Broadcasting Master v951", layout="wide")
DB = 'stations.csv'
sd = st.session_state

# ☁️ 구글 시트 연결 라이브러리 체크
try:
    from streamlit_gsheets import GSheetsConnection
    HAS_GSHEETS = True
except:
    HAS_GSHEETS = False

# [공통 도구함]
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
def load_db(use_gsheets):
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).fillna("")
            return df
        except: st.error("구글 시트 연결 실패. secrets.toml 위치를 확인하세요.")
    try:
        return pd.read_csv(DB, dtype=str).fillna("")
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df, use_gsheets):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df)
            st.toast("☁️ 클라우드 동기화 완료!")
        except Exception as e: st.error(f"구글 시트 저장 실패: {e}")

# [세션 상태 초기화]
if 'df' not in sd: sd.df = load_db(False)
defaults = {
    'use_gsheets': False, 'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None,
    'in_v_nm': "", 'in_reg_direct': "부산", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "",
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 100, 'ch_search': "", 'ref_loc': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL: 
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# ---------------------------------------------------------
# 좌측 사이드바 (관제 목록창 및 입력)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 시스템")
    
    # 1. 구글 시트 토글
    gs_toggle = st.toggle("☁️ 구글 시트 동기화", value=sd.use_gsheets)
    if gs_toggle != sd.use_gsheets:
        sd.use_gsheets = gs_toggle
        sd.df = load_db(gs_toggle)
        st.rerun()

    st.divider()
    
    # 2. 필터 설정
    sd.sel_reg = st.selectbox("📍 관제 지역", ["전체"] + sorted(list(sd.df['지역'].unique())))
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], horizontal=True, index=2)
    sd.ch_search = st.text_input("🔍 채널 검색 (예: 14)", value=sd.ch_search)
    
    st.divider()

    # 3. 입력창 (신규/수정 공용)
    st.subheader(f"🛠️ {sd.m_mode}")
    
    # 수정 모드일 때 '신규 등록'으로 돌아가는 버튼
    if sd.m_mode == "정보 수정":
        if st.button("🆕 신규 등록으로 전환"):
            sd.m_mode, sd.target_nm = "신규 등록", None
            sd.in_v_nm, sd.in_v_addr = "", ""
            for s in SL: sd[f"ch_{s}"] = ""
            st.rerun()

    sd.in_v_nm = st.text_input("시설 이름", value=sd.in_v_nm)
    sd.in_reg_direct = st.text_input("지역 (직접입력)", value=sd.in_reg_direct)
    cat_list = ["송신소", "중계소", "간이중계소"]
    sd.in_v_cat = st.selectbox("구분", cat_list, index=cat_list.index(sd.in_v_cat) if sd.in_v_cat in cat_list else 0)
    
    # 채널 입력 (DTV / UHD)
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

    # 기능 버튼들
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
        
        save_db(sd.df, sd.use_gsheets)
        st.rerun()

# ---------------------------------------------------------
# 우측 본문 (지도 및 데이터 표)
# ---------------------------------------------------------
st.title(f"📡 방송 관제 센터 ({sd.sel_reg})")

# 데이터 필터링
view_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search:
    view_df = view_df[view_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

# 거리 계산 (현재 위치 기준)
if sd.ref_loc:
    view_df['거리(km)'] = view_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
    view_df = view_df.sort_values('거리(km)')

# 지도 표시
with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    for _, r in view_df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        color = 'blue' if r['구분'] == '송신소' else 'green'
        popup_txt = f"<b>{r['이름']}</b><br>DTV: {r['SBS']},{r['KBS2']},{r['KBS1']}"
        folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=popup_txt).add_to(m)

    map_res = st_folium(m, width='stretch', height=600, key=f"map_{sd.map_key}")
    if map_res and map_res.get("center"):
        sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# [중요] 데이터 표 및 선택 이벤트
st.subheader("📊 시설 목록 (표에서 선택 시 좌측창에 자동 입력)")
event = st.dataframe(
    view_df, 
    on_select="rerun", 
    selection_mode="single-row", 
    hide_index=True, 
    width='content',
    key="table_select"
)

# 표에서 선택했을 때 좌측 입력창으로 데이터 전달
if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    selected_row = view_df.iloc[idx]
    
    # 세션 상태 업데이트 (좌측창에 반영됨)
    sd.m_mode = "정보 수정"
    sd.target_nm = selected_row['이름']
    sd.in_v_nm = selected_row['이름']
    sd.in_reg_direct = selected_row['지역']
    sd.in_v_cat = selected_row['구분']
    sd.in_t_la = safe_float(selected_row['위도'])
    sd.in_t_lo = safe_float(selected_row['경도'])
    sd.in_v_addr = selected_row['주소']
    for s in SL: sd[f"ch_{s}"] = str(selected_row[s])
    
    # 지도 중심 이동
    sd.base_center = [sd.in_t_la, sd.in_t_lo]
    st.rerun()
