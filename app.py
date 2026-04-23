import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import re

st.set_page_config(page_title="Broadcasting Master v560", layout="wide")
DB = 'stations.csv'

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

sd = st.session_state

# ---------------------------------------------------------
# [심장부] 데이터 보호 및 상태 관리 함수
# ---------------------------------------------------------
def sync_current_inputs():
    """현재 화면의 입력값들을 세션에 즉시 박제 (증발 방지)"""
    if 'in_v_nm' in sd: sd.saved_v_nm = sd.in_v_nm
    if 'in_reg_direct' in sd: sd.saved_reg = sd.in_reg_direct
    if 'in_v_addr' in sd: sd.saved_addr = sd.in_v_addr
    for s in SL:
        key = f"ch_{s}"
        if key in sd: sd[f"saved_{key}"] = sd[key]

def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except: return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

# 세션 기본값 설정
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'crosshair_center': None,
    'history': [], 'map_key': 100, 'sel_reg': "전체", 'm_mode': "신규 등록",
    'target_nm': None, 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "",
    'in_v_cat': "중계소", 'in_reg_box': "+ 직접 입력"
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

# ---------------------------------------------------------
# 🔥 [핵심 1] 표 선택 이벤트를 지도보다 먼저 가로챔 (원클릭 즉시 이동)
# ---------------------------------------------------------
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    if idx < len(disp_df):
        sel = disp_df.iloc[idx]
        if sd.target_nm != sel['이름']:
            sd.target_nm = sel['이름']
            # 삭제 모드일 때는 삭제 모드 유지, 아닐 때는 수정 모드로 자동 전환
            if sd.m_mode != "데이터 삭제": sd.m_mode = "정보 수정"
            sd.base_center, sd.base_zoom = [float(sel['위도']), float(sel['경도'])], 16
            sd.in_t_la, sd.in_t_lo, sd.in_v_addr = float(sel['위도']), float(sel['경도']), str(sel['주소'])
            # 채널 데이터 로드
            for s in SL: sd[f"ch_{s}"] = str(sel[s])
            sd.map_key += 1
            sd.main_table["selection"]["rows"] = [] # 버퍼 초기화
            st.rerun()

# ---------------------------------------------------------
# UI 스타일 (사이드바 및 표 중앙 정렬/색상)
# ---------------------------------------------------------
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    
    /* 위치 제어 버튼 디자인 */
    [data-testid="stSidebar"] div.stButton button {
        width: 100% !important; height: 60px !important; margin-bottom: 2px !important;
        font-size: 19px !important; background-color: #f8f9fa !important;
        border: 2px solid #adb5bd !important; border-radius: 10px !important;
        color: #1a1c23 !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    
    /* 3색 액션 버튼 */
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    
    /* 위도경도 대형 버튼 */
    div[data-testid="stNumberInput"] button { min-width: 50px !important; height: 50px !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바: 1위치제어 -> 2관제관리 -> 3위치지정
# ---------------------------------------------------------
with st.sidebar:
    # 1단: 위치 제어
    st.header("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색")
    geolocator = Nominatim(user_agent="broadcasting_v560")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색"):
            if search_addr:
                loc = geolocator.geocode(search_addr)
                if loc:
                    sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                    sd.in_t_la, sd.in_t_lo, sd.in_v_addr = loc.latitude, loc.longitude, loc.address
                    st.rerun()
    with c2:
        if st.button("↩️ 복구"):
            if sd.history: 
                sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()
    if st.button("🧭 내 위치"):
        gps = get_geolocation()
        if gps and 'coords' in gps:
            p = [gps['coords']['latitude'], gps['coords']['longitude']]
            sd.base_center, sd.base_zoom, sd.in_t_la, sd.in_t_lo = p, 16, p[0], p[1]
            st.rerun()

    st.divider()
    # 2단: 관제 및 관리
    st.header("⚙️ 관제 및 관리")
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))

    st.divider()
    # 3단: 위치 지정 및 등록
    st.header("🎯 위치 지정 및 등록")
    
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 신규 위치로 지정"):
        sync_current_inputs(); sd.m_mode, sd.target_nm = "신규 등록", None
        for s in SL: sd[f"ch_{s}"] = ""
        loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = loc[0], loc[1], loc; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 수정 위치로 지정"):
        sync_current_inputs(); sd.m_mode = "정보 수정"
        loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = loc[0], loc[1], loc; st.rerun()

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 등록"):
        final_nm = sd.in_v_nm
        final_reg = sd.in_reg_direct if (sd.m_mode == "신규 등록" and sd.in_reg_box == "+ 직접 입력") else sd.in_reg_box if sd.m_mode == "신규 등록" else sd.in_reg_direct
        if final_nm and final_reg:
            sd.history.append(sd.df.copy())
            v = [final_reg, sd.in_v_cat, final_nm] + [sd[f"ch_{s}"] for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.success("저장 완료!"); st.rerun()

    st.divider()
    # 작업 모드 선택
    mode_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 현재 작업 모드", mode_opts, index=mode_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 시설 등록")
        st.selectbox("1. 지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("📝 새 지역 명칭", key="in_reg_direct")
        st.text_input("2. 시설 이름", key="in_v_nm")
        st.radio("3. 시설 구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        st.text_area("4. 주소 확인/수정", key="in_v_addr")

    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        if sd.target_nm:
            st.text_input("시설 이름", key="in_v_nm")
            st.text_input("지역 명칭", key="in_reg_direct")
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
            st.text_area("주소 수정", key="in_v_addr")
        else: st.warning("목록에서 시설을 선택하세요.")

    # 🔥 [복구] 데이터 삭제 전용 섹션
    elif sd.m_mode == "데이터 삭제":
        st.subheader("🗑️ 데이터 삭제")
        if sd.target_nm:
            st.error(f"대상: {sd.target_nm}")
            if st.button("🚨 시설 삭제 실행", type="primary"):
                sd.history.append(sd.df.copy())
                sd.df = sd.df[sd.df['이름'] != sd.target_nm]
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                sd.target_nm = None; st.success("삭제되었습니다!"); st.rerun()
        else: st.warning("삭제할 시설을 목록에서 선택하세요.")

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.info("📺 물리 채널 설정")
        d_cols = st.columns(3); st.markdown("**📡 DTV**")
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        u_cols = st.columns(3); st.markdown("**✨ UHD**")
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

# ---------------------------------------------------------
# 본문: 지도
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

map_container = st.container()
with map_container:
    css_inj = "<style>.map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; } .map-crosshair::before { content: ''; position: absolute; top: 18px; left: -10px; width: 56px; height: 2px; background: #ff4b4b; } .map-crosshair::after { content: ''; position: absolute; left: 18px; top: -10px; height: 56px; width: 2px; background: #ff4b4b; } .leaflet-popup-content-wrapper { min-width: 500px !important; } .leaflet-popup-content { min-width: 480px !important; }</style><div class='map-crosshair'></div>"
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_inj))
    
    for _, r in disp_df.iterrows():
        is_editing = (sd.m_mode in ["정보 수정", "데이터 삭제"] and sd.target_nm == r['이름'])
        lat = float(sd.in_t_la) if is_editing else float(r['위도'])
        lon = float(sd.in_t_lo) if is_editing else float(r['경도'])
        p, color = [lat, lon], ('red' if r['구분'] == '송신소' else 'blue')
        dt_pop, uh_pop = "|".join([f"{s}:{r[s]}" for s in SL_DTV]), "|".join([f"{s}:{r[s]}" for s in SL_UHD])
        p_html = f"<div style='font-family: sans-serif; padding-top: 5px;'><div style='font-size:20px; font-weight:bold; color:#333; margin-bottom:6px;'>[{r['구분']}] {r['이름']}</div><div style='color:#666; font-size:15px; margin-bottom:12px;'>{r['주소']}</div><div style='font-size:17px; margin-bottom:8px; line-height:1.4;'><b>📡 DTV:</b><br>{dt_pop}</div><div style='font-size:17px; line-height:1.4;'><b>✨ UHD:</b><br>{uh_pop}</div></div>"
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, min_width=500, max_width=500)).add_to(m)
    
    map_data = st_folium(m, use_container_width=True, height=800, key=f"map_{sd.map_key}", returned_objects=["center"])
    if map_data and map_data.get("center"):
        sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# ---------------------------------------------------------
# 🔥 [핵심 복구] 데이터 현황 (색상 구분 + 중앙 정렬 + 원클릭 즉시이동)
# ---------------------------------------------------------
st.subheader("📊 데이터 현황")
def style_table(row):
    bg = '#fff0f0' if row['구분'] == '송신소' else '#f0f7ff'
    fg = '#cc0000' if row['구분'] == '송신소' else '#0066cc'
    return [f'background-color: {bg}; color: {fg}; text-align: center; font-weight: bold;' for _ in row]

view_df = disp_df.copy()
styled_df = view_df[['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']].style.apply(style_table, axis=1)

# key="main_table"로 최상단 이벤트 연동
st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
