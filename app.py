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

# [방어막] 새로고침 시 채널 데이터 증발 방지
def safe_rerun():
    sd.temp_channels = {s: sd.get(f"ch_{s}", "") for s in SL}
    st.rerun()

if 'temp_channels' in sd:
    for s in SL: sd[f"ch_{s}"] = sd.temp_channels.get(s, "")
    del sd.temp_channels

# [도구] 좌표 변환
def parse_dms_to_decimal(dms_str):
    try:
        pattern = r"(\d+)°(\d+)'([\d.]+)\"([NSEW])"
        matches = re.findall(pattern, dms_str)
        if len(matches) != 2: return None, None
        res = []
        for d, m, s, dr in matches:
            dec = float(d) + float(m)/60 + float(s)/3600
            if dr in ['S', 'W']: dec *= -1
            res.append(dec)
        return res[0], res[1]
    except: return None, None

def get_google_format(lat, lon):
    def to_dms(deg, is_lat):
        try:
            if not deg or str(deg).strip() == "": return ""
            deg = float(deg); d = int(abs(deg)); m = int((abs(deg) - d) * 60); s = round((abs(deg) - d - m/60) * 3600, 2)
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

# [CSS] 사이드바 및 표 스타일 (적색/청색 가독성 복구)
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button {
        width: 100% !important; height: 60px !important; margin-bottom: 2px !important;
        font-size: 19px !important; background-color: #f8f9fa !important;
        border: 2px solid #adb5bd !important; border-radius: 10px !important;
        color: #1a1c23 !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바: 1위치제어 -> 2관제관리 -> 3위치지정
# ---------------------------------------------------------
with st.sidebar:
    st.header("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색"); geolocator = Nominatim(user_agent="broadcasting_v540")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색"):
            if search_addr:
                try:
                    loc = geolocator.geocode(search_addr)
                    if loc:
                        sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                        sd.in_t_la, sd.in_t_lo, sd.in_v_addr = loc.latitude, loc.longitude, clean_kr_address(loc.address)
                        safe_rerun()
                except: st.error("오류")
    with c2:
        if st.button("↩️ 복구"):
            if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); safe_rerun()
    if st.button("🧭 내 위치"):
        gps = get_geolocation()
        if gps and 'coords' in gps:
            p = [gps['coords']['latitude'], gps['coords']['longitude']]
            sd.base_center, sd.base_zoom, sd.in_t_la, sd.in_t_lo = [p[0], p[1]], 16, p[0], p[1]
            try:
                rev = geolocator.reverse(f"{p[0]}, {p[1]}")
                if rev: sd.in_v_addr = clean_kr_address(rev.address)
            except: pass
            safe_rerun()

    st.divider()
    st.header("⚙️ 관제 및 관리")
    existing_regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + existing_regs, index=(existing_regs.index(sd.sel_reg)+1 if sd.sel_reg in existing_regs else 0))

    st.divider()
    st.header("🎯 위치 지정 및 등록")
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 신규 위치로 지정"):
        sd.m_mode = "신규 등록"; sd.target_nm = None; target_loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
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
        st.text_area("4. 주소 확인/수정", key="in_v_addr")
        dms_input = st.text_input("5. 구글어스 DMS 통합 좌표 붙여넣기")
        if dms_input:
            la_p, lo_p = parse_dms_to_decimal(dms_input)
            if la_p: sd.in_t_la, sd.in_t_lo, sd.base_center = la_p, lo_p, [la_p, lo_p]

    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        names = sd.df[sd.df['지역'] == sd.sel_reg]['이름'].tolist() if sd.sel_reg != "전체" else sd.df['이름'].tolist()
        if names:
            target_sel = st.selectbox("대상 선택", names, index=names.index(sd.target_nm) if sd.target_nm in names else 0)
            if sd.target_nm != target_sel:
                sd.target_nm = target_sel
                row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = row['이름'], row['지역'], row['구분']
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = float(row['위도']), float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.last_loaded_nm = sd.target_nm; st.rerun()
            st.text_input("시설 이름", key="in_v_nm"); st.text_input("지역 명칭", key="in_reg_direct")
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
            st.text_area("주소 수정", key="in_v_addr")
            dms_edit = st.text_input("DMS 통합 좌표로 위치 변경")
            if dms_edit:
                la_p, lo_p = parse_dms_to_decimal(dms_edit)
                if la_p: sd.in_t_la, sd.in_t_lo, sd.base_center = la_p, lo_p, [la_p, lo_p]

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.info("📺 물리 채널 설정")
        d_cols = st.columns(3); st.markdown("**📡 DTV 채널**")
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        u_cols = st.columns(3); st.markdown("**✨ UHD 채널**")
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

# ---------------------------------------------------------
# 본문: 지도 및 데이터 현황 (최상단 데이터 동기화 로직)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

# 🔥 [핵심 1] 표 스타일링 함수
def style_stations(row):
    bg = '#fff0f0' if row['구분'] == '송신소' else '#f0f7ff'
    fg = '#cc0000' if row['구분'] == '송신소' else '#0066cc'
    return [f'background-color: {bg}; color: {fg}; text-align: center; font-weight: bold;' for _ in row]

view_df = disp_df.copy()
view_df['통합 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
styled_df = view_df[['지역', '구분', '이름'] + SL + ['통합 좌표', '주소']].style.apply(style_stations, axis=1)

# ---------------------------------------------------------
# 지도 렌더링 (map_key를 이용한 마커 소생술)
# ---------------------------------------------------------
map_container = st.container()
with map_container:
    css_inj = "<style>.map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; } .map-crosshair::before { content: ''; position: absolute; top: 18px; left: -10px; width: 56px; height: 2px; background: #ff4b4b; } .map-crosshair::after { content: ''; position: absolute; left: 18px; top: -10px; height: 56px; width: 2px; background: #ff4b4b; } .leaflet-popup-content-wrapper { min-width: 500px !important; } .leaflet-popup-content { min-width: 480px !important; }</style><div class='map-crosshair'></div>"
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_inj))
    
    for _, r in disp_df.iterrows():
        is_editing = (sd.m_mode == "정보 수정" and sd.target_nm == r['이름'])
        lat = float(sd.in_t_la) if is_editing else float(r['위도']); lon = float(sd.in_t_lo) if is_editing else float(r['경도'])
        p, color = [lat, lon], ('red' if r['구분'] == '송신소' else 'blue')
        dt_pop, uh_pop = "|".join([f"{s}:{r[s]}" for s in SL_DTV]), "|".join([f"{s}:{r[s]}" for s in SL_UHD])
        p_html = f"<div style='font-family: sans-serif; padding-top: 5px;'><div style='font-size:20px; font-weight:bold; color:#333; margin-bottom:6px;'>[{r['구분']}] {r['이름']}</div><div style='color:#666; font-size:15px; margin-bottom:12px;'>{r['주소']}</div><div style='font-size:17px; margin-bottom:8px; line-height:1.4;'><b>📡 DTV:</b><br>{dt_pop}</div><div style='font-size:17px; line-height:1.4;'><b>✨ UHD:</b><br>{uh_pop}</div></div>"
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, min_width=500, max_width=500)).add_to(m)
    
    # 🔥 [핵심 2] map_key를 사용하여 선택 시 지도를 강제로 다시 그리게 함
    st_folium(m, use_container_width=True, height=900, key=f"map_v540_{sd.map_key}", returned_objects=["center"])

# ---------------------------------------------------------
# 데이터 현황 (하단 배치 및 원클릭 오류 방어)
# ---------------------------------------------------------
st.subheader("📊 데이터 현황")
event = st.dataframe(
    styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table"
)

# 🔥 [핵심 3] 원클릭 시 즉시 세션 업데이트 및 지도 갱신 신호
if event and "selection" in event and len(event["selection"]["rows"]) > 0:
    try:
        idx = event["selection"]["rows"][0]
        if idx < len(disp_df):
            sel = disp_df.iloc[idx]
            if sd.target_nm != sel['이름']:
                sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
                sd.base_center, sd.base_zoom = [float(sel['위도']), float(sel['경도'])], 16
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = float(sel['위도']), float(sel['경도']), str(sel['주소'])
                for s in SL: sd[f"ch_{s}"] = str(sel[s])
                sd.last_loaded_nm = sd.target_nm
                sd.map_key += 1 # 이 값을 바꿔서 지도를 즉시 새로 그리게 함
                st.rerun()
    except: pass

st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
