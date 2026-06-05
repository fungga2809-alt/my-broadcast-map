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
st.set_page_config(page_title="Broadcasting Master v1026", layout="wide")

# [관제 대시보드 전용 CSS]
st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; max-width: 100% !important; }
    [data-testid="stSidebar"] { background-color: #f1f3f5 !important; border-right: 1px solid #dee2e6 !important; }
    [data-testid="stSidebar"] div.stButton button, [data-testid="stSidebar"] button[kind="secondaryFormSubmit"] { width: 100% !important; height: 42px !important; border-radius: 8px !important; font-weight: bold !important; }
    .analysis-box { background-color: #ffffff; border: 1px solid #ced4da; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #1971c2 !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2f9e44 !important; color: white !important; font-size: 18px !important; }
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

# [도구함]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
    except: return default

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

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
        <details style='cursor:pointer; background:#f0f7ff; padding:5px; border-radius:5px; margin-bottom:5px;'><summary style='font-weight:bold;'>📱 DMB 채널</summary><div style='margin-top:8px;'>{dmb_h if dmb_h else '제원 없음'}</div></details>
        <details style='cursor:pointer; background:#eee; padding:5px; border-radius:5px;'><summary style='font-weight:bold;'>📻 FM 라디오</summary><div style='margin-top:8px;'>{fm_h if fm_h else '제원 없음'}</div></details>
    </div>"""

# 초기화 변수들
defaults = {
    'gs_sync_on': True, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
    'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 270000,
    'm_mode': "정보 수정", 'target_nm': None, 'in_v_nm': "", 'in_reg_direct': "", 
    'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 
    'prev_sel': [], 'msg_save': False, 'msg_extract': False, 'map_jump_q': "",
    'temp_active': False, 'temp_lat': 0.0, 'temp_lon': 0.0,
    'show_coverage': False, 'cov_radius': 10, 'show_los': True 
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

def load_db():
    if sd.get('gs_sync_on', False):
        try:
            st.cache_data.clear() 
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).astype(str).fillna("")
            df.columns = [col.strip() for col in df.columns]
            for c in CL:
                if c not in df.columns: df[c] = ""
            return df[CL]
        except: pass
    try:
        df = pd.read_csv(DB, dtype=str, encoding='utf-8-sig').fillna("")
        for c in CL:
            if c not in df.columns: df[c] = ""
        return df[CL]
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df[CL].to_csv(DB, index=False, encoding='utf-8-sig') 
    if sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df[CL]); st.cache_data.clear()
        except: pass

def get_filtered_sorted_df(df, sel_reg, search_query):
    res = df if sel_reg == "전체" else df[df['지역'] == sel_reg]
    if search_query:
        search_target = res['이름'] + " " + res['지역'] + " " + res['주소'] + " " + res[SL].apply(lambda x: ' '.join(x), axis=1)
        res = res[search_target.str.contains(search_query, case=False, na=False)]
    if not res.empty:
        sort_map = {'송신소': 1, '중계소': 2}
        res = res.copy()
        res['구분_순서'] = res['구분'].map(sort_map).fillna(3)
        res = res.sort_values(by=['지역', '구분_순서', '이름']).drop(columns=['구분_순서'])
    return res

if 'df' not in sd: sd.df = load_db()

if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    if sd.prev_sel != [idx]:
        sd.prev_sel = [idx]
        temp_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
        if idx < len(temp_df):
            sel = temp_df.iloc[idx]
            sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
            sd.temp_active = False
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            sd.in_v_addr, sd.in_t_la, sd.in_t_lo = str(sel['주소']), safe_float(sel['위도']), safe_float(sel['경도'])
            for s in SL: sd[f"ch_{s}"] = str(sel[s]) if s in sel else ""
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 관제 및 분석")
    
    gs_toggle = st.toggle("🌐 클라우드 실시간 연동", value=sd.gs_sync_on)
    if gs_toggle != sd.gs_sync_on:
        sd.gs_sync_on = gs_toggle
        if sd.gs_sync_on: sd.df = load_db()
        st.rerun()

    sd.map_layer = st.radio("🗺️ 지도 레이어", ["일반", "위성", "위성+이름", "특수지형도"], index=["일반", "위성", "위성+이름", "특수지형도"].index(sd.map_layer), horizontal=True)
    c_tog, c_sld = st.columns([1, 1])
    with c_tog: sd.show_coverage = st.toggle("⭕ 예상 커버리지", value=sd.show_coverage)
    with c_sld: 
        if sd.show_coverage: sd.cov_radius = st.slider("반경 (km)", 1, 50, sd.cov_radius, label_visibility="collapsed")

    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 내 장부 통합 검색", placeholder="저장된 시설명, 채널 등")

    st.markdown("**🌍 원하는 위치로 지도 이동**")
    st.markdown("""<div style='background-color: #e7f5ff; border-left: 4px solid #228be6; padding: 12px; border-radius: 4px; color: #1864ab; font-size: 13px;'>💡 <b>Pro Tip:</b> 좌표(위도,경도)나 주소를 넣고 [엔터]를 치세요.</div>""", unsafe_allow_html=True)
    
    with st.form("jump_form", clear_on_submit=False):
        c_jmp, c_btn = st.columns([3, 1])
        with c_jmp: jump_q = st.text_input("공간 이동", value=sd.map_jump_q, placeholder="좌표 입력", label_visibility="collapsed")
        with c_btn: jump_submit = st.form_submit_button("이동", use_container_width=True)
        if jump_submit and jump_q:
            lat_lon = parse_coord_input(jump_q)
            if lat_lon[0] is not None:
                sd.base_center = [lat_lon[0], lat_lon[1]]; sd.crosshair_center = [lat_lon[0], lat_lon[1]]; sd.map_jump_q = jump_q; sd.map_key += 1; st.rerun()
            else:
                geolocator = Nominatim(user_agent="b_master"); loc = None
                try:
                    loc = geolocator.geocode(jump_q)
                    if not loc:
                        q_nospace = re.sub(r'([가-힣]+)\s+(\d+[가-힣]+)', r'\1\2', jump_q)
                        if q_nospace != jump_q: loc = geolocator.geocode(q_nospace)
                    if loc: sd.base_center = [loc.latitude, loc.longitude]; sd.crosshair_center = [loc.latitude, loc.longitude]; sd.map_jump_q = jump_q; sd.map_key += 1; st.rerun()
                    else: st.toast("검색 실패! 구글 좌표를 복사해서 넣어주세요.", icon="❌")
                except: st.toast("지도 네트워크 오류", icon="⚠️")

    st.divider()
    st.subheader("📝 시설 제원 관리")
    c_loc, c_rst = st.columns(2)
    with c_loc:
        if st.button("📍 내 위치 이동"): sd.map_key += 1; st.rerun() 
    with c_rst:
        if st.button("🔄 입력창 비우기"):
            sd.m_mode, sd.target_nm = "신규 등록", None; sd.in_v_nm, sd.in_reg_direct, sd.in_v_addr = "", "", ""; sd.temp_active = False; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 1. 조준경 위치 추출"):
        sd.in_t_la, sd.in_t_lo = sd.crosshair_center; sd.base_center = [sd.in_t_la, sd.in_t_lo]
        try:
            loc = Nominatim(user_agent="b_master").reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
            if loc: sd.in_v_addr = loc.address
        except: pass
        if sd.m_mode == "신규 등록": sd.temp_active = True; sd.temp_lat, sd.temp_lon = sd.crosshair_center; sd.msg_extract = True
        elif sd.m_mode == "정보 수정" and sd.target_nm:
            v = [sd.in_reg_direct, sd.in_v_cat, sd.target_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v; save_db(sd.df); sd.msg_extract = True
        sd.map_key += 1; st.rerun()
    
    if sd.msg_extract: st.info("🎯 위치 정보 업데이트 완료!"); sd.msg_extract = False

    t1, t2, t3, t4 = st.tabs(["2. 기본", "TV", "DMB", "FM"])
    with t1:
        st.radio("작업 모드", ["신규", "수정", "삭제"], key="m_mode_tab", horizontal=True, label_visibility="collapsed")
        sd.m_mode = {"신규": "신규 등록", "수정": "정보 수정", "삭제": "데이터 삭제"}[st.session_state.m_mode_tab]
        if sd.m_mode == "데이터 삭제":
            if st.button("🚨 시설 영구 삭제"):
                if sd.target_nm: sd.df = sd.df[sd.df['이름'] != sd.target_nm]; save_db(sd.df); sd.target_nm = None; st.rerun()
        st.text_input("지역", key="in_reg_direct"); st.text_input("시설명", key="in_v_nm"); st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소", key="in_v_addr", height=70)
    with t2:
        c1, c2 = st.columns(2)
        with c1: st.markdown("**📺 DTV**"); for s in SL_DTV: st.text_input(s, key=f"ch_{s}")
        with c2: st.markdown("**✨ UHD**"); for s in SL_UHD: st.text_input(s, key=f"ch_{s}")
    with t3: st.markdown("**📱 DMB**"); for s in SL_DMB: st.text_input(s, key=f"ch_{s}")
    with t4: st.markdown("**📻 FM 라디오**"); cols = st.columns(2); 
    for i, s in enumerate(SL_FM):
        with cols[i % 2]: st.text_input(s, key=f"ch_{s}")

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 3. 데이터 통합 저장"):
        f_nm, f_reg = sd.in_v_nm, sd.in_reg_direct
        if f_nm and f_reg:
            v = [f_reg, sd.in_v_cat, f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); sd.target_nm = f_nm; sd.msg_save = True; sd.prev_sel = []; sd.temp_active = False; st.rerun()

    st.divider()
    with st.expander("📡 RF 기술 분석 툴킷"):
        if sd.target_nm:
            st.markdown(f"**대상:** {sd.target_nm} ↔ **현장(조준경)**")
            dist_km = geodesic((sd.in_t_la, sd.in_t_lo), sd.crosshair_center).km
            bear = calculate_bearing(sd.in_t_la, sd.in_t_lo, sd.crosshair_center[0], sd.crosshair_center[1])
            c1, c2 = st.columns(2)
            c1.metric("직선 거리", f"{dist_km:.2f} km"); c2.metric("방위각", f"{bear:.1f}°")
            if dist_km > 0.1:
                fresnel_r = 17.32 * math.sqrt(dist_km / (4 * 0.5)); earth_bulge = (dist_km * dist_km) / 50.96 
                c3, c4 = st.columns(2); c3.caption(f"프레넬: {fresnel_r:.1f}m"); c4.caption(f"지구 곡률: {earth_bulge:.1f}m")
                dist_pts = [dist_km * i / 20 for i in range(21)]; bulge_pts = [(d1 * (dist_km - d1)) / 17.0 for d1 in dist_pts]
                st.area_chart(pd.DataFrame({'가림고(m)': bulge_pts}, index=dist_pts), color="#ced4da", height=150)
                sd.show_los = st.checkbox("지도에 LOS 라인 표시", value=sd.show_los)
        else: st.info("표에서 시설을 선택하세요.")
    with st.expander("🧮 채널-주파수 변환기"):
        ch_input = st.number_input("채널 번호 (14~69)", 14, 69, 14); st.success(f"CH {ch_input} ➜ **{473 + (ch_input-14)*6} MHz**")

# --- 메인 화면 ---
st.title(f"📡 {sd.sel_reg} 통합 방송 관제 시스템")
res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png' if sd.map_layer == "특수지형도" else f'https://mt1.google.com/vt/lyrs={{"일반":"m","위성":"s","위성+이름":"y"}}[sd.map_layer]&hl=ko&x={{x}}&y={{y}}&z={{z}}'), attr='Google/OpenTopoMap')
folium.plugins.LocateControl(auto_start=False).add_to(m)
m.get_root().add_child(Template("""{% macro html(this, kwargs) %}<style>.crosshair{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:40px;border:2px solid #ff4b4b;border-radius:50%;z-index:1000;pointer-events:none;}.crosshair::before,.crosshair::after{content:'';position:absolute;background:#ff4b4b;}.crosshair::before{top:18px;left:-10px;width:60px;height:4px;}.crosshair::after{left:18px;top:-10px;height:60px;width:4px;}</style><div class="crosshair"></div>{% endmacro %}"""))

for _, r in res_df.iterrows():
    lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if sd.target_nm == r['이름'] else (safe_float(r['위도']), safe_float(r['경도']))
    if lat == 0.0: continue
    if sd.target_nm == r['이름']:
        if sd.get('show_coverage'): folium.Circle([lat, lon], sd.cov_radius * 1000, color='#1864ab', fill=True).add_to(m)
        if sd.get('show_los') and geodesic((lat, lon), sd.crosshair_center).km > 0.1: folium.PolyLine([[lat, lon], sd.crosshair_center], color='red', weight=2.5, dash_array='5,5').add_to(m)
    folium.Marker([lat, lon], icon=folium.Icon(color='red' if r['구분'] == '송신소' else 'blue'), popup=folium.Popup(generate_popup_html(r), max_width=400)).add_to(m)

if sd.get('temp_active'): folium.Marker([sd.temp_lat, sd.temp_lon], icon=folium.Icon(color='lightgray', icon='info-sign'), popup="🚧 신규 등록 대기").add_to(m)
map_res = st_folium(m, use_container_width=True, height=850, key=f"map_{sd.map_key}")
if map_res and map_res.get("center"): sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

st.subheader("📊 전국 방송 시설 데이터 현황")
st.dataframe(res_df.style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'};" for _ in row], axis=1), use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")
