import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import re

st.set_page_config(page_title="Broadcasting Infrastructure Master", layout="wide")
DB = 'stations.csv'

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

sd = st.session_state

# [도구] DMS 형식을 십진수 좌표로 변환
def parse_dms_to_decimal(dms_str):
    try:
        pattern = r"(\d+)°(\d+)'([\d.]+)\"([NSEW])"
        matches = re.findall(pattern, dms_str)
        if len(matches) != 2: return None, None
        results = []
        for d, m, s, direction in matches:
            decimal = float(d) + float(m)/60 + float(s)/3600
            if direction in ['S', 'W']: decimal *= -1
            results.append(decimal)
        return results[0], results[1]
    except: return None, None

def get_google_format(lat, lon):
    def to_dms(deg, is_lat):
        try:
            if not deg or str(deg).strip() == "": return ""
            deg = float(deg)
            d = int(abs(deg))
            m = int((abs(deg) - d) * 60)
            s = round((abs(deg) - d - m/60) * 3600, 2)
            suffix = (("N" if deg >= 0 else "S") if is_lat else ("E" if deg >= 0 else "W"))
            return f"{d}°{m}'{s}\"{suffix}"
        except: return ""
    return f"{to_dms(lat, True)} {to_dms(lon, False)}"

def clean_kr_address(addr_str):
    if not addr_str: return ""
    parts = [p.strip() for p in addr_str.split(',')]
    filtered = []
    for p in parts:
        if p == "대한민국" or re.match(r'^\d{4,5}$', p): continue
        if re.search(r'(도|광역시|특별시|자치시|시|군|구)$', p) and len(p) <= 7: continue
        filtered.append(p)
    filtered.reverse()
    return " ".join(filtered)

def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except: return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'crosshair_center': None,           
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "신규 등록", 'target_nm': None, 'last_loaded_nm': None,
    'in_reg_box': "+ 직접 입력", 'in_reg_direct': "", 'in_v_nm': "", 
    'in_v_cat': "중계소", 'in_v_addr': "", 'in_t_la': 35.1796, 'in_t_lo': 129.0756
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [CSS] 사이드바 배경 및 수직 버튼 동일 크기 튜닝
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; }
    
    /* 사이드바 배경색 (v420 다크 그레이) */
    [data-testid="stSidebar"] {
        background-color: #ced4da !important;
    }
    
    /* 🔥 [핵심] 위치 제어 버튼 수직형 대형화 디자인 */
    /* 텍스트 입력창 바로 아래의 버튼들만 타겟팅 */
    [data-testid="stSidebar"] div.stButton button {
        width: 100% !important;
        height: 60px !important; /* 세 버튼 모두 동일한 높이 부여 */
        margin-bottom: 8px !important; /* 버튼 사이 간격 */
        font-size: 18px !important;
        background-color: #f8f9fa !important;
        border: 2px solid #adb5bd !important;
        border-radius: 12px !important;
        color: #212529 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        transition: all 0.2s ease-in-out !important;
    }
    [data-testid="stSidebar"] div.stButton button:hover {
        background-color: #e2e6ea !important;
        transform: translateY(-2px) !important;
    }
    
    /* 3색 액션 버튼 (적/청/녹) 색상 유지 */
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; border: none !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; border: none !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    existing_regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    filter_idx = existing_regs.index(sd.sel_reg) + 1 if sd.sel_reg in existing_regs else 0
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + existing_regs, index=filter_idx)

    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색")
    
    # 🔥 [변경 사항] 버튼 3개를 수직으로 배치 (순서: 검색 -> 내위치 -> 복구)
    geolocator = Nominatim(user_agent="broadcasting_v450")
    
    if st.button("🔍 검색"):
        if search_addr:
            try:
                loc = geolocator.geocode(search_addr)
                if loc:
                    sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                    sd.in_t_la, sd.in_t_lo, sd.in_v_addr = loc.latitude, loc.longitude, clean_kr_address(loc.address)
                    sd.map_key += 1; st.rerun()
            except: st.error("오류")

    if st.button("🧭 내 위치"):
        gps = get_geolocation()
        if gps and 'coords' in gps:
            p = [gps['coords']['latitude'], gps['coords']['longitude']]
            sd.base_center, sd.base_zoom, sd.in_t_la, sd.in_t_lo = [p[0], p[1]], 16, p[0], p[1]
            try:
                rev = geolocator.reverse(f"{p[0]}, {p[1]}")
                if rev: sd.in_v_addr = clean_kr_address(rev.address)
            except: pass
            sd.map_key += 1; st.rerun()

    if st.button("↩️ 복구"):
        if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    
    # 3색 핵심 컨트롤
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 신규 위치로 지정"):
        sd.m_mode = "신규 등록"; sd.target_nm, sd.last_loaded_nm = None, None
        for s in SL: sd[f"ch_{s}"] = ""
        target_loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = target_loc[0], target_loc[1], [target_loc[0], target_loc[1]]
        try:
            rev = geolocator.reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
            if rev: sd.in_v_addr = clean_kr_address(rev.address)
        except: pass
        st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 수정 위치로 지정"):
        sd.m_mode = "정보 수정"
        target_loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = target_loc[0], target_loc[1], [target_loc[0], target_loc[1]]
        try:
            rev = geolocator.reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
            if rev: sd.in_v_addr = clean_kr_address(rev.address)
        except: pass
        st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
        if st.button("✅ 데이터 등록"):
            final_reg = sd.in_reg_direct if (sd.m_mode == "신규 등록" and sd.in_reg_box == "+ 직접 입력") else sd.in_reg_box if sd.m_mode == "신규 등록" else sd.in_reg_direct
            if sd.in_v_nm and final_reg:
                sd.history.append(sd.df.copy())
                v = [final_reg, sd.in_v_cat, sd.in_v_nm] + [sd[f"ch_{s}"] for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
                if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v
                else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                sd.in_v_nm, sd.in_v_addr, sd.last_loaded_nm = "", "", None 
                for s in SL: sd[f"ch_{s}"] = ""
                st.success("등록 완료!"); st.rerun()

    st.divider()
    st.subheader("📋 정보 원클릭 복사")
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)
    st.code(sd.in_v_addr if sd.in_v_addr else "위치를 지정하세요", language=None)

    st.divider()
    mode_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    selected_mode = st.radio("🛠️ 현재 작업 모드 상태", mode_opts, index=mode_opts.index(sd.m_mode), horizontal=True)
    if selected_mode != sd.m_mode:
        sd.m_mode = selected_mode
        if sd.m_mode == "신규 등록": sd.in_v_nm, sd.in_v_addr, sd.last_loaded_nm = "", "", None
        st.rerun()

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 시설 등록")
        st.selectbox("1. 지역 선택", ["+ 직접 입력"] + existing_regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("📝 새 지역 명칭", key="in_reg_direct")
        st.text_input("2. 시설 이름", key="in_v_nm")
        st.radio("3. 시설 구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        st.info("🏠 주소 및 좌표 설정")
        addr_api_query = st.text_input("4. 주소 검색(API)")
        if st.button("🏠 주소 자동 찾기"):
            if addr_api_query:
                try:
                    loc = geolocator.geocode(addr_api_query)
                    if loc:
                        sd.in_v_addr, sd.in_t_la, sd.in_t_lo = clean_kr_address(loc.address), loc.latitude, loc.longitude
                        sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                        sd.map_key += 1; st.rerun()
                except: st.error("검색 실패")
        st.text_area("5. 주소 확인/수정", key="in_v_addr")
        dms_input = st.text_input("6. 구글어스 DMS 통합 좌표 붙여넣기", placeholder="예: 35°33'27.49\"N 129°15'14.23\"E")
        if dms_input:
            la_parsed, lo_parsed = parse_dms_to_decimal(dms_input)
            if la_parsed: sd.in_t_la, sd.in_t_lo, sd.base_center = la_parsed, lo_parsed, [la_parsed, lo_parsed]

    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        names = sd.df[sd.df['지역'] == sd.sel_reg]['이름'].tolist() if sd.sel_reg != "전체" else sd.df['이름'].tolist()
        if names:
            sd.target_nm = st.selectbox("대상 선택", names, index=names.index(sd.target_nm) if sd.target_nm in names else 0)
            if sd.last_loaded_nm != sd.target_nm:
                row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = row['이름'], row['지역'], row['구분']
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = float(row['위도']), float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.last_loaded_nm = sd.target_nm
            st.text_input("시설 이름", key="in_v_nm"); st.text_input("지역 명칭", key="in_reg_direct")
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
            st.text_area("주소 수정", key="in_v_addr")
            dms_input_edit = st.text_input("DMS 통합 좌표로 위치 변경", placeholder="구글어스 좌표를 붙여넣으세요")
            if dms_input_edit:
                la_p, lo_p = parse_dms_to_decimal(dms_input_edit)
                if la_p: sd.in_t_la, sd.in_t_lo, sd.base_center = la_p, lo_p, [la_p, lo_p]
        else: st.warning("데이터 없음")

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.info("📺 물리 채널 설정")
        d_cols = st.columns(3); st.markdown("**📡 DTV 채널**")
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        u_cols = st.columns(3); st.markdown("**✨ UHD 채널**")
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

# ---------------------------------------------------------
# 본문: 지도
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
map_container = st.container()
with map_container:
    css_injection = "<style>.map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; } .map-crosshair::before { content: ''; position: absolute; top: 18px; left: -10px; width: 56px; height: 2px; background: #ff4b4b; } .map-crosshair::after { content: ''; position: absolute; left: 18px; top: -10px; height: 56px; width: 2px; background: #ff4b4b; } .leaflet-popup-content-wrapper { min-width: 500px !important; } .leaflet-popup-content { min-width: 480px !important; }</style><div class='map-crosshair'></div>"
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_injection))
    for _, r in disp_df.iterrows():
        is_editing = (sd.m_mode == "정보 수정" and sd.target_nm == r['이름'])
        lat, lon = (float(sd.in_t_la), float(sd.in_t_lo)) if (is_editing and sd.in_t_la) else (float(r['위도']), float(r['경도']))
        p, color = [lat, lon], ('red' if r['구분'] == '송신소' else 'blue')
        p_html = f"<div style='font-family: sans-serif; padding-top: 5px;'><div style='font-size:20px; font-weight:bold; color:#333; margin-bottom:6px;'>[{r['구분']}] {r['이름']}</div><div style='color:#666; font-size:15px; margin-bottom:12px;'>{r['주소']}</div></div>"
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, min_width=500, max_width=500)).add_to(m)
    map_data = st_folium(m, use_container_width=True, height=900, key=f"map_v450_{sd.map_key}", returned_objects=["center"])

if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

st.subheader("📊 데이터 현황")
view_df = disp_df.copy()
view_df['통합 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
st.dataframe(view_df[['지역', '구분', '이름'] + SL + ['통합 좌표', '주소']], use_container_width=True, hide_index=True)
st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
