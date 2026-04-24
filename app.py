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
st.set_page_config(page_title="Broadcasting Master v970", layout="wide")
DB = 'stations.csv'
sd = st.session_state

# [도구함: 좌표 변환 및 거리 계산]
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
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    st.toast("💾 로컬 stations.csv 저장 완료!")

# 세션 상태 초기화
if 'df' not in sd: sd.df = load_db()
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 300000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_v_nm': "", 'in_reg_box': "+ 새 지역 추가", 'in_reg_direct': "", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "",
    'ref_loc': None, 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': []
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# 표 선택 이벤트
if 'main_table' in sd:
    curr_sel = sd.main_table.get("selection", {}).get("rows", [])
    if curr_sel != sd.prev_sel:
        sd.prev_sel = curr_sel
        if curr_sel:
            idx = curr_sel[0]
            temp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
            if sd.ch_search: temp_df = temp_df[temp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]
            if idx < len(temp_df):
                sel = temp_df.iloc[idx]
                sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
                sd.in_v_nm, sd.in_reg_box, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
                for s in SL: sd[f"ch_{s}"] = str(sel[s])
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), str(sel['주소'])
                sd.base_center = [sd.in_t_la, sd.in_t_lo]
        else: sd.target_nm, sd.m_mode = None, "신규 등록"
        sd.map_key += 1; st.rerun()

# CSS 스타일 (v940 버튼 색상 유지)
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 18px !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; border-radius: 10px !important; border: 2px solid #adb5bd !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 설정")
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    
    st.divider()
    # 지역 필터링
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 주파수 역검색", value=sd.ch_search)

    st.divider()
    # 위치 추출 버튼
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치 추출"):
        sd.m_mode, sd.target_nm = "신규 등록", None; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치 추출"):
        sd.m_mode = "정보 수정"; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    
    # 저장 버튼
    if st.button("✅ 데이터 저장"):
        f_nm = sd.get('in_v_nm', "")
        # 직접 입력 혹은 선택된 지역명 확정
        f_reg = sd.get('in_reg_direct', "") if sd.get('in_reg_box') == "+ 새 지역 추가" else sd.get('in_reg_box')
        
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: 
                sd.df.loc[sd.df['이름'] == sd.target_nm] = v
                sd.target_nm = f_nm
            else: 
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    # 시설 정보 입력 섹션 (지역 추가 기능 포함)
    st.markdown("### 📝 시설 정보 입력")
    reg_options = ["+ 새 지역 추가"] + regs
    # 수정 모드일 때는 해당 시설의 지역이 자동으로 선택되도록 함
    cur_reg_idx = reg_options.index(sd.in_reg_box) if sd.in_reg_box in reg_options else 0
    st.selectbox("지역 선택", reg_options, index=cur_reg_idx, key="in_reg_box")
    
    if sd.in_reg_box == "+ 새 지역 추가":
        st.text_input("새 지역 명칭 입력", key="in_reg_direct", placeholder="예: 양산, 거창")
    
    st.text_input("시설 이름", key="in_v_nm")
    st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
    st.text_area("주소 확인/수정", key="in_v_addr")
    
    if sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            if st.button("🚨 시설 삭제 실행"):
                sd.history.append(sd.df.copy()); sd.df = sd.df[sd.df['이름'] != del_t]
                save_db(sd.df); sd.target_nm = None; st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.markdown("### 📡 물리 채널 설정")
        for section, icons, list_ch in [("DTV", "📡", SL_DTV), ("UHD", "✨", SL_UHD)]:
            st.write(f"{icons} {section}")
            cols = st.columns(3)
            for i, s in enumerate(list_ch):
                with cols[i % 3]: st.text_input(s, key=f"ch_{s}", label_visibility="collapsed")

# ---------------------------------------------------------
# 본문: 지도 (세로 크기 1000으로 확대)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search: disp_df = disp_df[disp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    # 조준경(Crosshair)
    cross_html = MacroElement()
    cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }.map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }</style><div class="map-crosshair"></div>{% endmacro %}""")
    m.get_root().add_child(cross_html)
    
    for _, r in disp_df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        color = 'red' if r['구분'] == '송신소' else 'blue'
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa')).add_to(m)
    
    # 🔥 [중요 수정] 지도의 세로 크기를 1000으로 키웠습니다.
    map_data = st_folium(m, width='stretch', height=1000, key=f"map_{sd.map_key}")
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# ---------------------------------------------------------
# 📊 데이터 현황 표 (26px, 색상 적용)
# ---------------------------------------------------------
st.subheader("📊 데이터 현황")
if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    
    def style_row(row):
        bg = '#fff0f0' if row['구분']=='송신소' else '#f0f7ff'
        fg = '#cc0000' if row['구분']=='송신소' else '#0066cc'
        return [f"background-color: {bg}; color: {fg}; font-weight: bold; font-size: 26px;" for _ in row]

    styled = view_df[CL + ['구글어스 좌표']].style.apply(style_row, axis=1)
    st.dataframe(styled, width='stretch', on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

    st.divider()
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        csv = disp_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📥 현재 리스트 CSV 다운로드", data=csv, file_name=f"broadcast_{sd.sel_reg}.csv", mime='text/csv', width='stretch')
    with c_d2:
        st.download_button("🌍 현재 리스트 KML 다운로드", data=generate_kml(disp_df), file_name='stations.kml', mime='application/vnd.google-earth.kml+xml', width='stretch')
