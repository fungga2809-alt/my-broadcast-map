import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import math
import re
from branca.element import Template, MacroElement

# 1. 페이지 설정 및 초기화
st.set_page_config(page_title="Broadcasting Master v840", layout="wide")
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

def get_dist_bearing(lat1, lon1, lat2, lon2):
    if lat1 == 0.0 or lat2 == 0.0: return 9999, ""
    R = 6371
    dLat, dLon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    dist = R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))
    y = math.sin(math.radians(lon2-lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2-lon1))
    brng = (math.degrees(math.atan2(y, x)) + 360) % 360
    dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return round(dist, 1), f"{dirs[int((brng + 22.5) // 45 % 8)]} ({int(brng)}°)"

def generate_kml(df):
    kml_pts = ""
    for _, r in df.iterrows():
        lat, lon = safe_float(r['위도']), safe_float(r['경도'])
        if lat == 0.0: continue
        desc = f"DTV: {r['SBS']},{r['KBS2']},{r['KBS1']},{r['EBS']},{r['MBC']} | UHD: {r['SBS(U)']},{r['KBS2(U)']},{r['KBS1(U)']},{r['EBS(U)']},{r['MBC(U)']}"
        kml_pts += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><description>{desc}</description><Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{kml_pts}</Document></kml>'

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

defaults = {
    'base_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 140000,
    'sel_reg': "전체", 'm_mode': "신규 등록", 'target_nm': None, 
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'history': [], 
    'last_clicked_nm': None, 'in_v_nm': "", 'in_reg_direct': "", 'in_v_cat': "중계소",
    'ref_loc': None, 'map_layer': "위성+이름", 'ch_search': "", 'prev_sel': []
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# 표 체크 선택/해제 감지
if 'main_table' in sd:
    curr_sel = sd.main_table.get("selection", {}).get("rows", [])
    if curr_sel != sd.prev_sel:
        sd.prev_sel = curr_sel
        if curr_sel:
            idx = curr_sel[0]
            temp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
            if sd.ch_search:
                mask = temp_df[SL].apply(lambda x: x.str.contains(sd.ch_search, na=False, case=False)).any(axis=1)
                temp_df = temp_df[mask]
            if sd.ref_loc:
                temp_df['거리(km)'] = temp_df.apply(lambda r: get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))[0], axis=1)
                temp_df = temp_df.sort_values('거리(km)')

            if idx < len(temp_df):
                sel = temp_df.iloc[idx]
                sd.target_nm = sel['이름']
                sd.m_mode = "정보 수정"
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
                for s in SL: sd[f"ch_{s}"] = str(sel[s])
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(sel['위도']), safe_float(sel['경도']), str(sel['주소'])
                sd.base_center = [sd.in_t_la, sd.in_t_lo]
        else:
            sd.target_nm = None
            sd.m_mode = "신규 등록"
        sd.map_key += 1; st.rerun()

# CSS 스타일 (표 글자 크기 및 행 높이 강제 주입)
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; font-size: 14pt !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; margin-bottom: 2px !important; font-size: 17px !important; background-color: #f8f9fa !important; border: 2px solid #adb5bd !important; border-radius: 10px !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
    div.element-container:has(.btn-delete-final) + div.element-container button { background-color: #d32f2f !important; color: white !important; font-weight: bold !important; }
    /* 🔥 표 전체 글자 크기 및 행 높이 조절 */
    [data-testid="stDataFrame"] { font-size: 13pt !important; }
    [data-testid="stDataFrame"] td { height: 45px !important; vertical-align: middle !important; }
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], index=["일반", "위성", "위성+이름"].index(sd.map_layer), horizontal=True)
    st.divider()
    st.header("🔍 기준점 설정")
    s_addr = st.text_input("주소/좌표 검색", key="top_search")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 검색") and s_addr:
            try:
                if ',' in s_addr: lat, lon = map(float, s_addr.split(',')); sd.base_center, sd.in_t_la, sd.in_t_lo, sd.ref_loc = [lat, lon], lat, lon, [lat, lon]
                else:
                    loc = Nominatim(user_agent="b_v840").geocode(s_addr)
                    if loc: sd.base_center, sd.in_t_la, sd.in_t_lo, sd.ref_loc = [loc.latitude, loc.longitude], loc.latitude, loc.longitude, [loc.latitude, loc.longitude]
                sd.map_key += 1; st.rerun()
            except: st.error("실패")
    with c2:
        if st.button("↩️ 복구") and sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()
    if st.button("🧭 내 위치 (기준점)"):
        gps = get_geolocation()
        if gps: p = [gps['coords']['latitude'], gps['coords']['longitude']]; sd.base_center, sd.in_t_la, sd.in_t_lo, sd.ref_loc = p, p[0], p[1], p; sd.map_key += 1; st.rerun()
    
    st.code(get_google_format(sd.in_t_la, sd.in_t_lo), language=None)

    st.divider()
    st.header("⚙️ 관제 관리")
    regs = sorted(sd.df['지역'].unique().tolist())
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs, index=(regs.index(sd.sel_reg)+1 if sd.sel_reg in regs else 0))
    sd.ch_search = st.text_input("🔎 주파수 역검색", value=sd.ch_search)

    st.divider()
    st.header("🎯 위치 지정")
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치"):
        sd.m_mode, sd.target_nm = "신규 등록", None; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치"):
        sd.m_mode = "정보 수정"; p = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.in_t_la, sd.in_t_lo, sd.base_center = p[0], p[1], p; st.rerun()
    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 등록"):
        f_nm, f_reg = sd.get('in_v_nm', ""), sd.get('in_reg_direct', "") if (sd.m_mode == "정보 수정" or sd.get('in_reg_box') == "+ 직접 입력") else sd.get('in_reg_box')
        if f_nm and f_reg:
            sd.history.append(sd.df.copy())
            v = [f_reg, sd.get('in_v_cat', "중계소"), f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.get('in_v_addr', "")]
            if sd.m_mode == "정보 수정" and sd.target_nm: sd.df.loc[sd.df['이름'] == sd.target_nm] = v; sd.target_nm = f_nm
            else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    m_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    sd.m_mode = st.radio("🛠️ 작업 모드", m_opts, index=m_opts.index(sd.m_mode), horizontal=True)

    if sd.m_mode == "신규 등록":
        st.selectbox("지역 선택", ["+ 직접 입력"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 직접 입력": st.text_input("새 지역 명칭", key="in_reg_direct")
        st.text_input("시설 이름", key="in_v_nm"); st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 확인", key="in_v_addr")
    elif sd.m_mode == "정보 수정":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            sel_target = st.selectbox("수정 대상 시설", curr_names, index=(curr_names.index(sd.target_nm) if sd.target_nm in curr_names else 0))
            if sd.target_nm != sel_target:
                sd.target_nm = sel_target
                row = sd.df[sd.df['이름'] == sel_target].iloc[0]
                sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = row['이름'], row['지역'], row['구분']
                sd.in_t_la, sd.in_t_lo, sd.in_v_addr = safe_float(row['위도']), safe_float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.base_center = [sd.in_t_la, sd.in_t_lo]; sd.map_key += 1; st.rerun()
            st.text_input("시설 이름 수정", key="in_v_nm"); st.text_input("지역 명칭 수정", key="in_reg_direct") 
            st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True); st.text_area("주소 수정", key="in_v_addr")
    elif sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            st.markdown('<span class="btn-delete-final"></span>', unsafe_allow_html=True)
            if st.button("🚨 시설 삭제 실행"):
                sd.history.append(sd.df.copy()); sd.df = sd.df[sd.df['이름'] != del_t]; sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); sd.target_nm = None; st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider(); st.header("📺 물리 채널 설정")
        st.markdown("### 📡 DTV")
        d1, d2, d3 = st.columns(3)
        with d1: st.text_input(SL_DTV[0], key=f"ch_{SL_DTV[0]}")
        with d2: st.text_input(SL_DTV[1], key=f"ch_{SL_DTV[1]}")
        with d3: st.text_input(SL_DTV[2], key=f"ch_{SL_DTV[2]}")
        d4, d5 = st.columns(2)
        with d4: st.text_input(SL_DTV[3], key=f"ch_{SL_DTV[3]}")
        with d5: st.text_input(SL_DTV[4], key=f"ch_{SL_DTV[4]}")
        st.markdown("### ✨ UHD")
        u1, u2, u3 = st.columns(3)
        with u1: st.text_input(SL_UHD[0], key=f"ch_{SL_UHD[0]}")
        with u2: st.text_input(SL_UHD[1], key=f"ch_{SL_UHD[1]}")
        with u3: st.text_input(SL_UHD[2], key=f"ch_{SL_UHD[2]}")
        u4, u5 = st.columns(2)
        with u4: st.text_input(SL_UHD[3], key=f"ch_{SL_UHD[3]}")
        with u5: st.text_input(SL_UHD[4], key=f"ch_{SL_UHD[4]}")

# ---------------------------------------------------------
# 본문: 지도
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
if sd.ch_search:
    mask = disp_df[SL].apply(lambda x: x.str.contains(sd.ch_search, na=False, case=False)).any(axis=1)
    disp_df = disp_df[mask]

if sd.ref_loc:
    dists, brngs = [], []
    for _, r in disp_df.iterrows():
        d, b = get_dist_bearing(sd.ref_loc[0], sd.ref_loc[1], safe_float(r['위도']), safe_float(r['경도']))
        dists.append(d); brngs.append(b)
    disp_df['거리(km)'], disp_df['방향'] = dists, brngs
    disp_df = disp_df.sort_values('거리(km)')

with st.container():
    crosshair_macro = MacroElement()
    crosshair_macro._template = Template("""
        {% macro html(this, kwargs) %}
        <style>
        .map-crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }
        .map-crosshair::before, .map-crosshair::after { content: ''; position: absolute; background: #ff4b4b; }
        .map-crosshair::before { top: 17px; left: -10px; width: 56px; height: 2px; }
        .map-crosshair::after { left: 17px; top: -10px; height: 56px; width: 2px; }
        .leaflet-popup-content-wrapper { min-width: 380px !important; }
        </style>
        <div class="map-crosshair"></div>
        {% endmacro %}
    """)

    l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
    tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='G')
    m.get_root().add_child(crosshair_macro)
    if sd.ref_loc: folium.Marker(sd.ref_loc, icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)

    for _, r in disp_df.iterrows():
        is_target = (sd.target_nm == r['이름'])
        lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_target else (safe_float(r['위도']), safe_float(r['경도']))
        if lat == 0.0: continue
        color = 'red' if r['구분'] == '송신소' else 'blue'
        if is_target: folium.Circle(location=[lat, lon], radius=(10000 if '송신소' in r['구분'] else 2000), color=color, fill=True, fill_opacity=0.2, weight=3).add_to(m)
        dtv_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_DTV])
        uhd_list = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; color:#007bff;'><span><b>{s}</b></span><span>: {r[s]}</span></div>" for s in SL_UHD])
        p_html = f"<div style='width:350px; font-family:sans-serif; font-size:15px; line-height:1.5;'><div style='font-size:20px; font-weight:bold; color:#333; border-bottom:2px solid #ccc; padding-bottom:5px; margin-bottom:10px;'>[{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span></div><div style='color:#666; margin-bottom:12px; font-size:13px;'>{r['주소']}</div><div style='display:flex; justify-content:space-between;'><div style='width:48%;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px;'>📡 DTV</div>{dtv_list}</div><div style='width:48%; border-left:1px solid #ddd; padding-left:12px;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px; color:#007bff;'>✨ UHD</div>{uhd_list}</div></div></div>"
        folium.Marker([lat, lon], icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:3px 8px;background:white;border:2px solid {color};border-radius:5px;color:{color};font-weight:bold;white-space:nowrap;transform:translate(15px,-30px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker([lat, lon], icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=400)).add_to(m)
    
    map_data = st_folium(m, use_container_width=True, height=900, key=f"map_{sd.map_key}", returned_objects=["center"])
    if map_data and map_data.get("center"): sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

# ---------------------------------------------------------
# 🔥 [수정] 13pt 글꼴 및 행 높이 확장 적용 표
# ---------------------------------------------------------
st.subheader("📊 데이터 현황")

def style_df(row): 
    bg = '#fff0f0' if row['구분']=='송신소' else '#f0f7ff'
    fg = '#cc0000' if row['구분']=='송신소' else '#0066cc'
    # font-size: 13pt 와 padding 추가하여 행 높이 확보
    return [f"background-color: {bg}; color: {fg}; text-align: center; font-weight: bold; font-size: 13pt; padding: 10px 0px;" for _ in row]

if not disp_df.empty:
    view_df = disp_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    display_cols = ['지역', '구분', '이름'] + SL + (['거리(km)', '방향'] if sd.ref_loc else []) + ['구글어스 좌표', '주소']
    
    styled_df = view_df[display_cols].style.apply(style_df, axis=1)
    styled_df = styled_df.set_properties(**{'text-align': 'center'})
    
    # 전문가님 요청 픽셀(px) 세팅
    cfg = {
        '지역': st.column_config.TextColumn(width=80),
        '구분': st.column_config.TextColumn(width=80),
        '이름': st.column_config.TextColumn(width=100),
        '구글어스 좌표': st.column_config.TextColumn(width=250),
        '주소': st.column_config.TextColumn(width=350),
    }
    for s in SL_DTV: cfg[s] = st.column_config.TextColumn(width=50)
    for s in SL_UHD: cfg[s] = st.column_config.TextColumn(width=70)
    if sd.ref_loc: cfg.update({'거리(km)': st.column_config.NumberColumn(width=60), '방향': st.column_config.TextColumn(width=60)})

    # 표가 너무 작게 느껴지지 않도록 use_container_width=True 로 변경하여 전체 너비 활용
    st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table", column_config=cfg)

c_dl1, c_dl2 = st.columns(2)
with c_dl1: st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv', use_container_width=True)
with c_dl2: st.download_button("🌍 KML 다운로드", data=generate_kml(sd.df).encode('utf-8'), file_name='stations.kml', mime='application/vnd.google-earth.kml+xml', use_container_width=True)
