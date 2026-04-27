import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from branca.element import Template, MacroElement
from streamlit_gsheets import GSheetsConnection 
import time

# 1. 페이지 설정 및 가로 꽉 참 설정
st.set_page_config(page_title="Broadcasting Master v985", layout="wide")

sd = st.session_state
DB = 'stations.csv'
GS_URL = st.secrets.get("gsheets_url", "")

# [CSS 스타일] 가로 꽉 참 및 동적 폰트 설정
def apply_custom_style(font_size):
    st.markdown(f"""<style>
        .main .block-container {{ padding: 1rem !important; max-width: 100% !important; }}
        [data-testid="stSidebar"] {{ background-color: #f8f9fa !important; }}
        [data-testid="stSidebar"] div.stButton button {{ width: 100%; border-radius: 8px; height: 45px; }}
        div.element-container:has(.btn-red) + div.element-container button {{ background-color: #ff4b4b; color: white; }}
        div.element-container:has(.btn-blue) + div.element-container button {{ background-color: #3498db; color: white; }}
        div.element-container:has(.btn-green) + div.element-container button {{ background-color: #2ecc71; color: white; }}
        [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {{ font-size: {font_size}px !important; }}
    </style>""", unsafe_allow_html=True)

# [도구함]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
    except: return default

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [데이터 로직]
def load_db():
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=GS_URL, ttl=0).astype(str).fillna("")
            for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True).replace('nan', '')
            return df
        except: pass
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True)
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig')
    if sd.get('gs_sync_on', False) and GS_URL:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=GS_URL, data=df)
            st.cache_data.clear()
        except Exception as e: st.error(f"시트 동기화 실패: {e}")

# [세션 초기화]
defaults = {
    'df': load_db(), 'gs_sync_on': False, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
    'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'map_key': 100,
    'm_mode': "신규 등록", 'target_nm': None, 'font_size': 18,
    'in_v_nm': "", 'in_reg_box': "+ 새 지역 추가", 'in_reg_direct': "", 'in_v_cat': "송신소",
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'cov_radius': 10
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

apply_custom_style(sd.font_size)

# [사이드바 설정]
with st.sidebar:
    st.title("⚙️ 관제 센터 설정")
    
    # 12. 파일 업데이트 기능 (구글 시트와 무관)
    uploaded_file = st.file_uploader("📥 CSV 파일 업데이트", type="csv")
    if uploaded_file:
        sd.df = pd.read_csv(uploaded_file, dtype=str).fillna("")
        save_db(sd.df); st.rerun()

    # 1. 구글 시트 연동 토글
    sd.gs_sync_on = st.toggle("🌐 구글 시트 실시간 동기화", value=sd.gs_sync_on)
    
    # 2. 지도 레이어
    sd.map_layer = st.radio("🗺️ 지도 레이어", ["일반", "위성", "위성+이름"], horizontal=True)
    
    # 14. 폰트 크기 조정
    sd.font_size = st.slider("📏 표 폰트 크기", 10, 40, sd.font_size)

    st.divider()
    # 3. 지역 필터
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("📍 지역 필터", ["전체"] + regs)
    
    # 4. 통합 검색창
    sd.ch_search = st.text_input("🔎 통합 검색", placeholder="시설명, 지역, 물리번호(채널) 검색 가능")

    st.divider()
    # 5. 위치 추출 및 저장 버튼
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치 추출"):
        sd.m_mode, sd.target_nm = "신규 등록", None
        sd.in_t_la, sd.in_t_lo = sd.crosshair_center
        try:
            loc = Nominatim(user_agent="b_master").reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
            if loc: sd.in_v_addr = loc.address
        except: pass
        sd.map_key += 1; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치 추출"):
        if sd.target_nm:
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center
            sd.map_key += 1; st.toast("위치 좌표가 갱신되었습니다!"); st.rerun()

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 저장"):
        f_nm = sd.in_v_nm
        f_reg = sd.in_reg_direct if sd.in_reg_box == "+ 새 지역 추가" else sd.in_reg_box
        if f_nm and f_reg:
            v = [f_reg, sd.in_v_cat, f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            if sd.m_mode == "정보 수정" and sd.target_nm:
                sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); st.rerun()

    # 7 & 8. 정보 입력창
    st.divider()
    st.subheader("📝 시설 정보 입력")
    st.radio("작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], key="m_mode", horizontal=True)
    
    if sd.m_mode == "신규 등록":
        st.selectbox("지역 선택", ["+ 새 지역 추가"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 새 지역 추가": st.text_input("새 지역명", key="in_reg_direct")
    else:
        st.text_input("지역명 수정", key="in_reg_direct")

    st.text_input("시설 이름", key="in_v_nm")
    st.radio("구분", ["송신소", "중계소", "간이중계소"], key="in_v_cat", horizontal=True)
    st.text_area("주소 및 좌표 상세", key="in_v_addr")
    
    # 6. 좌표 및 주소 복사 지원용 표시
    st.caption("📍 현재 설정 좌표 (복사 가능)")
    st.code(f"{sd.in_t_la}, {sd.in_t_lo}")

    st.subheader("📡 물리 채널 설정")
    for section, list_ch in [("DTV", SL_DTV), ("UHD", SL_UHD)]:
        st.write(f"**{section}**")
        cols = st.columns(5)
        for i, s in enumerate(list_ch):
            with cols[i]: st.text_input(s, key=f"ch_{s}", label_visibility="collapsed")
    
    # 11. 커버리지 반경 설정
    sd.cov_radius = st.number_input("📡 커버리지 가시화 반경 (km)", 1, 100, sd.cov_radius)

# [메인 화면]
st.title("📡 방송 관제 센터 실시간 모니터링")

# 데이터 필터링
res_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search:
    mask = res_df.apply(lambda row: sd.ch_search.lower() in " ".join(row.values).lower(), axis=1)
    res_df = res_df[mask]

# 정렬
sort_map = {'송신소': 1, '중계소': 2, '간이중계소': 3}
res_df = res_df.assign(s_order=res_df['구분'].map(sort_map).fillna(4)).sort_values(['지역', 's_order', '이름']).drop('s_order', axis=1)

# [지도 렌더링]
l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='Google')

# 조준경 매크로
cross_html = MacroElement()
cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.crosshair::before, .crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.crosshair::before { top: 18px; left: -10px; width: 60px; height: 4px; }.crosshair::after { left: 18px; top: -10px; height: 60px; width: 4px; }</style><div class="crosshair"></div>{% endmacro %}""")
m.get_root().add_child(cross_html)

# 마커 추가
for _, r in res_df.iterrows():
    lat, lon = safe_float(r['위도']), safe_float(r['경도'])
    if lat == 0: continue
    
    is_target = (sd.target_nm == r['이름'])
    # 🚩 위치 수정 중인 마커는 실시간 좌표를 따름
    disp_lat, disp_lon = (sd.in_t_la, sd.in_t_lo) if is_target else (lat, lon)
    
    color = 'red' if r['구분'] == '송신소' else 'blue'
    
    # 10. 팝업 디자인
    dtv_tags = "".join([f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid #eee;'><b>{s}</b><span>{r[s]}</span></div>" for s in SL_DTV])
    uhd_tags = "".join([f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid #eee; color:#007bff;'><b>{s}</b><span>{r[s]}</span></div>" for s in SL_UHD])
    
    p_html = f"""<div style='width:300px; font-family:sans-serif;'>
        <div style='font-size:18px; font-weight:bold; border-bottom:2px solid #333; margin-bottom:5px;'>
            [{r['구분']}] <span style='background:#ffff00;'>{r['이름']}</span>
        </div>
        <div style='font-size:12px; color:#666; margin-bottom:10px;'>{r['주소']}</div>
        <div style='display:flex; justify-content:space-between;'>
            <div style='width:48%; font-size:13px;'><b>📡 DTV</b>{dtv_tags}</div>
            <div style='width:48%; font-size:13px; border-left:1px solid #ddd; padding-left:10px;'><b>✨ UHD</b>{uhd_tags}</div>
        </div>
    </div>"""
    
    folium.Marker([disp_lat, disp_lon], icon=folium.Icon(color=color), popup=folium.Popup(p_html, max_width=400)).add_to(m)
    
    # 11. 커버리지 시각화 (클릭한 대상 강조)
    if is_target:
        folium.Circle([disp_lat, disp_lon], radius=sd.cov_radius*1000, color=color, fill=True, fill_opacity=0.1).add_to(m)

map_res = st_folium(m, use_container_width=True, height=850, key=f"map_v{sd.map_key}")
if map_res and map_res.get("center"):
    sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# [데이터 현황 표]
st.subheader("📊 방송 시설 데이터 현황")
if not res_df.empty:
    # 표 선택 이벤트
    sel_data = st.dataframe(
        res_df.style.apply(lambda x: [f"background-color: {'#fff0f0' if x['구분']=='송신소' else '#f0f7ff'}" for _ in x], axis=1),
        use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table"
    )
    
    # 선택 시 정보 로드
    if sel_data.get("selection", {}).get("rows"):
        idx = sel_data["selection"]["rows"][0]
        sel = res_df.iloc[idx]
        if sd.target_nm != sel['이름']:
            sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            sd.in_v_addr, sd.in_t_la, sd.in_t_lo = sel['주소'], safe_float(sel['위도']), safe_float(sel['경도'])
            for s in SL: sd[f"ch_{s}"] = sel[s]
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

    # 13. KML 내보내기 및 12. CSV 저장
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 현재 리스트 CSV 저장", data=res_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations_export.csv", use_container_width=True)
    with c2:
        kml_data = f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        for _, r in res_df.iterrows():
            kml_data += f"<Placemark><name>{r['이름']}</name><Point><coordinates>{r['경도']},{r['위도']},0</coordinates></Point></Placemark>"
        kml_data += "</Document></kml>"
        st.download_button("🌍 구글어스용 KML 저장", data=kml_data, file_name="stations.kml", use_container_width=True)
