import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from branca.element import Template, MacroElement
from streamlit_gsheets import GSheetsConnection 
import time 

# 1. 페이지 설정 및 가로 꽉 참 설정
st.set_page_config(page_title="Broadcasting Master v984", layout="wide")

# CSS: 26px 폰트, 가로 꽉 참, 버튼 색상 완벽 보존
st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; max-width: 100% !important; }
    html, body, [class*="css"] { font-size: 18px !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; border-radius: 10px !important; border: 2px solid #adb5bd !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { font-size: 26px !important; height: 45px !important; }
</style>""", unsafe_allow_html=True)

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
        desc = f"DTV: {r['SBS']},{r['KBS2']},{r['KBS1']},{r['EBS']},{r['MBC']}"
        kml_pts += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><description>{desc}</description><Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{kml_pts}</Document></kml>'

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [데이터 로드/저장]
def load_db():
    df = pd.DataFrame(columns=CL, dtype=str)
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=GS_URL, ttl=0).astype(str).fillna("")
            for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True).replace('nan', '')
            st.toast("🌐 구글 시트 연동 성공!")
            return df
        except Exception as e: st.error(f"❌ 시트 로드 실패: {e}")
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True)
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=GS_URL, data=df)
            st.cache_data.clear() 
            st.sidebar.success("✅ 저장 완료!")
        except Exception as e: st.error(f"❌ 저장 실패: {e}")
    else: st.toast("💾 로컬 CSV 업데이트 완료!")

def get_filtered_sorted_df(df, sel_reg, search_query):
    res = df if sel_reg == "전체" else df[df['지역'] == sel_reg]
    if search_query:
        search_target = res['이름'] + " " + res['지역'] + " " + res['주소'] + " " + res[SL].apply(lambda x: ' '.join(x), axis=1)
        res = res[search_target.str.contains(search_query, case=False, na=False)]
    if not res.empty:
        sort_map = {'송신소': 1, '중계소': 2, '간이중계소': 3}
        res = res.copy()
        res['구분_순서'] = res['구분'].map(sort_map).fillna(4)
        res = res.sort_values(by=['지역', '구분_순서', '이름']).drop(columns=['구분_순서'])
    return res

# [세션 상태 초기화]
if 'df' not in sd: sd.df = load_db()
defaults = {
    'crosshair_center': [35.1796, 129.0756], 'base_center': [35.1796, 129.0756], 
    'base_zoom': 14, 'map_key': 8000, 'sel_reg': "전체", 'm_mode': "신규 등록", 
    'target_nm': None, 'in_v_nm': "", 'in_reg_box': "+ 새 지역 추가", 
    'in_reg_direct': "", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 
    'in_v_addr': "", 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': [], 'gs_sync_on': False
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# 🛠️ [원클릭 수정]: 표 선택 시 즉시 세션 상태를 갱신하도록 로직 순서 변경
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    if sd.prev_sel != [idx]:
        sd.prev_sel = [idx]
        temp_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
        if idx < len(temp_df):
            sel = temp_df.iloc[idx]
            sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            sd.in_v_addr, sd.in_t_la, sd.in_t_lo = str(sel['주소']), safe_float(sel['위도']), safe_float(sel['경도'])
            for s in SL: sd[f"ch_{s}"] = str(sel[s])
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1
            st.rerun()

with st.sidebar:
    st.header("⚙️ 관제 설정")
    sync_toggle = st.toggle("🌐 구글 시트 실시간 연동", value=sd.gs_sync_on)
    if sync_toggle != sd.gs_sync_on:
        sd.gs_sync_on = sync_toggle
        sd.df = load_db(); st.rerun()

    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 통합 검색", value=sd.ch_search)

    st.divider()
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치 추출"):
        p = sd.crosshair_center
        sd.m_mode, sd.target_nm = "신규 등록", None
        sd.in_t_la, sd.in_t_lo = p[0], p[1]
        try:
            loc = Nominatim(user_agent="b_v984").reverse(f"{p[0]}, {p[1]}", timeout=3)
            if loc: sd.in_v_addr = loc.address
        except: pass
        sd.map_key += 1; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치 추출"):
        if sd.target_nm:
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center[0], sd.crosshair_center[1]
            sd.map_key += 1 
            st.toast("🎯 마커가 조준경 위치로 이동되었습니다!"); st.rerun()

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 저장"):
        f_nm = sd.get('in_v_nm', "")
        f_reg = sd.get('in_reg_direct', "") if (sd.m_mode == "정보 수정" or sd.get('in_reg_box') == "+ 새 지역 추가") else sd.get('in_reg_box')
        if f_nm and f_reg:
            v = [f_reg, sd.get('in_v_cat', "송신소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: 
                sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
            else: 
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    st.divider(); st.markdown("### 📝 시설 정보 입력")
    if sd.m_mode == "신규 등록":
        reg_options = ["+ 새 지역 추가"] + regs
        st.selectbox("지역 선택", reg_options, key="in_reg_box")
        if sd.in_reg_box == "+ 새 지역 추가": st.text_input("새 지역 명칭 입력", key="in_reg_direct")
    else:
        st.text_input("지역 이름 수정", key="in_reg_direct")
    
    st.text_input("시설 이름", key="in_v_nm")
    st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
    st.text_area("주소 확인/수정", key="in_v_addr")
    
    # 🛠️ [원클릭 삭제]: 삭제 버튼 즉시 반응 로직
    if sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            if st.button("🚨 시설 삭제 실행"):
                sd.df = sd.df[sd.df['이름'] != del_t]
                save_db(sd.df); sd.target_nm = None; st.rerun()

    st.divider(); st.markdown("### 📡 물리 채널 설정")
    for section, icons, list_ch in [("DTV", "📡", SL_DTV), ("UHD", "✨", SL_UHD)]:
        st.write(f"{icons} {section}")
        cols = st.columns(3)
        for i, s in enumerate(list_ch):
            with cols[i % 3]: st.text_input(s, key=f"ch_{s}", label_visibility="collapsed")

# --- 메인 지도 (세로 850px 확장) ---
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")
disp_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)

l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
cross_html = MacroElement()
cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }.map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }</style><div class="map-crosshair"></div>{% endmacro %}""")
m.get_root().add_child(cross_html)

for _, r in disp_df.iterrows():
    is_t = (sd.target_nm == r['이름'])
    lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_t else (safe_float(r['위도']), safe_float(r['경도']))
    if lat == 0.0: continue
    color = 'red' if r['구분'] == '송신소' else 'blue'
    dtv_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>: {sd.get(f'ch_{s}', r[s]) if is_t else r[s]}</span></div>" for s in SL_DTV])
    uhd_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; color:#007bff;'><span><b>{s}</b></span><span>: {sd.get(f'ch_{s}', r[s]) if is_t else r[s]}</span></div>" for s in SL_UHD])
    p_html = f"<div style='width:350px; font-size:15px;'><div style='font-size:20px; font-weight:bold; color:#333; border-bottom:2px solid #ccc; padding-bottom:5px; margin-bottom:10px;'>[{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span></div><div>{r['주소']}</div><div style='display:flex; justify-content:space-between;'><div style='width:48%;'><b>📡 DTV</b>{dtv_list}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:12px; color:#007bff;'><b>✨ UHD</b>{uhd_list}</div></div></div>"
    folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=folium.Popup(p_html, max_width=400)).add_to(m)

map_data = st_folium(m, use_container_width=True, height=850, key=f"map_{sd.map_key}")
if map_data and map_data.get("center"):
    sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# --- 데이터 현황 및 다운로드 ---
st.subheader("📊 데이터 현황")
if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    styled = view_df[CL + ['구글어스 좌표']].style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'}; color: {'#cc0000' if row['구분']=='송신소' else '#0066cc'}; font-weight: bold; font-size: 26px; border-bottom: 1px solid #ccc;" for _ in row], axis=1)
    st.dataframe(styled, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

    st.divider()
    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 CSV 저장", data=disp_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations.csv", use_container_width=True)
    with c2: st.download_button("🌍 KML 저장", data=generate_kml(disp_df), file_name='stations.kml', use_container_width=True)
