import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
from streamlit_gsheets import GSheetsConnection
from branca.element import Template, MacroElement
import time

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v989", layout="wide")
DB = 'stations.csv'
GS_URL = st.secrets.get("gsheets_url", "")

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

# [데이터 로드 로직]
def load_db():
    df = pd.DataFrame(columns=CL, dtype=str)
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            # ttl=0 설정으로 캐시 없이 실시간 데이터를 강제 로드합니다.
            df = conn.read(spreadsheet=GS_URL, ttl=0).astype(str).fillna("")
            if not df.empty:
                msg = st.sidebar.empty()
                msg.success("🌐 구글 시트 연동 성공!")
                time.sleep(3) # 요청하신 3초 유지
                msg.empty()
                return df[CL]
        except: pass
    
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        return df.reindex(columns=CL, fill_value="")
    except:
        return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=GS_URL, data=df)
            msg = st.sidebar.empty()
            msg.success("✅ 구글 시트 저장 완료!")
            time.sleep(3)
            msg.empty()
        except: st.error("구글 시트 저장 실패")

# [필터링 및 세션 초기화]
def get_filtered_df(df, reg, q):
    if df.empty: return df
    res = df if reg == "전체" else df[df['지역'] == reg]
    if q:
        target = res['이름'] + " " + res['지역'] + " " + res['주소']
        res = res[target.str.contains(q, case=False, na=False)]
    return res

defaults = {
    'base_center': [35.1796, 129.0756], 'map_key': 9000, 'gs_sync_on': False,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'table_font_size': 26,
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'crosshair_center': [35.1796, 129.0756]
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
if 'df' not in sd: sd.df = load_db()

# CSS 스타일 (26px 폰트 및 버튼 균등 배치)
st.markdown(f"""<style>
    [data-testid="stSidebar"] {{ background-color: #ced4da !important; }}
    [data-testid="stSidebar"] div.stButton button {{ width: 100% !important; height: 50px !important; font-weight: bold !important; }}
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {{ font-size: {sd.table_font_size}px !important; }}
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 설정")
    old_sync = sd.gs_sync_on
    sd.gs_sync_on = st.toggle("🌐 구글 시트 실시간 연동", value=sd.gs_sync_on)
    if old_sync != sd.gs_sync_on:
        sd.df = load_db()
        st.rerun()

    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    q = st.text_input("🔎 통합 검색", key="ch_search")
    sd.table_font_size = st.slider("📊 표 글자 크기", 10, 50, sd.table_font_size)

    st.divider()
    st.subheader("🔍 위치 제어")
    c_loc = st.columns([1, 1, 1], gap="small")
    with c_loc[0]:
        if st.button("🎯신규"):
            sd.m_mode, p = "신규 등록", sd.crosshair_center
            sd.in_t_la, sd.in_t_lo = p[0], p[1]
            try:
                loc = Nominatim(user_agent="b_v989").reverse(f"{p[0]}, {p[1]}", timeout=3)
                if loc: sd.in_v_addr = loc.address
            except: pass
            sd.map_key += 1; st.rerun()
    with c_loc[1]:
        if st.button("🎯수정"):
            p = sd.crosshair_center
            sd.in_t_la, sd.in_t_lo = p[0], p[1]
            try:
                loc = Nominatim(user_agent="b_v989").reverse(f"{p[0]}, {p[1]}", timeout=3)
                if loc: sd.in_v_addr = loc.address
            except: pass
            sd.map_key += 1; st.toast("위치 추출 완료"); st.rerun()
    with c_loc[2]:
        if st.button("↩️복구"):
            if sd.history: sd.df = sd.history.pop(); save_db(sd.df); st.rerun()

    st.divider()
    st.subheader("📋 정보 원클릭 복사")
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)
    st.code(sd.v_addr if sd.get('v_addr') else "주소를 입력하세요", language=None)

    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], horizontal=True)

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.subheader("📝 시설 정보 입력")
        reg_opt = ["+ 새 지역 추가"] + regs
        sel_reg = st.selectbox("1. 지역 선택", reg_opt)
        f_reg = st.text_input("📝 새 지역 명칭", key="in_reg_direct") if sel_reg == "+ 새 지역 추가" else sel_reg
        f_nm = st.text_input("2. 시설 이름", key="in_v_nm")
        f_cat = st.radio("3. 시설 구분", ["송신소", "중계소"], horizontal=True)
        sd.v_addr = st.text_area("4. 주소 등록", value=sd.in_v_addr)

        st.info("📺 물리 채널 설정")
        for section, list_ch in [("📡 DTV", SL_DTV), ("✨ UHD", SL_UHD)]:
            st.markdown(f"**{section}**")
            cols = st.columns(3)
            for i, s in enumerate(list_ch):
                cols[i % 3].text_input(s, key=f"ch_{s}")

        if st.button("✅ 데이터 저장"):
            if f_nm and f_reg:
                sd.history.append(sd.df.copy())
                v = [f_reg, f_cat, f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.v_addr]
                if sd.m_mode == "정보 수정" and sd.get('target_nm'):
                    sd.df.loc[sd.df['이름'] == sd.target_nm] = v
                else:
                    sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                save_db(sd.df); st.rerun()

# ---------------------------------------------------------
# 본문: 지도 및 데이터 현황
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")
disp_df = get_filtered_df(sd.df, sd.sel_reg, sd.get('ch_search', ""))

m = folium.Map(location=sd.base_center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
cross_html = MacroElement()
cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }.map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }</style><div class="map-crosshair"></div>{% endmacro %}""")
m.get_root().add_child(cross_html)

for _, r in disp_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat != 0:
        folium.Marker([lat, lon], icon=folium.Icon(color='red' if r['구분'] == '송신소' else 'blue', icon='tower-broadcast', prefix='fa'), popup=r['이름']).add_to(m)

map_data = st_folium(m, use_container_width=True, height=700, key=f"map_{sd.map_key}")
if map_data and map_data.get("center"):
    sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

st.subheader("📊 데이터 현황")
if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    event = st.dataframe(view_df[CL + ['구글어스 좌표']], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")
    
    if event and event.get("selection", {}).get("rows"):
        idx = event["selection"]["rows"][0]
        sel = disp_df.iloc[idx]
        sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
        sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), str(sel['주소'])
        sd.base_center = [sd.in_t_la, sd.in_t_lo]
        for s in SL: sd[f"ch_{s}"] = str(sel[s])
        sd.map_key += 1; st.rerun()

    c1, c2 = st.columns(2)
    c1.download_button("📥 CSV 다운로드", data=disp_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations.csv", use_container_width=True)
    c2.download_button("🌍 KML 다운로드", data=generate_kml(disp_df), file_name='stations.kml', use_container_width=True)
