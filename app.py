import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import math
import re
import requests
from streamlit_gsheets import GSheetsConnection 

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 전역 변수
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Broadcasting Master v1056", layout="wide")

st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    [data-testid="stSidebar"] { background-color: #f1f3f5 !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #1971c2 !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2f9e44 !important; color: white !important; font-size: 16px !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #e03131 !important; color: white !important; }
    div[role="radiogroup"] { gap: 1rem; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# 채널 및 DB 구조 설정
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL_DMB = ['DMB(SBS)', 'DMB(KBS)', 'DMB(MBC)']
SL_FM = [
    'KBS 1R', 'KBS 2R', 'KBS 음악FM', 
    'MBC 1FM', 'MBC 2FM', 
    'KNN 파워FM', 'KNN 러브FM', 'EBS FM', 
    'CBS 표준FM', 'CBS 음악FM', 'FEBC 극동방송', 
    '교통방송', '교통방송 eFM', 
    '국악방송', 'BBS 불교방송'
]
SL = SL_DTV + SL_UHD + SL_DMB + SL_FM
CL = ['지역', '구분', '이름', '커버리지'] + SL + ['위도', '경도', '주소']
DB = 'stations.csv'
sd = st.session_state

# -----------------------------------------------------------------------------
# 2. 세션 상태 안전 초기화
# -----------------------------------------------------------------------------
if 'init' not in sd:
    sd.update({
        'gs_sync_on': True, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
        'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 
        'base_zoom': 14, 'map_key': 10000, 'm_mode': "신규 등록", 'target_nm': None,
        'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "송신소", 'in_v_cov': 0.0,
        'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 
        'temp_active': False, 'temp_lat': 0.0, 'temp_lon': 0.0,
        'show_global_coverage': False, 'show_los_chart': False, 'show_los_line': True, 'map_jump_q': "",
        'prev_sel_name': None, 'pending_update': None,
        'api_sido': "", 'api_sgg': "", 'api_service_key': "" # API용 변수 추가
    })
    sd['init'] = True

for s in SL:
    if f"ch_{s}" not in sd:
        sd[f"ch_{s}"] = ""

if sd.get('pending_update'):
    sel = sd.pending_update
    sd.m_mode = "정보 수정"
    sd.in_v_nm = sel.get('이름', "")
    sd.in_reg_direct = sel.get('지역', "")
    sd.in_v_cat = sel.get('구분', "송신소")
    try: sd.in_v_cov = float(sel.get('커버리지', 0.0)) if str(sel.get('커버리지', '')).strip() != "" else 0.0
    except: sd.in_v_cov = 0.0
    sd.in_v_addr = str(sel.get('주소', ""))
    
    for s in SL: 
        raw_val = str(sel.get(s, "")).strip()
        if s not in SL_FM and raw_val != "":
            try:
                if float(raw_val).is_integer():
                    raw_val = str(int(float(raw_val)))
            except: pass
        sd[f"ch_{s}"] = raw_val
    sd.pending_update = None

# -----------------------------------------------------------------------------
# 3. 핵심 기능 함수 (전파누리 오픈 API 호출 엔진 포함)
# -----------------------------------------------------------------------------
def fetch_radio_channels_api(sido_nm, sgg_nm, service_key):
    """ 정부 공공데이터포털 전파누리 라디오 정보 조회 API """
    url = "http://apis.data.go.kr/B551257/getRadioChInfoService/getRadioChInfoList"
    params = {
        'serviceKey': service_key, 'pageNo': '1', 'numOfRows': '100', 'type': 'json',
        'sido': sido_nm, 'sgg': sgg_nm
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            
            # 검색 매핑용 버퍼 초기화
            results = {k: "" for k in SL_FM}
            for item in items:
                bcast_nm = str(item.get('bcastNm', ''))
                # 주파수에서 숫자와 소수점만 깔끔하게 추출 (예: 102.9MHz -> 102.9)
                freq = "".join(re.findall(r"[\d\.]+", str(item.get('chFreq', ''))))
                if not freq: continue
                
                if "기독교" in bcast_nm or "CBS" in bcast_nm:
                    if "음악" in bcast_nm: results['CBS 음악FM'] = freq
                    else: results['CBS 표준FM'] = freq
                elif "극동" in bcast_nm or "FEBC" in bcast_nm: results['FEBC 극동방송'] = freq
                elif "교통" in bcast_nm or "TBN" in bcast_nm: results['교통방송'] = freq
                elif "불교" in bcast_nm or "BBS" in bcast_nm: results['BBS 불교방송'] = freq
                elif "국악" in bcast_nm: results['국악방송'] = freq
            return results
    except: pass
    return None

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
    return f"""<div style='width:350px; font-family:sans-serif; font-size:14px;'>
        <div style='font-size:16px; font-weight:bold;'>[{r.get('구분','')}] {r.get('이름','')}</div>
        <div style='color:#555;'>{r.get('주소','')}{cov_h}</div>
        <hr style='margin: 8px 0;'>
        <div style='display:flex; justify-content:space-between;'><div style='width:48%;'><b>📡 DTV</b>{dtv_h}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:10px;'><b>✨ UHD</b>{uhd_h}</div></div>
    </div>"""

def load_db():
    if sd.gs_sync_on:
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
    if sd.gs_sync_on:
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
        res = res.sort_values(by=['지역', '구분_순서', '이름']).drop(columns=['구분_순서']).reset_index(drop=True)
    return res

if 'df' not in sd:
    sd.df = load_db()

# -----------------------------------------------------------------------------
# 4. 사이드바 UI
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 대시보드")
    sd.gs_sync_on = st.toggle("🌐 클라우드 연동", value=sd.gs_sync_on)
    sd.map_layer = st.radio("지도 레이어", ["일반", "위성", "위성+이름", "특수지형도"], index=["일반", "위성", "위성+이름", "특수지형도"].index(sd.map_layer), horizontal=True)
    sd.show_global_coverage = st.toggle("⭕ 등록된 커버리지 지도 표시", value=sd.show_global_coverage)

    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 내 장부 검색", placeholder="저장된 시설명, 채널 등")

    st.markdown("**🌍 원하는 위치로 지도 이동**")
    with st.form("jump_form", clear_on_submit=False):
        c_jmp, c_btn = st.columns([3, 1])
        with c_jmp: jump_q = st.text_input("공간 이동", value=sd.map_jump_q, placeholder="좌표 입력 (예: 35.17, 129.07)", label_visibility="collapsed")
        with c_btn: jump_submit = st.form_submit_button("이동", use_container_width=True)
        if jump_submit and jump_q:
            lat_lon = parse_coord_input(jump_q)
            if lat_lon[0] is not None:
                sd.base_center = list(lat_lon)
                sd.crosshair_center = list(lat_lon)
                sd.map_jump_q = jump_q
                sd.map_key += 1
            else:
                loc = Nominatim(user_agent="b_master").geocode(jump_q)
                if loc: 
                    sd.base_center = [loc.latitude, loc.longitude]
                    sd.crosshair_center = [loc.latitude, loc.longitude]
                    sd.map_jump_q = jump_q
                    sd.map_key += 1
                else: st.toast("검색 실패! 구글지도에서 좌표를 복사해서 넣어주세요.", icon="❌")

    st.divider()
    tab1, tab2 = st.tabs(["📝 시설 관리", "📡 RF 분석"])

    # ---------- TAB 1: 시설 등록/수정 ----------
    with tab1:
        st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
        if st.button("🎯 1. 조준경 위치 추출 (신규/수정)", use_container_width=True):
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            try:
                loc = Nominatim(user_agent="b_master").reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
                if loc: sd.in_v_addr = loc.address
            except: pass
            sd.temp_active = True
            sd.temp_lat, sd.temp_lon = sd.crosshair_center
            sd.map_key += 1
            st.toast("📍 조준경 위치가 성공적으로 추출되었습니다!", icon="✅")
            st.rerun()
            
        if st.button("🔄 2. 입력창 초기화", use_container_width=True): 
            sd.m_mode = "신규 등록"
            sd.target_nm = None
            sd.prev_sel_name = None 
            sd.in_v_nm = ""
            sd.in_reg_direct = ""
            sd.in_v_cov = 0.0
            sd.temp_active = False
            sd.show_los_chart = False
            for s in SL: sd[f"ch_{s}"] = ""
            st.rerun()

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        st.radio("작업 모드 선택", ["신규 등록", "정보 수정", "데이터 삭제"], key="m_mode", horizontal=True)

        if sd.m_mode == "데이터 삭제":
            st.error(f"'{sd.target_nm}' 시설을 영구 삭제합니다.")
            st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
            if st.button("🚨 삭제 실행", use_container_width=True) and sd.target_nm:
                sd.df = sd.df[sd.df['이름'] != sd.target_nm]
                save_db(sd.df)
                sd.target_nm = None
                sd.prev_sel_name = None
                st.rerun()

        st.text_input("지역", key="in_reg_direct")
        
        # 🚩 [신기능]: 전파누리 오픈 API 연동 툴킷
        with st.expander("📡 전파누리 라디오 API 주파수 원격 제어"):
            st.text_input("공공데이터포털 인증키", key="api_service_key", type="password", placeholder="Service Key (Decoding) 붙여넣기")
            st.text_input("시/도 (예: 부산광역시)", key="api_sido")
            st.text_input("시/군/구 (예: 연제구)", key="api_sgg")
            if st.button("🚀 정부 API 주파수 연동 실행", use_container_width=True):
                if sd.api_sido and sd.api_sgg and sd.api_service_key:
                    with st.spinner("오픈 API로부터 해당 행정구역 주파수 매핑 중..."):
                        api_res = fetch_radio_channels_api(sd.api_sido, sd.api_sgg, sd.api_service_key)
                        if api_res:
                            count = 0
                            for k, v in api_res.items():
                                if v:
                                    sd[f"ch_{k}"] = v
                                    count += 1
                            if count > 0:
                                st.success(f"총 {count}개 채널 주파수 로드 성공! 아래 '통합 저장' 시 시트에도 즉시 연동됩니다.")
                                st.rerun()
                            else: st.warning("해당 구역에 등록된 종교/교통 방송 정보가 없습니다.")
                        else: st.error("인증키 오류 또는 전파누리 API 점검 중입니다.")
                else: st.error("인증키, 시/도, 시/군/구를 모두 입력해 주십시오.")

        st.text_input("시설명", key="in_v_nm")
        c_cat, c_cov = st.columns(2)
        with c_cat: st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        with c_cov: st.number_input("커버리지(km)", key="in_v_cov", step=1.0)
        st.text_area("주소", key="in_v_addr", height=70)
        st.caption(f"📍 **현재 설정된 좌표:** {sd.in_t_la:.6f}, {sd.in_t_lo:.6f}")

        with st.expander("📺 DTV & UHD 채널 입력", expanded=True):
            c1, c2 = st.columns(2)
            with c1: 
                st.markdown("**DTV**")
                for s in SL_DTV: st.text_input(s, key=f"ch_{s}")
            with c2: 
                st.markdown("**UHD**")
                for s in SL_UHD: st.text_input(s, key=f"ch_{s}")
                
        with st.expander("📻 DMB & FM 라디오 채널 입력", expanded=True):
            st.markdown("**DMB**")
            c_dmb1, c_dmb2, c_dmb3 = st.columns(3)
            with c_dmb1: st.text_input(SL_DMB[0], key=f"ch_{SL_DMB[0]}")
            with c_dmb2: st.text_input(SL_DMB[1], key=f"ch_{SL_DMB[1]}")
            with c_dmb3: st.text_input(SL_DMB[2], key=f"ch_{SL_DMB[2]}")
            
            st.markdown("**FM 라디오**")
            c_fm1, c_fm2 = st.columns(2)
            for i, s in enumerate(SL_FM):
                with c_fm1 if i % 2 == 0 else c_fm2: st.text_input(s, key=f"ch_{s}") 

        st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
        if st.button("✅ 3. 데이터 통합 저장", use_container_width=True):
            if sd.in_v_nm and sd.in_reg_direct:
                v = [sd.in_reg_direct, sd.in_v_cat, sd.in_v_nm, str(sd.in_v_cov)] + [sd[f"ch_{s}"] for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
                if sd.m_mode == "정보 수정" and sd.target_nm: 
                    sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
                else: 
                    sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                save_db(sd.df)
                sd.target_nm = sd.in_v_nm
                sd.prev_sel_name = sd.in_v_nm
                sd.temp_active = False
                st.success("데이터가 완벽하게 저장되었습니다!")
                st.rerun()
            else: st.error("지역명 또는 시설명이 비어있습니다.")

    # ---------- TAB 2: RF 기술 분석 ----------
    with tab2:
        st.markdown("### 🔍 가시권(LOS) 단면도")
        if sd.target_nm:
            st.markdown(f"**현재 대상:** <span style='color:#1864ab; font-weight:bold;'>{sd.target_nm}</span>", unsafe_allow_html=True)
            sd.show_los_chart = st.toggle("🚀 가시선 분석 켜기", value=sd.show_los_chart)
            if sd.show_los_chart:
                dist_km = geodesic((sd.in_t_la, sd.in_t_lo), sd.crosshair_center).km
                bear = calculate_bearing(sd.in_t_la, sd.in_t_lo, sd.crosshair_center[0], sd.crosshair_center[1])
                c1, c2 = st.columns(2)
                c1.metric("수신 거리", f"{dist_km:.2f} km")
                c2.metric("방위각", f"{bear:.1f}°")
                if dist_km > 0.1:
                    fresnel_r = 17.32 * math.sqrt(dist_km / (4 * 0.5))
                    earth_bulge = (dist_km * dist_km) / 50.96 
                    st.caption(f"프레넬 반경: **{fresnel_r:.1f}m** | 지구 곡률: **{earth_bulge:.1f}m**")
                    dist_pts = [dist_km * i / 20 for i in range(21)]
                    bulge_pts = [(d1 * (dist_km - d1)) / 17.0 for d1 in dist_pts]
                    st.area_chart(pd.DataFrame({'가림고(m)': bulge_pts}, index=dist_pts), color="#ced4da", height=150)
                    sd.show_los_line = st.checkbox("지도에 빨간색 LOS 라인 그리기", value=sd.show_los_line)
        else: st.info("하단 표에서 기준 송신소를 먼저 클릭하세요.")
        st.divider()
        st.subheader("🧮 물리 채널 ➜ 주파수 변환기")
        ch = st.number_input("CH 번호 입력 (14~69)", 14, 69, 14)
        st.success(f"CH {ch} 중심 주파수 = **{473 + (ch-14)*6} MHz**")

# -----------------------------------------------------------------------------
# 5. 메인 화면 렌더링 (지도)
# -----------------------------------------------------------------------------
res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
if sd.map_layer == "특수지형도":
    tile_url = 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png'
    attr = 'Map style: &copy; OpenTopoMap'
else:
    tile_url = f'http://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    attr = 'Google'

m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr=attr)
crosshair_html = """
<div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid red; border-radius: 50%; pointer-events: none; z-index: 1000;">
    <div style="position: absolute; top: 50%; left: -10px; width: 60px; height: 2px; background: red;"></div>
    <div style="position: absolute; top: -10px; left: 50%; width: 2px; height: 60px; background: red;"></div>
</div>
"""
m.get_root().html.add_child(folium.Element(crosshair_html))

for _, r in res_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat == 0.0: continue
    cov = safe_float(r.get('커버리지', 0))
    if sd.show_global_coverage and cov > 0:
        folium.Circle(location=[lat, lon], radius=cov * 1000, color='#1864ab', fill=True, fill_color='#74c0fc', fill_opacity=0.2).add_to(m)
    if sd.show_los_chart and sd.show_los_line and sd.target_nm == r['이름']:
        if geodesic((lat, lon), sd.crosshair_center).km > 0.1:
            folium.PolyLine(locations=[[lat, lon], sd.crosshair_center], color='red', weight=2.5, dash_array='5, 5').add_to(m)
    folium.Marker([lat, lon], icon=folium.Icon(color='red' if r['구분']=='송신소' else 'blue'), popup=folium.Popup(generate_popup_html(r), max_width=400)).add_to(m)

if sd.temp_active: 
    folium.Marker([sd.temp_lat, sd.temp_lon], icon=folium.Icon(color='lightgray', icon='info-sign')).add_to(m)

map_res = st_folium(m, use_container_width=True, height=800, key=f"map_{sd.map_key}", returned_objects=["center"])
if map_res and map_res.get("center"): 
    sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# -----------------------------------------------------------------------------
# 6. 표 데이터 렌더링 및 클릭 이벤트
# -----------------------------------------------------------------------------
st.subheader("📊 전국 방송 시설 데이터 현황")
if not res_df.empty:
    display_df = res_df.copy()
    cols_to_clean = ['커버리지'] + SL_DTV + SL_UHD + SL_DMB
    for c in cols_to_clean:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(lambda x: str(int(float(x))) if str(x).replace('.', '', 1).isdigit() and float(x).is_integer() else x)

    event = st.dataframe(
        display_df.style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'}; color: {'#cc0000' if row['구분']=='송신소' else '#0066cc'};" for _ in row], axis=1), 
        use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table"
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        if idx < len(res_df):
            sel_name = res_df.iloc[idx]['이름']
            if sd.get('prev_sel_name') != sel_name:
                sd['prev_sel_name'] = sel_name 
                sel = res_df.iloc[idx]
                sd.target_nm = sel_name
                sd.temp_active = False
                sd.show_los_chart = False 
                sd.in_t_la = safe_float(sel.get('위도', 0.0))
                sd.in_t_lo = safe_float(sel.get('경도', 0.0))
                sd.base_center = [sd.in_t_la, sd.in_t_lo]
                sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
                sd.map_key += 1
                sd.pending_update = sel.to_dict()
                st.rerun()
    else:
        if sd.get('prev_sel_name') is not None: sd.prev_sel_name = None

    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 CSV 저장 (Excel용)", data=res_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations.csv", use_container_width=True)
    with c2: st.download_button("🌍 KML 저장 (Google Earth용)", data='<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>' + "".join([f"<Placemark><name>{r['이름']}</name><Point><coordinates>{r['경도']},{r['위도']},0</coordinates></Point></Placemark>" for _, r in res_df.iterrows()]) + "</Document></kml>", file_name="stations.kml", use_container_width=True)
