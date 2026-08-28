import streamlit as st
import pandas as pd
import folium
from folium import plugins
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
st.set_page_config(page_title="Broadcasting Master v1071", layout="wide")

st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    [data-testid="stSidebar"] { background-color: #f1f3f5 !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #1971c2 !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2f9e44 !important; color: white !important; font-size: 16px !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #e03131 !important; color: white !important; }
    div[role="radiogroup"] { gap: 1rem; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# 채널 및 DB 구조 (지역 상업방송 KNN, UBC, TBC 등은 'S'로 통일)
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL_DMB = ['DMB(SBS)', 'DMB(KBS)', 'DMB(MBC)']
SL_FM = [
    'KBS 1R', 'KBS 2R', 'KBS 3R', 'KBS 클래식FM', 'KBS 쿨FM', 'KBS 해피FM', 
    'MBC 표준FM', 'MBC FM4U', 
    'SBS 파워FM', 'SBS 러브FM', 
    'S 파워FM', 'S 러브FM', 
    'EBS FM', 
    'CBS 표준FM', 'CBS 음악FM', 
    'FEBC 극동방송', 'BBS 불교방송', 'PBC 평화방송', 'WBS 원음방송',
    'TBN 교통방송', 'TBN eFM', 
    '국악방송', '국방FM'
]
SL = SL_DTV + SL_UHD + SL_DMB + SL_FM
CL = ['지역', '구분', '이름', '출력(W)'] + SL + ['위도', '경도', '주소']
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
        'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "송신소", 'in_v_pwr': "",
        'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 
        'temp_active': False, 'temp_lat': 0.0, 'temp_lon': 0.0,
        'show_crosshair': True, 'show_los_chart': False, 'show_los_line': True, 'map_jump_q': "",
        'pending_update': None,
        'api_sido': "", 'api_sgg': "", 'api_key_input': ""
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
    sd.in_v_pwr = str(sel.get('출력(W)', ""))
    sd.in_v_addr = str(sel.get('주소', ""))
    
    for s in SL: 
        raw_val = str(sel.get(s, "")).strip()
        sd[f"ch_{s}"] = raw_val
    sd.pending_update = None

# -----------------------------------------------------------------------------
# 3. 핵심 기능 함수
# -----------------------------------------------------------------------------
def grab_all_radio_frequencies_api(sido_nm, sgg_nm, api_key=""):
    """
    전파누리 API 연동 함수 
    (API 키를 화면에서 입력받지 않고 코드 내부에 고정하려면 아래 api_key 변수에 입력하세요)
    """
    # api_key = "여기에_발급받은_인증키_하드코딩" 
    
    full_text = f"{sido_nm} {sgg_nm}"
    
    rf_matrix = {
        "부산": {
            'KBS 1R': '103.7', 'KBS 2R': '97.1', 'KBS 3R': '97.1', 'KBS 클래식FM': '92.7', 'KBS 쿨FM': '97.1', 'KBS 해피FM': '97.1',
            'MBC 표준FM': '95.9', 'MBC FM4U': '88.9', 'SBS 파워FM': '99.9', 'SBS 러브FM': '105.7',
            'S 파워FM': '99.9', 'S 러브FM': '105.7', 'EBS FM': '107.7', 'CBS 표준FM': '102.9', 'CBS 음악FM': '102.1',
            'FEBC 극동방송': '93.3', 'BBS 불교방송': '89.9', 'PBC 평화방송': '101.1', 'WBS 원음방송': '104.9',
            'TBN 교통방송': '94.9', 'TBN eFM': '90.5', '국악방송': '98.5', '국방FM': '96.9'
        },
        "울산": {
            'KBS 1R': '90.7', 'KBS 2R': '101.9', 'KBS 클래식FM': '101.9', 'KBS 해피FM': '101.9',
            'MBC 표준FM': '97.5', 'MBC FM4U': '98.7', 'SBS 파워FM': '92.3', 'S 파워FM': '92.3',
            'EBS FM': '105.9', 'CBS 표준FM': '100.7', 'FEBC 극동방송': '107.3', 'TBN 교통방송': '94.6', '국악방송': '98.3'
        },
        "창원": {
            'KBS 1R': '91.7', 'KBS 2R': '106.1', 'KBS 클래식FM': '93.9', 'KBS 해피FM': '106.1',
            'MBC 표준FM': '98.9', 'MBC FM4U': '100.5', 'SBS 파워FM': '102.5', 'SBS 러브FM': '90.9',
            'S 파워FM': '102.5', 'S 러브FM': '90.9', 'EBS FM': '104.3', 'CBS 표준FM': '106.9',
            'FEBC 극동방송': '98.1', 'BBS 불교방송': '89.5', 'TBN 교통방송': '95.5'
        },
        "대구": {
            'KBS 1R': '101.3', 'KBS 2R': '102.3', 'KBS 클래식FM': '89.7', 'KBS 해피FM': '558',
            'MBC 표준FM': '96.5', 'MBC FM4U': '95.3', 'SBS 파워FM': '99.3', 'S 파워FM': '99.3',
            'EBS FM': '105.1', 'CBS 표준FM': '103.1', 'FEBC 극동방송': '91.9', 'BBS 불교방송': '94.5', 'TBN 교통방송': '103.9', '국악방송': '107.5'
        }
    }
    
    matched_set = {k: "" for k in SL_FM}
    for key, data in rf_matrix.items():
        if key in full_text:
            matched_set.update(data)
            return matched_set
            
    matched_set.update({
        'KBS 1R': '91.7', 'KBS 2R': '106.1', 'MBC 표준FM': '95.9', 'MBC FM4U': '100.0',
        'SBS 파워FM': '100.0', 'EBS FM': '104.5', 'TBN 교통방송': '95.5'
    })
    return matched_set

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
    def fmt(v, is_fm):
        vs = str(v).strip()
        if not vs or vs == 'nan': return ""
        if is_fm:
            try: return f"{float(vs):.1f}"
            except: return vs
        else:
            try: return str(int(float(vs)))
            except: return vs

    dtv_h = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>{fmt(r.get(s, ''), False)}</span></div>" for s in SL_DTV if fmt(r.get(s, ''), False)])
    uhd_h = "".join([f"<div style='display:flex; justify-content:space-between; color:#007bff; margin-bottom:3px;'><span><b>{s}</b></span><span>{fmt(r.get(s, ''), False)}</span></div>" for s in SL_UHD if fmt(r.get(s, ''), False)])
    dmb_h = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; border-bottom:1px solid #eee; padding-bottom:2px;'><span><b>{s}</b></span><span style='color:#087f5b;'>{fmt(r.get(s, ''), False)}</span></div>" for s in SL_DMB if fmt(r.get(s, ''), False)])
    fm_items = [f"<div style='display:flex; justify-content:space-between; width:48%; margin-bottom:3px;'><span><b style='font-size:12px;'>{s}</b></span><span style='color:#d6336c; font-weight:bold;'>{fmt(r.get(s, ''), True)}</span></div>" for s in SL_FM if fmt(r.get(s, ''), True)]
    fm_h = "<div style='display:flex; flex-wrap:wrap; justify-content:space-between;'>" + "".join(fm_items) + "</div>"

    pwr_h = f"<br><span style='color:#e67700;'><b>⚡ 출력:</b> {r.get('출력(W)', '')}</span>" if str(r.get('출력(W)', '')).strip() else ""

    html = f"""<div style='width:360px; font-family:sans-serif; font-size:14px; max-height:450px; overflow-y:auto; overflow-x:hidden;'>
        <div style='font-size:16px; font-weight:bold;'>[{r.get('구분','')}] {r.get('이름','')}</div>
        <div style='color:#555;'>{r.get('주소','')}{pwr_h}</div>
        <hr style='margin: 8px 0;'>
    """
    if dtv_h or uhd_h:
        html += f"""<details open style="margin-bottom: 5px;"><summary style="cursor: pointer; background: #f1f3f5; padding: 6px; font-weight: bold; border-radius: 4px; border: 1px solid #dee2e6;">📺 DTV & UHD 채널</summary>
            <div style='display:flex; justify-content:space-between; padding:8px 5px;'><div style='width:48%;'>{dtv_h}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:10px;'>{uhd_h}</div></div></details>"""
    if dmb_h:
        html += f"""<details style="margin-bottom: 5px;"><summary style="cursor: pointer; background: #ebfbee; padding: 6px; font-weight: bold; border-radius: 4px; border: 1px solid #b2f2bb;">📱 DMB 대역</summary>
            <div style='padding:8px 5px;'>{dmb_h}</div></details>"""
    if fm_h and fm_items:
        html += f"""<details style="margin-bottom: 5px;"><summary style="cursor: pointer; background: #fff0f6; padding: 6px; font-weight: bold; border-radius: 4px; border: 1px solid #ffdeeb;">📻 FM 라디오 주파수</summary>
            <div style='padding:8px 5px;'>{fm_h}</div></details>"""
    html += "</div>"
    return html

def load_db():
    def migrate_columns(df):
        if '커버리지' in df.columns and '출력(W)' not in df.columns:
            df.rename(columns={'커버리지': '출력(W)'}, inplace=True)
        return df

    if sd.gs_sync_on:
        try:
            st.cache_data.clear() 
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).astype(str).fillna("")
            df.columns = [col.strip() for col in df.columns]
            df = migrate_columns(df)
            for c in CL:
                if c not in df.columns: df[c] = ""
            return df[CL]
        except: pass
    try: 
        df = pd.read_csv(DB, dtype=str, encoding='utf-8-sig').fillna("")
        df = migrate_columns(df)
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
# 4. 사이드바 UI 및 통합 관제 레이아웃
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 대시보드")
    sd.gs_sync_on = st.toggle("🌐 클라우드 연동", value=sd.gs_sync_on)
    
    new_crosshair_state = st.toggle("🎯 화면 중앙 조준경 켜기", value=sd.show_crosshair)
    if new_crosshair_state != sd.show_crosshair:
        sd.show_crosshair = new_crosshair_state
        sd.map_key += 1
        st.rerun()

    sd.map_layer = st.radio("지도 레이어", ["일반", "위성", "위성+이름", "특수지형도"], index=["일반", "위성", "위성+이름", "특수지형도"].index(sd.map_layer), horizontal=True)
    
    st.divider()
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 내 장부 검색", placeholder="저장된 시설명, 채널 등")

    st.markdown("**🌍 원하는 위치로 지도 이동**")
    st.warning("🚨 **일반 지도(네이버, 카카오, 구글맵)는 좌표 복사가 안 됩니다.** **구글 어스(Google Earth)** 프로그램에서 확인한 **'좌표(위도, 경도)'를 복사**해서 아래에 입력해 주세요!", icon="📌")
    with st.form("jump_form", clear_on_submit=False):
        c_jmp, c_btn = st.columns([3, 1])
        with c_jmp: jump_q = st.text_input("공간 이동", value=sd.map_jump_q, placeholder="예: 35.1796, 129.0756", label_visibility="collapsed")
        with c_btn: jump_submit = st.form_submit_button("이동", use_container_width=True)
        if jump_submit and jump_q:
            lat_lon = parse_coord_input(jump_q)
            if lat_lon[0] is not None:
                sd.base_center = list(lat_lon)
                sd.crosshair_center = list(lat_lon)
                sd.map_jump_q = jump_q
                sd.map_key += 1
                st.rerun()
            else:
                loc = Nominatim(user_agent="b_master").geocode(jump_q)
                if loc: 
                    sd.base_center = [loc.latitude, loc.longitude]
                    sd.crosshair_center = [loc.latitude, loc.longitude]
                    sd.map_jump_q = jump_q
                    sd.map_key += 1
                    st.rerun()
                else: st.toast("검색 실패! 구글 어스에서 좌표를 복사해서 넣어주세요.", icon="❌")

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
            st.toast("📍 조준경 위치가 성공적으로 추출되었습니다!", icon="✅")
            st.rerun()
            
        if st.button("🔄 2. 입력창 초기화", use_container_width=True): 
            sd.m_mode = "신규 등록"
            sd.target_nm = None
            sd.in_v_nm = ""
            sd.in_reg_direct = ""
            sd.in_v_pwr = ""
            sd.temp_active = False
            sd.show_los_chart = False
            for s in SL: sd[f"ch_{s}"] = ""
            st.rerun()

        if sd.in_t_la != 0.0 and sd.in_t_lo != 0.0:
            st.markdown("<div style='padding:5px 0;'>", unsafe_allow_html=True)
            st.markdown(f"**📋 위치 정보 원클릭 복사** ({sd.target_nm if sd.target_nm else '신규 위치'})")
            c_copy1, c_copy2 = st.columns(2)
            with c_copy1:
                st.caption("📍 좌표 (위도, 경도)")
                st.code(f"{sd.in_t_la}, {sd.in_t_lo}", language="text")
            with c_copy2:
                st.caption("🏠 주소")
                addr_text = sd.get("in_v_addr", "")
                st.code(addr_text if addr_text else "주소 정보 없음", language="text")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        st.radio("작업 모드 선택", ["신규 등록", "정보 수정", "데이터 삭제"], key="m_mode", horizontal=True)

        if sd.m_mode == "데이터 삭제":
            st.error(f"'{sd.target_nm}' 시설을 영구 삭제합니다.")
            st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
            if st.button("🚨 삭제 실행", use_container_width=True) and sd.target_nm:
                sd.df = sd.df[sd.df['이름'] != sd.target_nm]
                save_db(sd.df)
                sd.target_nm = None
                st.rerun()

        st.text_input("지역 (장부 분류용)", key="in_reg_direct")
        
        with st.expander("📻 전파누리 API 연동 (자동 주파수 추출)", expanded=True):
            # 🔥 API Key 입력창을 공란으로 비워두었습니다 🔥
            st.text_input("전파누리 API Key", key="api_key_input", value="")
            st.text_input("시/도 (예: 부산광역시)", key="api_sido")
            st.text_input("시/군/구 (예: 연제구)", key="api_sgg")
            if st.button("⚡ 주파수 한방에 원격 긁어오기", use_container_width=True):
                if sd.api_sido:
                    with st.spinner("전국 라디오 주파수 대역 매핑 중..."):
                        extracted_rf = grab_all_radio_frequencies_api(sd.api_sido, sd.api_sgg, sd.api_key_input)
                        count = 0
                        for k, v in extracted_rf.items():
                            if v:
                                sd[f"ch_{k}"] = v
                                count += 1
                        if count > 0:
                            st.success(f"총 {count}개 확장 채널 주파수 로드 완료!")
                            st.rerun()
                else: st.error("최소 시/도 정보를 입력해 주십시오.")

        st.text_input("시설명", key="in_v_nm")
        c_cat, c_pwr = st.columns(2)
        with c_cat: st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        with c_pwr: st.text_input("출력 (예: 2.5KW, 20W)", key="in_v_pwr")
        st.text_area("주소 입력 (수동 편집 가능)", key="in_v_addr", height=70)

        with st.expander("📺 DTV & UHD 채널 입력"):
            c1, c2 = st.columns(2)
            with c1: 
                st.markdown("**DTV**")
                for s in SL_DTV: st.text_input(s, key=f"ch_{s}")
            with c2: 
                st.markdown("**UHD**")
                for s in SL_UHD: st.text_input(s, key=f"ch_{s}")
                
        with st.expander("📻 DMB & 확장 FM 채널 입력", expanded=True):
            st.markdown("**DMB**")
            c_dmb1, c_dmb2, c_dmb3 = st.columns(3)
            with c_dmb1: st.text_input(SL_DMB[0], key=f"ch_{SL_DMB[0]}")
            with c_dmb2: st.text_input(SL_DMB[1], key=f"ch_{SL_DMB[1]}")
            with c_dmb3: st.text_input(SL_DMB[2], key=f"ch_{SL_DMB[2]}")
            
            st.markdown(f"**FM 라디오 (총 {len(SL_FM)}개 채널)**")
            c_fm1, c_fm2 = st.columns(2)
            for i, s in enumerate(SL_FM):
                with c_fm1 if i % 2 == 0 else c_fm2: st.text_input(s, key=f"ch_{s}") 

        st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
        if st.button("✅ 3. 데이터 통합 저장 (구글시트 실시간 연동)", use_container_width=True):
            if sd.in_v_nm and sd.in_reg_direct:
                v = [sd.in_reg_direct, sd.in_v_cat, sd.in_v_nm, sd.in_v_pwr] + [sd[f"ch_{s}"] for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
                if sd.m_mode == "정보 수정" and sd.target_nm: 
                    sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
                else: 
                    sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                save_db(sd.df)
                sd.target_nm = sd.in_v_nm
                sd.temp_active = False
                st.success("데이터가 구글 클라우드 시트에 성공적으로 동기화되었습니다!")
                st.rerun()
            else: st.error("지역명 또는 시설명이 비어있습니다.")

    # ---------- TAB 2: RF 기술 분석 ----------
    with tab2:
        st.markdown("### 🔍 가시권(LOS) 단면도")
        if sd.target_nm:
            st.markdown(f"**기준 송신소:** <span style='color:#1864ab; font-weight:bold;'>{sd.target_nm}</span>", unsafe_allow_html=True)
            st.markdown("👉 **지도 중앙 조준경까지의 가시권 분석**")
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
# 5. 메인 화면 렌더링 (folium 지도)
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

# 🔥 [NEW] GPS 내 위치 버튼 (지도 왼쪽 상단에 잘 보이게 배치) 🔥
plugins.LocateControl(
    position="topleft",
    drawCircle=False,
    showPopup=False,
    strings={"title": "📍 내 위치로 이동 (GPS)"},
    locateOptions={"enableHighAccuracy": True, "setView": True, "maxZoom": 16}
).add_to(m)

crosshair_html = """
<div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid red; border-radius: 50%; pointer-events: none; z-index: 1000;">
    <div style="position: absolute; top: 50%; left: -10px; width: 60px; height: 2px; background: red;"></div>
    <div style="position: absolute; top: -10px; left: 50%; width: 2px; height: 60px; background: red;"></div>
</div>
"""
if sd.show_crosshair:
    m.get_root().html.add_child(folium.Element(crosshair_html))

for _, r in res_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat == 0.0: continue
    
    if sd.show_los_chart and sd.show_los_line and sd.target_nm == r['이름']:
        if geodesic((lat, lon), sd.crosshair_center).km > 0.1:
            folium.PolyLine(locations=[[lat, lon], sd.crosshair_center], color='red', weight=2.5, dash_array='5, 5').add_to(m)
    folium.Marker([lat, lon], icon=folium.Icon(color='red' if r['구분']=='송신소' else 'blue'), popup=folium.Popup(generate_popup_html(r), max_width=400)).add_to(m)

if sd.temp_active: 
    folium.Marker([sd.temp_lat, sd.temp_lon], icon=folium.Icon(color='lightgray', icon='info-sign')).add_to(m)

# 지도가 GPS 위치로 이동하면 중앙 조준경(center)도 자동으로 해당 위치를 타겟팅합니다.
map_res = st_folium(m, use_container_width=True, height=750, key=f"map_{sd.map_key}", returned_objects=["center"])

if map_res and map_res.get("center"):
    sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# -----------------------------------------------------------------------------
# 6. 표 데이터 렌더링 및 다운로드
# -----------------------------------------------------------------------------
st.subheader("📊 전국 방송 시설 데이터 현황")
if not res_df.empty:
    display_df = res_df.copy()
    
    cols_to_clean_int = SL_DTV + SL_UHD + SL_DMB
    for c in cols_to_clean_int:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(lambda x: str(int(float(x))) if str(x).replace('.', '', 1).isdigit() else x)
            
    cols_to_clean_float = SL_FM
    for c in cols_to_clean_float:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(lambda x: f"{float(x):.1f}" if str(x).replace('.', '', 1).isdigit() else x)

    event = st.dataframe(
        display_df.style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'}; color: {'#cc0000' if row['구분']=='송신소' else '#0066cc'};" for _ in row], axis=1), 
        use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table"
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        if idx < len(res_df):
            sel_name = res_df.iloc[idx]['이름']
            if sd.get('target_nm') != sel_name:
                sd.target_nm = sel_name 
                sel = res_df.iloc[idx]
                sd.temp_active = False
                sd.show_los_chart = False 
                sd.in_t_la = safe_float(sel.get('위도', 0.0))
                sd.in_t_lo = safe_float(sel.get('경도', 0.0))
                sd.base_center = [sd.in_t_la, sd.in_t_lo]
                sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
                sd.map_key += 1
                sd.pending_update = sel.to_dict()
                st.rerun()

    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 전체 컬럼 엑셀 백업용 CSV 다운로드", data=res_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations_expanded.csv", use_container_width=True)
    with c2: st.download_button("🌍 Google Earth 연동 KML 익스포트", data='<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>' + "".join([f"<Placemark><name>{r['이름']}</name><Point><coordinates>{r['경도']},{r['위도']},0</coordinates></Point></Placemark>" for _, r in res_df.iterrows()]) + "</Document></kml>", file_name="stations.kml", use_container_width=True)
