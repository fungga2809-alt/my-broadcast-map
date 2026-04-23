import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import re

# 1. 페이지 설정 및 데이터 로드 (최상단)
st.set_page_config(page_title="Broadcasting Master v620", layout="wide")
DB = 'stations.csv'
sd = st.session_state

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except: return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

def safe_float(val, default=0.0):
    try:
        if not val or str(val).strip() == "": return default
        return float(val)
    except: return default

# 2. 세션 상태 초기화
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 7000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'last_clicked_nm': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# ---------------------------------------------------------
# 🔥 [핵심 해결] 위젯이 그려지기 전 최상단에서 클릭 이벤트 처리
# ---------------------------------------------------------
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    # 필터링된 현재 데이터프레임 기준으로 추출
    disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    
    if idx < len(disp_df):
        sel = disp_df.iloc[idx]
        if sd.last_clicked_nm != sel['이름']:
            # 위젯이 그려지기 전에 세션 상태를 먼저 업데이트 (API 에러 방지)
            sd.last_clicked_nm = sel['이름']
            sd.target_nm = sel['이름']
            sd.m_mode = "정보 수정"
            sd.base_center = [safe_float(sel['위도'], 35.1796), safe_float(sel['경도'], 129.0756)]
            sd.in_t_la = safe_float(sel['위도'])
            sd.in_t_lo = safe_float(sel['경도'])
            sd.in_v_addr = str(sel['주소'])
            # 시설 상세 정보 매핑
            sd.in_v_nm = sel['이름']
            sd.in_reg_direct = sel['지역']
            sd.in_v_cat = sel['구분']
            for s in SL: sd[f"ch_{s}"] = str(sel[s])
            
            sd.map_key += 1
            # 선택 버퍼 초기화는 스트림릿이 알아서 하므로 여기서 직접 수정하지 않음
            st.rerun()

# ---------------------------------------------------------
# UI 스타일 및 사이드바 (정보 보존 로직 통합)
# ---------------------------------------------------------
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button {
        width: 100% !important; height: 55px !important; margin-bottom: 3px !important;
        font-size: 18px !important; background-color: #f8f9fa !important;
        border: 2px solid #adb5bd !important; border-radius: 10px !important;
        color: #1a1c23 !important; box-shadow: 0 3px 5px rgba(0,0,0,0.1) !important;
    }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("🔍 위치 제어")
    s_addr = st.text_input("주소/건물명 검색")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색") and s_addr:
            loc = Nominatim(user_agent="b_v620").geocode(s_addr)
            if loc:
                sd.base_center, sd.in_t_la, sd.in_t_lo, sd.in_v_addr = [loc.latitude, loc.longitude], loc.latitude, loc.longitude, loc.address
                sd.map_key += 1; st.rerun()
    with c2:
        if st.button("↩️ 복구") and sd.history:
            sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()
    if st.button("🧭 내 위치"):
        gps = get_geolocation()
        if gps:
            p = [gps['coords']['latitude'], gps['coords']['longitude']]
            sd.base_center, sd.in_t_la, sd.in_t_lo = p, p[0], p[1]; sd.map_key += 1; st.rerun()

    st.divider()
    st.header("⚙️ 관제 및 관리")
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))

    st.divider()
    st.header("🎯 위치 지정 및 등록")
    # 위치 지정 시 key를 통한 동기화 덕분에 텍스트 데이터는 보존됨
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 신규 위치로 지정"):
        sd.m_mode, sd.target_nm = "신규 등록", None
        p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 수정 위치로 지정"):
        sd.m_mode = "정보 수정"
        p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 등록"):
        f_nm = sd.get('in_v_nm', "")
        f_reg = sd.get('in_reg_direct', "") if sd.m_mode != "신규 등록" or sd.get('in_reg_box') == "+ 직접 입력" else sd.get('in_reg_box')
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.success("저장 완료!"); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.selectbox("1. 지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("📝 새 지역 명칭", key="in_reg_direct")
        st.text_input("2. 시설 이름", key="in_v_nm")
        st.radio("3. 시설 구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        st.text_area("4. 주소 확인", key="in_v_addr")

    elif sd.m_mode == "정보 수정":
        if sd.target_nm:
            st.text_input("시설 이름", key="in_v_nm")
            st.text_input("지역 명칭", key="in_reg_direct")
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
            st.text_area("주소 수정", key="in_v_addr")
        else: st.warning("목록에서 수정할 대상을 선택하세요.")

    elif sd.m_mode == "데이터 삭제":
        curr_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
        curr_names = curr_df['이름'].tolist() if not curr_df.empty else []
        if curr_names:
            del_target = st.selectbox("삭제 시설 선택", curr_names)
            if st.button("🚨 시설 삭제 실행", type="primary"):
                sd.history.append(sd.df.copy()); sd.df = sd.df[sd.df['이름'] != del_target]
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); sd.target_nm = None; st.success("삭제 완료!"); st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.info("📺 물리 채널")
        d_cols = st.columns(3); st.markdown("**📡 DTV**")
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        u_cols = st.columns(3); st.markdown("**✨ UHD**")
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

# ---------------------------------------------------------
# 본문 (지도 상단 / 표 하단)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

# 지도 렌더링
with st.container():
    css_inj = "<style>.map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; } .map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; } .map-crosshair::before { top: 18px; left: -10px; width: 56px; height: 2px; } .map-crosshair::after { left: 18px; top: -10px; height: 56px; width: 2px; } .leaflet-popup-content-wrapper { min-width: 500px !important; }</style><div class='map-crosshair'></div>"
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_inj))
    
    for _, r in disp_df.iterrows():
        is_edit = (sd.m_mode in ["정보 수정", "데이터 삭제"] and sd.target_nm == r['이름'])
        lat = safe_float(sd.in_t_la) if is_edit else safe_float(r['위도'])
        lon = safe_float(sd.in_t_lo) if is_edit else safe_float(r['경도'])
        if lat == 0.0 or lon == 0.0: continue
            
        color = 'red' if r['구분'] == '송신소' else 'blue'
        p_html = f"<div style='width:480px; font-size:16px;'><b>[{r['구분']}] {r['이름']}</b><br>{r['주소']}<br><br><b>📡 DTV:</b> { '|'.join([f'{s}:{r[s]}' for s in SL_DTV]) }<br><b>✨ UHD:</b> { '|'.join([f'{s}:{r[s]}' for s in SL_UHD]) }</div>"
        folium.Marker([lat, lon], icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:3px 8px;background:white;border:2px solid {color};border-radius:5px;color:{color};font-weight:bold;white-space:nowrap;transform:translate(15px,-30px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=500)).add_to(m)
    
    map_data = st_folium(m, use_container_width=True, height=750, key=f"map_{sd.map_key}", returned_objects=["center"])
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# 데이터 현황 표 (색상 구분 및 중앙 정렬)
st.subheader("📊 데이터 현황")
def style_df(row):
    bg, fg = ('#fff0f0', '#cc0000') if row['구분'] == '송신소' else ('#f0f7ff', '#0066cc')
    return [f'background-color: {bg}; color: {fg}; text-align: center; font-weight: bold;' for _ in row]

if not disp_df.empty:
    styled = disp_df[['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']].style.apply(style_df, axis=1)
    st.dataframe(styled, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
