import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import math
import numpy as np
from branca.element import Template, MacroElement

# 1. 페이지 설정 (디자인 및 레이아웃)
st.set_page_config(page_title="Broadcasting Master v966", layout="wide")
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

# [데이터 로드 및 저장: 로컬 전용]
def load_db():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        df['이름'] = df['이름'].str.strip()
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    st.toast("💾 로컬 stations.csv에 저장되었습니다!")

# 세션 상태 초기화
if 'df' not in sd: sd.df = load_db()
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 260000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'ref_loc': None, 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': [],
    'ant_h': 10, 'show_los': False, 'los_target': "" 
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# 표 선택 이벤트 (v940 로직 반영)
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

# CSS 스타일 (v940 버튼 색상 유지)
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 18px !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; border-radius: 10px !important; border: 2px solid #adb5bd !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    div.element-container:has(.btn-delete-final) + div.element-container button { background-color: #d32f2f !important; color: white !important; font-weight: bold !important; }
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 설정 (로컬 전용)")
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    
    st.header("🔍 기준점 (내 위치)")
    s_addr = st.text_input("주소/좌표 검색")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색") and s_addr:
            try:
                if ',' in s_addr: lat, lon = map(float, s_addr.split(',')); sd.base_center, sd.ref_loc = [lat, lon], [lat, lon]
                else:
                    loc = Nominatim(user_agent="b_v966").geocode(s_addr)
                    if loc: sd.base_center, sd.ref_loc = [loc.latitude, loc.longitude], [loc.latitude, loc.longitude]
                sd.map_key += 1; st.rerun()
            except: st.error("검색 실패")
    with c2:
        if st.button("↩️ 복구"):
            if sd.history: sd.df = sd.history.pop(); save_db(sd.df); st.rerun()
    if st.button("🧭 내 위치 (GPS)"):
        gps = get_geolocation()
        if gps: p = [gps['coords']['latitude'], gps['coords']['longitude']]; sd.base_center, sd.ref_loc = p, p; sd.map_key += 1; st.rerun()
    
    st.subheader("📋 정보 원클릭 복사")
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)
    st.code(sd.in_v_addr if sd.in_v_addr else "위치를 지정하세요", language=None)

    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 주파수 역검색", value=sd.ch_search)

    st.divider()
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치"):
        sd.m_mode, sd.target_nm = "신규 등록", None; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치"):
        sd.m_mode = "정보 수정"; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 저장"):
        f_nm, f_reg = sd.get('in_v_nm', ""), sd.get('in_reg_direct', "") if (sd.m_mode == "정보 수정" or sd.get('in_reg_box') == "+ 직접 입력") else sd.get('in_reg_box')
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v; sd.target_nm = f_nm
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.selectbox("지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("새 지역 명칭", key="in_reg_direct")
        st.text_input("시설 이름", key="in_v_nm"); st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 확인", key="in_v_addr")
    
    elif sd.m_mode == "정보 수정":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            sel_target = st.selectbox("수정 대상", curr_names, index=(curr_names.index(sd.target_nm) if sd.target_nm in curr_names else 0))
            if sd.target_nm != sel_target:
                sd.target_nm = sel_target
                row = sd.df[sd.df['이름'] == sel_target].iloc[0]
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = row['이름'], row['지역'], row['구분']
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(row['위도']), safe_float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.base_center = [sd.in_t_la, sd.in_t_lo]; sd.map_key += 1; st.rerun()
            st.text_input("시설명 수정", key="in_v_nm"); st.text_input("지역 수정", key="in_reg_direct") 
            st.radio("구분 수정", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 수정", key="in_v_addr")
            
    elif sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            st.markdown('<span class="btn-delete-final"></span>', unsafe_allow_html=True)
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
# 본문: 지도 및 가시권 분석
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search: disp_df = disp_df[disp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

if sd.ref_loc:
    disp_df['거리(km)'] = disp_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
    disp_df = disp_df.sort_values('거리(km)')

with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    # 조준경 추가
    cross_html = MacroElement()
    cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }.map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }</style><div class="map-crosshair"></div>{% endmacro %}""")
    m.get_root().add_child(cross_html)
    
    if sd.ref_loc: folium.Marker(sd.ref_loc, icon=folium.Icon(color='green', icon='home', prefix='fa'), popup="기준점").add_to(m)

    for _, r in disp_df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        color = 'red' if r['구분'] == '송신소' else 'blue'
        p_html = f"<b>{r['이름']}</b><br>{r['주소']}<br>DTV: {r['SBS']},{r['KBS2']}"
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=300)).add_to(m)
    
    map_data = st_folium(m, width='stretch', height=700, key=f"map_{sd.map_key}")
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# 🏔️ 가시권 시뮬레이터 (v940 복원)
if sd.target_nm and sd.ref_loc:
    st.divider()
    st.subheader(f"🏔️ 가시권(LoS) 분석: {sd.target_nm}")
    col_a, col_b = st.columns([3, 1])
    with col_a: temp_ant = st.number_input("🏠 수신 안테나 높이 (m)", min_value=0, value=sd.ant_h, step=5)
    with col_b:
        st.write("") # 간격 맞춤
        if st.button("📊 계산 실행", width='stretch'):
            sd.ant_h = temp_ant; sd.show_los = True; sd.los_target = sd.target_nm
    if sd.show_los and sd.los_target == sd.target_nm:
        x = np.linspace(0, 10, 50); terrain = 100 * np.sin(x) + 50 # 예시 지형
        st.area_chart(pd.DataFrame({"지형": terrain, "가시선": np.linspace(500, 50+sd.ant_h, 50)}))

# 📊 데이터 표 및 다운로드
st.subheader("📊 데이터 현황")
if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    
    def style_row(row):
        bg = '#fff0f0' if row['구분']=='송신소' else '#f0f7ff'
        return [f"background-color: {bg}; font-weight: bold; font-size: 24px;" for _ in row]

    styled = view_df[CL + ['구글어스 좌표']].style.apply(style_row, axis=1)
    st.dataframe(styled, width='stretch', on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

    st.divider()
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        # 🔥 전문가님이 원하신 CSV 다운로드 버튼
        csv = disp_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📥 현재 리스트 CSV 다운로드", data=csv, file_name=f"broadcast_{sd.sel_reg}.csv", mime='text/csv', width='stretch')
    with c_d2:
        # 🔥 KML 다운로드 버튼
        st.download_button("🌍 현재 리스트 KML 다운로드", data=generate_kml(disp_df), file_name='stations.kml', mime='application/vnd.google-earth.kml+xml', width='stretch')
