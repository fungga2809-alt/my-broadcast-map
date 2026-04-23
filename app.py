import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import re

# 1. 페이지 설정 및 초기화
st.set_page_config(page_title="Broadcasting Master v750", layout="wide")
DB = 'stations.csv'
sd = st.session_state

def safe_float(val, default=0.0):
    try:
        if not val or str(val).strip() == "": return default
        return float(val)
    except: return default

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

def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        df['이름'] = df['이름'].str.strip()
        return df
    except: return pd.DataFrame(columns=['지역', '구분', '이름', '위도', '경도', '주소'], dtype=str)

if 'df' not in sd: sd.df = load_data()

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# 필수 변수 안전 초기화 (AttributeError 방지)
defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 75000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'last_clicked_nm': None, 'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "중계소"
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# 🔥 [원클릭 이동 로직] 표 클릭 시 즉시 데이터 로드 및 위치 이동
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    if idx < len(disp_df):
        sel = disp_df.iloc[idx]
        if sd.last_clicked_nm != sel['이름']:
            sd.last_clicked_nm, sd.target_nm, sd.m_mode = sel['이름'], sel['이름'], "정보 수정"
            # 텍스트 데이터 로드 (고정)
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            for s in SL: sd[f"ch_{s}"] = str(sel[s])
            # 위치 이동
            sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), str(sel['주소'])
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

# [CSS]
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; margin-bottom: 2px !important; font-size: 17px !important; background-color: #f8f9fa !important; border: 2px solid #adb5bd !important; border-radius: 10px !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    div.element-container:has(.btn-delete-final) + div.element-container button { background-color: #d32f2f !important; color: white !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("🔍 위치 제어")
    s_addr = st.text_input("주소 또는 좌표 검색", key="top_search")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색") and s_addr:
            try:
                if ',' in s_addr:
                    lat, lon = map(float, s_addr.split(','))
                    sd.base_center, sd.in_t_la, sd.in_t_lo = [lat, lon], lat, lon
                else:
                    loc = Nominatim(user_agent="b_v750").geocode(s_addr)
                    if loc: sd.base_center, sd.in_t_la, sd.in_t_lo, sd.in_v_addr = [loc.latitude, loc.longitude], loc.latitude, loc.longitude, loc.address
                sd.map_key += 1; st.rerun()
            except: st.error("검색 실패")
    with c2:
        if st.button("↩️ 복구"):
            if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()
    if st.button("🧭 내 위치"):
        gps = get_geolocation()
        if gps: p = [gps['coords']['latitude'], gps['coords']['longitude']]; sd.base_center, sd.in_t_la, sd.in_t_lo = p, p[0], p[1]; sd.map_key += 1; st.rerun()

    st.subheader("📋 정보 원클릭 복사")
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)
    st.code(sd.in_v_addr if sd.in_v_addr else "위치를 지정하세요", language=None)

    st.divider()
    # 🔥 [복구] 관제 필터 상단 배치
    st.header("⚙️ 관제 및 관리")
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))

    with st.expander("🏷️ 지역 명칭 일괄 변경"):
        old_reg = st.selectbox("바꿀 대상", regs, key="old_reg_sel")
        new_reg = st.text_input("새 이름", value="서울", key="new_reg_in")
        if st.button("🚀 변경 실행"):
            sd.history.append(sd.df.copy()); sd.df['지역'] = sd.df['지역'].replace(old_reg, new_reg); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    st.header("🎯 위치 지정 및 등록")
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치 지정"):
        sd.m_mode, sd.target_nm = "신규 등록", None; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치 지정"):
        sd.m_mode = "정보 수정"; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 등록"):
        f_nm = sd.get('in_v_nm', "")
        f_reg = sd.get('in_reg_direct', "") if (sd.m_mode == "정보 수정" or sd.get('in_reg_box') == "+ 직접 입력") else sd.get('in_reg_box')
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 시설 등록")
        st.selectbox("지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("새 지역 명칭", key="in_reg_direct")
        st.text_input("시설 이름", key="in_v_nm"); st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 확인", key="in_v_addr")
    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        if sd.target_nm:
            st.text_input("시설 이름", key="in_v_nm")
            st.text_input("지역 명칭 변경", key="in_reg_direct") 
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
            st.text_area("주소 수정", key="in_v_addr")
        else: st.warning("목록에서 대상을 선택하세요.")
    elif sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            st.markdown('<span class="btn-delete-final"></span>', unsafe_allow_html=True)
            if st.button("🚨 시설 삭제 실행"):
                sd.history.append(sd.df.copy()); sd.df = sd.df[sd.df['이름'] != del_t]; sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); sd.target_nm = None; st.success("삭제 완료!"); st.rerun()

    # 🔥 [디자인 재현] 채널 설정 그리드 (image_0b9989.png)
    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider()
        st.markdown("### 📺 물리 채널 설정")
        # DTV 섹션
        st.markdown("## 📡 DTV")
        d1, d2, d3 = st.columns(3)
        with d1: st.text_input(SL_DTV[0], key=f"ch_{SL_DTV[0]}")
        with d2: st.text_input(SL_DTV[1], key=f"ch_{SL_DTV[1]}")
        with d3: st.text_input(SL_DTV[2], key=f"ch_{SL_DTV[2]}")
        d4, d5 = st.columns(2)
        with d4: st.text_input(SL_DTV[3], key=f"ch_{SL_DTV[3]}")
        with d5: st.text_input(SL_DTV[4], key=f"ch_{SL_DTV[4]}")
        
        # UHD 섹션
        st.markdown("## ✨ UHD")
        u1, u2, u3 = st.columns(3)
        with u1: st.text_input(SL_UHD[0], key=f"ch_{SL_UHD[0]}")
        with u2: st.text_input(SL_UHD[1], key=f"ch_{SL_UHD[1]}")
        with u3: st.text_input(SL_UHD[2], key=f"ch_{SL_UHD[2]}")
        u4, u5 = st.columns(2)
        with u4: st.text_input(SL_UHD[3], key=f"ch_{SL_UHD[3]}")
        with u5: st.text_input(SL_UHD[4], key=f"ch_{SL_UHD[4]}")

# ---------------------------------------------------------
# 본문: 지도 (2단 팝업)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

with st.container():
    css_inj = "<style>.map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; } .map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; } .map-crosshair::before { top: 18px; left: -10px; width: 56px; height: 2px; } .map-crosshair::after { left: 18px; top: -10px; height: 56px; width: 2px; } .leaflet-popup-content-wrapper { min-width: 380px !important; }</style><div class='map-crosshair'></div>"
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_inj))
    for _, r in disp_df.iterrows():
        is_edit = (sd.m_mode in ["정보 수정", "데이터 삭제"] and sd.target_nm == r['이름'])
        lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_edit else (safe_float(r['위도']), safe_float(r['경도']))
        if lat == 0.0: continue
        color = 'red' if r['구분'] == '송신소' else 'blue'
        
        # 팝업 2단 구성 (image_0b2222.png 재현)
        dtv_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_DTV])
        uhd_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; color:#007bff;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_UHD])
        p_html = f"<div style='width:350px; font-family:sans-serif; font-size:15px; line-height:1.5;'><div style='font-size:20px; font-weight:bold; color:#333; border-bottom:2px solid #ccc; padding-bottom:5px; margin-bottom:10px;'>[{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span></div><div style='color:#666; margin-bottom:12px; font-size:13px;'>{r['주소']}</div><div style='display:flex; justify-content:space-between;'><div style='width:48%;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px;'>📡 DTV</div>{dtv_list}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:12px;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px; color:#007bff;'>✨ UHD</div>{uhd_list}</div></div></div>"
        folium.Marker([lat, lon], icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:3px 8px;background:white;border:2px solid {color};border-radius:5px;color:{color};font-weight:bold;white-space:nowrap;transform:translate(15px,-30px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=400)).add_to(m)
    
    map_data = st_folium(m, use_container_width=True, height=750, key=f"map_{sd.map_key}", returned_objects=["center"])
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# 3. 데이터 현황판 (상시 노출)
st.subheader("📊 데이터 현황")
def style_df(row): return [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'}; color: {'#cc0000' if row['구분']=='송신소' else '#0066cc'}; text-align: center; font-weight: bold;" for _ in row]
if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    st.dataframe(view_df[['지역', '구분', '이름'] + SL + ['구글어스 좌표', '주소']].style.apply(style_df, axis=1), use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")
st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
