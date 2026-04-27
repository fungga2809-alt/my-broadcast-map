import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
from streamlit_gsheets import GSheetsConnection
from branca.element import Template, MacroElement

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v986", layout="wide")
DB = 'stations.csv'
GS_URL = st.secrets.get("gsheets_url", "") # secrets.toml에 설정된 URL 사용

sd = st.session_state

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

def generate_kml(df):
    kml_pts = ""
    for _, r in df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        desc = f"DTV: {r['SBS']},{r['KBS2']},{r['KBS1']},{r['EBS']},{r['MBC']} | UHD: {r['SBS(U)']},{r['KBS2(U)']},{r['KBS1(U)']},{r['EBS(U)']},{r['MBC(U)']}"
        kml_pts += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><description>{desc}</description><Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{kml_pts}</Document></kml>'

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [데이터 로드/저장 로직 - ON/OFF 스위치 연동]
def load_db():
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=GS_URL, ttl="1m")
            st.toast("🌐 구글 시트에서 최신 데이터를 가져왔습니다.")
            return df.astype(str).fillna("")
        except Exception as e:
            st.warning(f"구글 시트 로드 실패, 로컬 데이터를 사용합니다. ({e})")
    
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        st.toast("💾 로컬 stations.csv 데이터를 사용합니다.")
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    # 1. 로컬 저장 (언제나 수행)
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    
    # 2. 구글 시트 저장 (스위치 ON일 때만 수행)
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=GS_URL, data=df)
            st.toast("✅ 구글 시트 동기화 완료!")
        except Exception as e:
            st.error(f"구글 시트 업데이트 실패: {e}")
    else:
        st.toast("💾 로컬 파일에만 저장되었습니다.")

# [세션 상태 초기화]
if 'df' not in sd: sd.df = load_db()
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 6000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_v_nm': "", 'in_reg_box': "+ 새 지역 추가", 'in_reg_direct': "", 'in_v_cat': "송신소", 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "",
    'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': [], 'history': [],
    'crosshair_center': [35.1796, 129.0756], 'table_font_size': 26,
    'gs_sync_on': False  # 구글 시트 연동 초기값: OFF
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

# ---------------------------------------------------------
# 사이드바 (ON/OFF 스위치 배치)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 설정")
    
    # 🔥 구글 시트 연동 ON/OFF 스위치
    old_sync = sd.gs_sync_on
    sd.gs_sync_on = st.toggle("🌐 구글 시트 실시간 연동", value=sd.gs_sync_on)
    if old_sync != sd.gs_sync_on:
        sd.df = load_db() # 상태가 바뀌면 데이터를 다시 로드
        st.rerun()

    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    
    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 통합 검색", value=sd.ch_search)
    sd.table_font_size = st.slider("📊 표 글자 크기 (px)", 10, 40, sd.table_font_size)

    st.divider()
    # 버튼 스타일 및 기능 (v984/v985와 동일)
    st.markdown('<style>div.stButton > button:first-child { width:100%; height:50px; }</style>', unsafe_allow_html=True)
    
    if st.button("🎯 신규 위치 추출"):
        p = sd.crosshair_center
        sd.in_t_la, sd.in_t_lo = p[0], p[1]
        try:
            loc = Nominatim(user_agent="b_v986").reverse(f"{p[0]}, {p[1]}", timeout=3)
            if loc: sd.in_v_addr = loc.address
        except: pass
        sd.map_key += 1; st.rerun()

    if st.button("✅ 데이터 저장"):
        f_nm = sd.get('in_v_nm', "")
        f_reg = sd.get('in_reg_direct', "") if (sd.m_mode == "정보 수정" or sd.get('in_reg_box') == "+ 새 지역 추가") else sd.get('in_reg_box')
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: 
                sd.df.loc[sd.df['이름'] == sd.target_nm] = v
            else: 
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); st.rerun()

    # (이하 작업 모드, 정보 입력 섹션 등 v985와 동일 구조 유지)
    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], index=["신규 등록", "정보 수정", "데이터 삭제"].index(sd.m_mode), horizontal=True)
    # ... (기존 코드와 동일하게 정보 입력창 구성)
