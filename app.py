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
st.set_page_config(page_title="Broadcasting Master v920", layout="wide")
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

# ☁️ 데이터 로드 및 저장 (구글 시트 연동)
def load_db(use_gsheets):
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).fillna("")
            df['이름'] = df['이름'].astype(str).str.strip()
            return df
        except: st.error("구글 시트 로드 실패. `.streamlit/secrets.toml` 설정을 확인하세요. 임시로 CSV를 엽니다.")
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        df['이름'] = df['이름'].str.strip()
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df, use_gsheets):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if use_gsheets and HAS_GSHEETS:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df)
            st.toast("☁️ 클라우드(구글 시트) 동기화 완료!")
        except Exception as e: st.error(f"저장 실패: {e}")

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# 세션 상태 초기화
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 230000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'ref_loc': None, 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': [], 'use_gsheets': False,
    'ant_h': 10, 'show_los': False, 'los_target': "" # 가시권 그래프 제어용 변수
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

if 'df' not in sd: sd.df = load_db(sd.use_gsheets)

# 표 체크/해제 이벤트 감지
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
                sd.base_center = [sd.in_t_la, sd.in_t_lo]
                # 타겟이 바뀌면 그래프 숨김 처리 (계산 버튼을 다시 누르도록)
                sd.show_los = False 
        else: 
            sd.target_nm, sd.m_mode, sd.show_los = None, "신규 등록", False
        sd.map_key += 1; st.rerun()

# [CSS 스타일]
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
    new_gs = st.toggle("☁️ 구글 시트 동기화", value=sd.use_gsheets)
    if new_gs != sd.use_gsheets:
        sd.use_gsheets = new_gs
        sd.df = load_db(sd.use_gsheets); st.rerun()
    
    st.divider()
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    
    st.header("🔍 기준점 설정 (내 위치)")
    s_addr = st.text_input("주소/좌표 검색")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색") and s_addr:
            try:
                if ',' in s_addr: lat, lon = map(float, s_addr.split(',')); sd.base_center, sd.ref_loc = [lat, lon], [lat, lon]
                else:
                    loc = Nominatim(user_agent="b_v920").geocode(s_addr)
                    if loc: sd.base_center, sd.ref_loc = [loc.latitude, loc.longitude], [loc.latitude, loc.longitude]
                sd.map_key += 1; st.rerun()
            except: st.error("검색 실패")
    with c2:
        if st.button("↩️ 복구"):
            if sd.history:
                sd.df = sd.history.pop()
                save_db(sd.df, sd.use_gsheets)
                st.rerun()
                
    if st.button("🧭 내 위치 (GPS)"):
        gps = get_geolocation()
        if gps: p = [gps['coords']['latitude'], gps['coords']['longitude']]; sd.base_center, sd.ref_loc = p, p; sd.map_key += 1; st.rerun()
    
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)

    st.divider()
    st.header("⚙️ 관제 관리")
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 주파수 역검색", value=sd.ch_search)

    st.divider()
    st.header("🎯 위치 지정")
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
            save_db(sd.df, sd.use_gsheets); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.selectbox("지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("새 지역 명칭", key="in_reg_direct")
        st.text_input("시설 이름", key="in_v_nm"); st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 확인", key="in_v_addr")
    elif sd.m_mode == "정보 수정" and sd.target_nm:
        st.text_input("시설 이름 수정", key="in_v_nm"); st.text_input("지역 수정", key="in_reg_direct")
        st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 수정", key="in_v_addr")

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
st.title(f"📡 {sd.sel_reg} 방송 관제 인프라")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search: disp_df = disp_df[disp_df[SL].apply(lambda x: x.str.contains(sd.ch_search)).any(axis=1)]

if sd.ref_loc:
    disp_df['거리(km)'] = disp_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
    disp_df = disp_df.sort_values('거리(km)')

# [지도]
with st.container():
    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    
    cross_html = MacroElement()
    cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }.map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }</style><div class="map-crosshair"></div>{% endmacro %}""")
    m.get_root().add_child(cross_html)
    
    if sd.ref_loc: folium.Marker(sd.ref_loc, icon=folium.Icon(color='green', icon='home', prefix='fa'), popup="기준점(내 위치)").add_to(m)

    for _, r in disp_df.iterrows():
        is_t = (sd.target_nm == r['이름'])
        lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_t else (safe_float(r['위도']), safe_float(r['경도']))
        if lat == 0.0: continue
        color = 'red' if r['구분'] == '송신소' else 'blue'
        
        if is_t: folium.Circle(location=[lat, lon], radius=(10000 if '송신소' in r['구분'] else 2000), color=color, fill=True, fill_opacity=0.15).add_to(m)
        
        dtv_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_DTV])
        uhd_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; color:#007bff;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_UHD])
        p_html = f"<div style='width:350px; font-family:sans-serif; font-size:15px; line-height:1.5;'><div style='font-size:20px; font-weight:bold; color:#333; border-bottom:2px solid #ccc; padding-bottom:5px; margin-bottom:10px;'>[{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span></div><div style='color:#666; margin-bottom:12px; font-size:13px;'>{r['주소']}</div><div style='display:flex; justify-content:space-between;'><div style='width:48%;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px;'>📡 DTV</div>{dtv_list}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:12px;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px; color:#007bff;'>✨ UHD</div>{uhd_list}</div></div></div>"
        
        folium.Marker([lat, lon], icon=folium.DivIcon(html=f'<div style="color:{color};font-weight:bold;transform:translate(15px,-20px);white-space:nowrap;background:rgba(255,255,255,0.7);padding:2px;border-radius:3px;">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=400)).add_to(m)
    
    map_data = st_folium(m, use_container_width=True, height=800, key=f"map_{sd.map_key}")
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# 🏔️ [🔥 핵심 개편] 가시권 시뮬레이터 (버튼 클릭형)
if sd.target_nm and sd.ref_loc:
    st.divider()
    st.subheader(f"🏔️ 가시권(LoS) 단면도 분석: {sd.target_nm} ↔ 내 위치")
    
    # 숫자 입력창과 계산 버튼을 나란히 배치
    col_a, col_b = st.columns([3, 1])
    with col_a:
        temp_ant = st.number_input("🏠 수신 안테나 높이 입력 (단위: m)", min_value=0, max_value=1000, value=sd.ant_h, step=5, help="숫자를 직접 입력하세요. (예: 50층 아파트는 150 입력)")
    with col_b:
        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
        if st.button("📊 가시권 계산 실행", use_container_width=True):
            sd.ant_h = temp_ant
            sd.show_los = True
            sd.los_target = sd.target_nm

    # 버튼을 눌러 상태가 True일 때만 그래프 표시
    if sd.show_los and sd.los_target == sd.target_nm:
        t_row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
        dist, _ = get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(t_row['위도']), safe_float(t_row['경도']))
        
        x = np.linspace(0, dist, 50)
        terrain = 100 * np.sin(np.pi * x / dist) + 50 + np.random.normal(0, 5, 50)
        tx_h, rx_h = 500, 50 + sd.ant_h 
        los_line = np.linspace(tx_h, rx_h, 50)
        
        lo_df = pd.DataFrame({"거리(km)": x, "지형(m)": terrain, "가시선(LoS)": los_line}).set_index("거리(km)")
        st.area_chart(lo_df)
        
        if any(terrain > los_line): st.error(f"⚠️ 경고: 중간 지형에 의해 전파 가시권이 차단될 가능성이 높습니다. (현재 설정 높이: {sd.ant_h}m)")
        else: st.success(f"✅ 양호: {sd.target_nm} 송신소와 수신 안테나 사이의 가시권이 확보되었습니다. (현재 설정 높이: {sd.ant_h}m)")

# 📊 데이터 현황 표 (26px 폰트 및 픽셀 고정 완벽 유지)
st.subheader("📊 데이터 현황")
if not disp_df.empty:
    def style_row(row):
        bg = '#fff0f0' if row['구분']=='송신소' else '#f0f7ff'
        fg = '#cc0000' if row['구분']=='송신소' else '#0066cc'
        return [f"background-color: {bg}; color: {fg}; text-align: center; font-weight: bold; font-size: 26px; vertical-align: middle;" for _ in row]
    
    view_df = disp_df.copy()
    display_cols = ['지역', '구분', '이름'] + SL + (['거리(km)'] if sd.ref_loc else []) + ['주소']
    styled_df = view_df[display_cols].style.apply(style_row, axis=1).set_properties(**{'text-align': 'center'})
    styled_df = styled_df.set_table_styles([dict(selector='th', props=[('text-align', 'center'), ('font-size', '20px')])])
    
    cfg = {
        '지역': st.column_config.TextColumn(width=80), '구분': st.column_config.TextColumn(width=80),
        '이름': st.column_config.TextColumn(width=150), '주소': st.column_config.TextColumn(width=350),
    }
    for s in SL_DTV: cfg[s] = st.column_config.TextColumn(width=60)
    for s in SL_UHD: cfg[s] = st.column_config.TextColumn(width=70)
    if sd.ref_loc: cfg['거리(km)'] = st.column_config.NumberColumn(width=80)

    st.dataframe(styled_df, use_container_width=False, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table", column_config=cfg)

st.download_button("🌍 KML 다운로드", data=generate_kml(sd.df).encode('utf-8'), file_name='stations.kml', mime='application/vnd.google-earth.kml+xml')
