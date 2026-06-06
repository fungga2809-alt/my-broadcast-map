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

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v1034", layout="wide")

# 2. 전역 변수 및 CSS
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL_DMB = ['DMB(SBS)', 'DMB(KBS)', 'DMB(MBC)']
SL_FM = ['KBS1-FM', 'KBS2-FM', 'KBS-Music', 'MBC-FM', 'MBC-AM', 'KNN-FM', 'EBS-FM', '교통방송', '국악방송', '불교방송', '평화방송', '기독교방송']
# 🚩 [변경사항]: '커버리지' DB 컬럼 추가
SL = SL_DTV + SL_UHD + SL_DMB + SL_FM
CL = ['지역', '구분', '이름', '커버리지'] + SL + ['위도', '경도', '주소']

st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    [data-testid="stSidebar"] { background-color: #f1f3f5 !important; }
    .analysis-box { background-color: #ffffff; border: 1px solid #ced4da; padding: 10px; border-radius: 8px; margin-bottom: 10px; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #1971c2 !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2f9e44 !important; color: white !important; font-size: 16px !important; }
</style>""", unsafe_allow_html=True)

# 3. 함수 모음
def safe_float(val, default=0.0):
    try: return float(val) if pd.notnull(val) and str(val).strip() != "" else default
    except: return default

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

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
    cov_h = f"<br><span style='color:#e67700;'><b>⭕ 등록된 커버리지:</b> {r.get('커버리지', '')} km</span>" if r.get('커버리지', '') and safe_float(r.get('커버리지')) > 0 else ""
    return f"""<div style='width:350px; font-size:14px;'>
        <div style='font-size:16px; font-weight:bold;'>[{r.get('구분','')}] {r.get('이름','')}</div>
        <div style='color:#555;'>{r.get('주소','')}{cov_h}</div>
        <hr style='margin: 8px 0;'>
        <div style='display:flex; justify-content:space-between;'><div style='width:48%;'><b>📡 DTV</b>{dtv_h}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:10px;'><b>✨ UHD</b>{uhd_h}</div></div>
    </div>"""

def load_db():
    if st.session_state.sd.get('gs_sync_on', False):
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
            if c not in df.columns: df[c] = "" # 기존 CSV에 커버리지 컬럼이 없으면 자동 생성
        return df[CL]
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df[CL].to_csv(DB, index=False, encoding='utf-8-sig') 
    if st.session_state.sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df[CL])
        except: pass

def get_filtered_sorted_df(df, sel_reg, search_query):
    res = df if sel_reg == "전체" else df[df['지역'] == sel_reg]
    if search_query:
        search_target = res['이름'] + " " + res['지역'] + " " + res['주소']
        res = res[search_target.str.contains(search_query, case=False, na=False)]
    if not res.empty:
        sort_map = {'송신소': 1, '중계소': 2}
        res = res.copy()
        res['구분_순서'] = res['구분'].map(sort_map).fillna(3)
        res = res.sort_values(by=['지역', '구분_순서', '이름']).drop(columns=['구분_순서'])
    return res

# 4. 세션 초기화
if 'sd' not in st.session_state:
    st.session_state.sd = {
        'gs_sync_on': True, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
        'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 340000,
        'm_mode': "신규 등록", 'target_nm': None, 'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "송신소", 'in_v_cov': 0.0,
        'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'temp_active': False, 'temp_lat': 0.0, 'temp_lon': 0.0,
        'show_global_coverage': False, 'show_los_chart': False, 'show_los_line': True, 'map_jump_q': ""
    }
sd = st.session_state.sd

if 'df' not in sd: sd.df = load_db()

# [표 선택 연동]
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    temp_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
    if idx < len(temp_df):
        sel = temp_df.iloc[idx]
        if sd.target_nm != sel['이름']:
            sd.target_nm = sel['이름']
            sd.m_mode = "정보 수정"
            sd.temp_active = False
            sd.show_los_chart = False # 타겟 변경 시 분석 차트 초기화
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            sd.in_v_cov = safe_float(sel.get('커버리지', 0))
            sd.in_v_addr, sd.in_t_la, sd.in_t_lo = str(sel['주소']), safe_float(sel['위도']), safe_float(sel['경도'])
            for s in SL: sd[f"ch_{s}"] = str(sel[s]) if s in sel else ""
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

# 5. 사이드바 UI
with st.sidebar:
    st.header("⚙️ 관제 대시보드")
    sd.gs_sync_on = st.toggle("🌐 클라우드 연동", value=sd.gs_sync_on)
    sd.map_layer = st.radio("지도 레이어", ["일반", "위성", "위성+이름", "특수지형도"], index=["일반", "위성", "위성+이름", "특수지형도"].index(sd.map_layer), horizontal=True)
    
    # 🚩 [변경사항]: 임의 슬라이더 삭제, 등록된 커버리지 표시 스위치로 변경
    sd.show_global_coverage = st.toggle("⭕ 등록된 커버리지 지도 표시", value=sd.show_global_coverage)

    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 내 장부 검색", placeholder="저장된 시설명, 채널 등")

    with st.form("jump_form", clear_on_submit=False):
        jump_q = st.text_input("🌍 공간 이동 (좌표/주소 엔터)", value=sd.map_jump_q, placeholder="좌표 입력")
        if st.form_submit_button("이동", use_container_width=True) and jump_q:
            lat_lon = parse_coord_input(jump_q)
            if lat_lon[0] is not None:
                sd.base_center = list(lat_lon); sd.crosshair_center = list(lat_lon); sd.map_jump_q = jump_q; sd.map_key += 1; st.rerun()
            else:
                loc = Nominatim(user_agent="b_master").geocode(jump_q)
                if loc: sd.base_center = [loc.latitude, loc.longitude]; sd.crosshair_center = [loc.latitude, loc.longitude]; sd.map_jump_q = jump_q; sd.map_key += 1; st.rerun()
                else: st.toast("검색 실패!", icon="❌")

    st.divider()
    
    # 🚩 [변경사항]: 기능 분리를 위한 탭 적용
    tab1, tab2 = st.tabs(["📝 시설 관리", "📡 RF 분석"])

    # ---------- TAB 1: 시설 등록 및 수정 ----------
    with tab1:
        st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
        if st.button("🎯 1. 조준경 위치 추출 (신규/수정)"):
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center; sd.base_center = [sd.in_t_la, sd.in_t_lo]
            try:
                loc = Nominatim(user_agent="b_master").reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
                if loc: sd.in_v_addr = loc.address
            except: pass
            if sd.m_mode == "신규 등록": sd.temp_active = True; sd.temp_lat, sd.temp_lon = sd.crosshair_center
            sd.map_key += 1; st.rerun()
            
        c_mode, c_rst = st.columns([2, 1])
        with c_mode: sd.m_mode = st.radio("작업", ["신규 등록", "정보 수정", "데이터 삭제"], index=["신규 등록", "정보 수정", "데이터 삭제"].index(sd.m_mode), horizontal=True, label_visibility="collapsed")
        with c_rst: 
            if st.button("🔄 초기화"): sd.m_mode = "신규 등록"; sd.target_nm = None; sd.in_v_nm = ""; sd.in_v_cov = 0.0; sd.temp_active = False; st.rerun()

        if sd.m_mode == "데이터 삭제":
            st.error(f"'{sd.target_nm}' 시설을 영구 삭제합니다.")
            if st.button("🚨 삭제 실행", use_container_width=True) and sd.target_nm:
                sd.df = sd.df[sd.df['이름'] != sd.target_nm]; save_db(sd.df); sd.target_nm = None; st.rerun()

        st.text_input("지역", key="in_reg_direct")
        st.text_input("시설명", key="in_v_nm")
        
        c_cat, c_cov = st.columns(2)
        with c_cat: st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        # 🚩 [변경사항]: 커버리지 DB 입력란 추가
        with c_cov: sd.in_v_cov = st.number_input("커버리지(km)", value=float(sd.in_v_cov), step=1.0)
        
        st.text_area("주소", key="in_v_addr", height=70)

        with st.expander("📺 주파수 채널 입력 (DTV/UHD/DMB/FM)", expanded=False):
            st.caption("필요한 채널만 입력하세요.")
            c1, c2 = st.columns(2)
            with c1: st.markdown("**DTV**"); [st.text_input(s, key=f"ch_{s}") for s in SL_DTV]
            with c2: st.markdown("**UHD**"); [st.text_input(s, key=f"ch_{s}") for s in SL_UHD]
            st.markdown("**DMB & FM**")
            c3, c4 = st.columns(2)
            with c3: [st.text_input(s, key=f"ch_{s}") for s in SL_DMB]
            with c4: [st.text_input(s, key=f"ch_{s}") for s in SL_FM[:3]] # 생략 최소화

        st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
        if st.button("✅ 2. 데이터 통합 저장", use_container_width=True):
            if sd.in_v_nm and sd.in_reg_direct:
                v = [sd.in_reg_direct, sd.in_v_cat, sd.in_v_nm, str(sd.in_v_cov)] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
                if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
                else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                save_db(sd.df); sd.target_nm = sd.in_v_nm; sd.temp_active = False; st.success("저장 완료!"); st.rerun()
            else: st.error("지역과 시설명을 입력하세요.")

    # ---------- TAB 2: RF 기술 분석 ----------
    with tab2:
        st.subheader("🔍 가시권(LOS) 분석")
        if sd.target_nm:
            st.markdown(f"**대상:** {sd.target_nm}")
            # 🚩 [변경사항]: 버튼 클릭 시에만 분석 결과 표시
            if st.button("🚀 가시선 분석 실행 (대상 ↔ 조준경)", use_container_width=True):
                sd.show_los_chart = True
                
            if sd.show_los_chart:
                dist_km = geodesic((sd.in_t_la, sd.in_t_lo), sd.crosshair_center).km
                bear = calculate_bearing(sd.in_t_la, sd.in_t_lo, sd.crosshair_center[0], sd.crosshair_center[1])
                c1, c2 = st.columns(2)
                c1.metric("수신 거리", f"{dist_km:.2f} km"); c2.metric("방위각", f"{bear:.1f}°")
                
                if dist_km > 0.1:
                    fresnel_r = 17.32 * math.sqrt(dist_km / (4 * 0.5)); earth_bulge = (dist_km * dist_km) / 50.96 
                    st.caption(f"프레넬 반경: **{fresnel_r:.1f}m** | 지구 곡률: **{earth_bulge:.1f}m**")
                    dist_pts = [dist_km * i / 20 for i in range(21)]; bulge_pts = [(d1 * (dist_km - d1)) / 17.0 for d1 in dist_pts]
                    st.area_chart(pd.DataFrame({'가림고(m)': bulge_pts}, index=dist_pts), color="#ced4da", height=150)
                    sd.show_los_line = st.checkbox("지도에 LOS 라인 그리기", value=sd.show_los_line)
        else:
            st.info("하단 표에서 기준 송신소를 먼저 선택하세요.")
            
        st.divider()
        st.subheader("🧮 물리 채널 ➜ 주파수 변환기")
        ch = st.number_input("CH 번호 입력 (14~69)", 14, 69, 14)
        st.success(f"CH {ch} 중심 주파수 = **{473 + (ch-14)*6} MHz**")


# --- 메인 화면 ---
res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png' if sd.map_layer == "특수지형도" else 'http://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'), attr='Google')

# 조준경 삽입
m.get_root().html.add_child(folium.Element("""
<div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid red; border-radius: 50%; pointer-events: none; z-index: 1000;">
    <div style="position: absolute; top: 50%; left: -10px; width: 60px; height: 2px; background: red;"></div>
    <div style="position: absolute; top: -10px; left: 50%; width: 2px; height: 60px; background: red;"></div>
</div>"""))

# 마커 및 시각화 렌더링
for _, r in res_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat == 0.0: continue
    
    # 커버리지 그리기
    cov = safe_float(r.get('커버리지', 0))
    if sd.show_global_coverage and cov > 0:
        folium.Circle([lat, lon], radius=cov * 1000, color='#1864ab', fill=True, fill_color='#74c0fc', fill_opacity=0.2, tooltip=f"{r['이름']} (반경 {cov}km)").add_to(m)
        
    # 가시권 분석 라인 그리기
    if sd.show_los_chart and sd.show_los_line and sd.target_nm == r['이름']:
        if geodesic((lat, lon), sd.crosshair_center).km > 0.1:
            folium.PolyLine([[lat, lon], sd.crosshair_center], color='red', weight=2.5, dash_array='5, 5', tooltip="RF 가시선").add_to(m)

    folium.Marker([lat, lon], icon=folium.Icon(color='red' if r['구분']=='송신소' else 'blue'), popup=folium.Popup(generate_popup_html(r), max_width=400)).add_to(m)

if sd.get('temp_active'): folium.Marker([sd.temp_lat, sd.temp_lon], icon=folium.Icon(color='lightgray', icon='info-sign')).add_to(m)

map_res = st_folium(m, use_container_width=True, height=800, key=f"map_{sd.map_key}")
if map_res and map_res.get("center"): sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

st.subheader("📊 전국 방송 시설 데이터 현황")
st.dataframe(res_df.style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'};" for _ in row], axis=1), use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")
