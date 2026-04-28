import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from branca.element import Template, MacroElement
from streamlit_gsheets import GSheetsConnection 
import time

# 1. 페이지 설정
st.set_page_config(page_title="Broadcasting Master v999", layout="wide")

# [디자인 CSS]
st.markdown("""<style>
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; max-width: 100% !important; }
    html, body, [class*="css"] { font-size: 18px !important; }
    [data-testid="stSidebar"] { background-color: #ced4da !important; }
    [data-testid="stSidebar"] div.stButton button { width: 100% !important; height: 50px !important; border-radius: 10px !important; border: 2px solid #adb5bd !important; }
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; }
</style>""", unsafe_allow_html=True)

sd = st.session_state
DB = 'stations.csv'

# [채널 목록 구성]
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL_DMB = ['DMB(SBS)', 'DMB(KBS)', 'DMB(MBC)']
SL_FM = ['KBS1-FM', 'KBS2-FM', 'KBS-Music', 'MBC-FM', 'MBC-AM', 'KNN-FM', 'EBS-FM', '교통방송', '국악방송', '불교방송', '평화방송', '기독교방송']

SL = SL_DTV + SL_UHD + SL_DMB + SL_FM
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [도구함]
def safe_float(val, default=0.0):
    try: return float(val) if val and str(val).strip() != "" else default
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

# [데이터 로직]
def load_db():
    if sd.get('gs_sync_on', False):
        try:
            st.cache_data.clear() 
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).astype(str).fillna("")
            for s in SL: 
                if s in df.columns: df[s] = df[s].str.replace(r'\.0$', '', regex=True).replace('nan', '')
            return df
        except: pass
    try:
        # 🚩 한글 깨짐 방지를 위해 utf-8-sig로 읽기 시도
        df = pd.read_csv(DB, dtype=str, encoding='utf-8-sig').fillna("")
        for s in SL: 
            if s in df.columns: df[s] = df[s].str.replace(r'\.0$', '', regex=True)
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

def save_db(df):
    # 🚩 [중요] 엑셀에서 한글 안 깨지게 utf-8-sig로 저장
    df.to_csv(DB, index=False, encoding='utf-8-sig') 
    if sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df) 
            st.cache_data.clear()
        except: pass

def get_filtered_sorted_df(df, sel_reg, search_query):
    res = df if sel_reg == "전체" else df[df['지역'] == sel_reg]
    if search_query:
        search_target = res['이름'] + " " + res['지역'] + " " + res['주소'] + " " + res[SL].apply(lambda x: ' '.join(x), axis=1)
        res = res[search_target.str.contains(search_query, case=False, na=False)]
    if not res.empty:
        sort_map = {'송신소': 1, '중계소': 2}
        res = res.copy()
        res['구분_순서'] = res['구분'].map(sort_map).fillna(3)
        res = res.sort_values(by=['지역', '구분_순서', '이름']).drop(columns=['구분_순서'])
    return res

if 'df' not in sd: sd.df = load_db()

# [기본 설정]
map_options = ["일반", "위성", "위성+이름"]
defaults = {
    'gs_sync_on': False, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
    'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 50000,
    'm_mode': "정보 수정", 'target_nm': None, 'in_v_nm': "", 'in_reg_box': "전체", 
    'in_reg_direct': "", 'in_v_cat': "송신소", 'in_t_la': 35.1796, 'in_t_lo': 129.0756, 
    'in_v_addr': "", 'prev_sel': [], 
    'msg_save': False, 'msg_extract': False, 'msg_dl': False
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [원클릭 표 선택]
if 'main_table' in sd and sd.main_table.get("selection", {}).get("rows"):
    idx = sd.main_table["selection"]["rows"][0]
    if sd.prev_sel != [idx]:
        sd.prev_sel = [idx]
        temp_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)
        if idx < len(temp_df):
            sel = temp_df.iloc[idx]
            sd.target_nm, sd.m_mode = sel['이름'], "정보 수정"
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_cat = sel['이름'], sel['지역'], sel['구분']
            sd.in_v_addr, sd.in_t_la, sd.in_t_lo = str(sel['주소']), safe_float(sel['위도']), safe_float(sel['경도'])
            for s in SL: sd[f"ch_{s}"] = str(sel[s]) if s in sel else ""
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 관제 설정")
    
    # 🚩 [알림 영역] 새로고침 후에도 유지되도록 설계
    if sd.msg_save:
        st.success("✅ 데이터 수정/저장이 완료되었습니다!"); sd.msg_save = False
    if sd.msg_extract:
        st.info("🎯 위치/주소 정보 자동 업데이트 완료!"); sd.msg_extract = False

    sync_toggle = st.toggle("🌐 구글 시트 실시간 연동", value=sd.gs_sync_on)
    if sync_toggle != sd.gs_sync_on:
        sd.gs_sync_on = sync_toggle
        if sd.gs_sync_on: sd.df = load_db()
        st.rerun()
        
    sd.map_layer = st.radio("🗺️ 레이어", map_options, index=map_options.index(sd.map_layer), horizontal=True)
    st.divider()
    
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 통합 검색", placeholder="시설명, 지역, 채널번호 등")

    st.caption("📋 클릭하여 주소 복사")
    st.code(sd.in_v_addr if sd.in_v_addr else "주소 정보 없음", language="text")
    st.caption("📍 현재 좌표 복사")
    st.code(f"{sd.in_t_la}, {sd.in_t_lo}", language="text")

    col_loc, col_rst = st.columns(2)
    with col_loc:
        if st.button("📍 내 위치 찾기"): sd.map_key += 1; st.rerun() 
    with col_rst:
        if st.button("🔄 입력 초기화"):
            sd.m_mode, sd.target_nm = "신규 등록", None
            sd.in_v_nm, sd.in_reg_direct, sd.in_v_addr = "", "", ""
            for s in SL: sd[f"ch_{s}"] = ""
            st.rerun()

    st.divider()
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 신규 위치 추출"):
        sd.m_mode, sd.target_nm = "신규 등록", None
        sd.in_t_la, sd.in_t_lo = sd.crosshair_center
        sd.base_center = [sd.crosshair_center[0], sd.crosshair_center[1]]
        try:
            loc = Nominatim(user_agent="b_master").reverse(f"{sd.in_t_la}, {sd.in_t_lo}")
            if loc: sd.in_v_addr = loc.address
        except: pass
        sd.map_key += 1; st.rerun()

    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 수정 위치 추출"):
        if sd.target_nm:
            sd.in_t_la, sd.in_t_lo = sd.crosshair_center
            sd.base_center = [sd.crosshair_center[0], sd.crosshair_center[1]]
            v = [sd.in_reg_direct, sd.in_v_cat, sd.target_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
            save_db(sd.df); sd.map_key += 1; sd.msg_extract = True; st.rerun()

    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
    if st.button("✅ 데이터 수정 저장"):
        f_nm = sd.in_v_nm
        f_reg = sd.in_reg_direct if sd.in_reg_box == "+ 새 지역 추가" else sd.in_reg_box
        if f_nm and f_reg:
            v = [f_reg, sd.in_v_cat, f_nm] + [sd.get(f"ch_{s}", "") for s in SL] + [str(sd.in_t_la), str(sd.in_t_lo), sd.in_v_addr]
            if sd.m_mode == "정보 수정" and sd.target_nm:
                sd.df.loc[sd.df['이름'] == sd.target_nm, CL] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            save_db(sd.df); sd.target_nm = f_nm; sd.msg_save = True; st.rerun()

    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], index=["신규 등록", "정보 수정", "데이터 삭제"].index(sd.m_mode), horizontal=True)

    if sd.m_mode == "데이터 삭제":
        st.divider(); st.markdown("### 🗑️ 시설 삭제 관리")
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제할 시설 선택", curr_names)
            st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
            if st.button("🚨 시설 영구 삭제 실행"):
                sd.df = sd.df[sd.df['이름'] != del_t]
                save_db(sd.df); sd.target_nm = None; st.toast(f"🗑️ {del_t} 삭제 완료", icon="✅")
                time.sleep(0.5); st.rerun()
    else:
        st.divider(); st.markdown("### 📝 시설 정보 입력")
        if sd.m_mode == "신규 등록":
            st.selectbox("지역 선택", ["+ 새 지역 추가"] + regs, key="in_reg_box")
            if sd.in_reg_box == "+ 새 지역 추가": st.text_input("새 지역 명칭 입력", key="in_reg_direct")
        else: st.text_input("지역 이름 수정", key="in_reg_direct")
        st.text_input("시설 이름", key="in_v_nm")
        st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
        st.text_area("주소 확인/수정", key="in_v_addr")

        with st.expander("📡 상세 채널(TV/DMB/FM) 설정"):
            for section, list_ch in [("📺 DTV", SL_DTV), ("✨ UHD", SL_UHD), ("📱 DMB", SL_DMB), ("📻 FM Radio", SL_FM)]:
                st.markdown(f"**{section}**")
                cols = st.columns(3)
                for i, s in enumerate(list_ch):
                    with cols[i % 3]: st.text_input(s, key=f"ch_{s}", label_visibility="visible", placeholder="채널/주파수")

# --- 메인 화면 ---
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")

# 🚩 다운로드 진행 안내 (토스트)
if sd.msg_dl:
    st.toast("💾 파일 생성이 완료되었습니다. 브라우저의 다운로드함을 확인하세요!", icon="📥")
    sd.msg_dl = False

res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)

l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='Google')
folium.plugins.LocateControl(auto_start=False).add_to(m)

cross_html = MacroElement()
cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.crosshair::before, .crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.crosshair::before { top: 18px; left: -10px; width: 60px; height: 4px; }.crosshair::after { left: 18px; top: -10px; height: 60px; width: 4px; }</style><div class="crosshair"></div>{% endmacro %}""")
m.get_root().add_child(cross_html)

for _, r in res_df.iterrows():
    is_t = (sd.target_nm == r['이름'])
    lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_t else (safe_float(r['위도']), safe_float(r['경도']))
    if lat == 0.0: continue
    color = 'red' if r['구분'] == '송신소' else 'blue'
    
    dtv_h = "".join([f"<div style='display:flex; justify-content:space-between;'><span><b>{s}</b></span><span>{r.get(s, '')}</span></div>" for s in SL_DTV])
    uhd_h = "".join([f"<div style='display:flex; justify-content:space-between; color:#007bff;'><span><b>{s}</b></span><span>{r.get(s, '')}</span></div>" for s in SL_UHD])
    dmb_h = "".join([f"<div style='display:flex; justify-content:space-between; border-bottom:1px dashed #eee; padding:2px 0;'><span><b>{s.split('(')[1][:-1]}</b></span><b>{r.get(s, '')}</b></div>" for s in SL_DMB if r.get(s, '')])
    fm_h = "".join([f"<div style='display:flex; justify-content:space-between; border-bottom:1px dashed #eee; padding:2px 0;'><span>{s}</span><b>{r.get(s, '')} MHz</b></div>" for s in SL_FM if r.get(s, '')])
    
    p_html = f"""<div style='width:350px; font-family:sans-serif; font-size:14px;'>
        <div style='font-size:18px; font-weight:bold; border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:8px;'>
            [{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span>
        </div>
        <div style='color:#666; margin-bottom:10px;'>{r['주소']}</div>
        <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
            <div style='width:48%;'><b>📡 DTV</b>{dtv_h}</div>
            <div style='width:48%; border-left:1px solid #ddd; padding-left:10px;'><b>✨ UHD</b>{uhd_h}</div>
        </div>
        <details style='cursor:pointer; background:#f0f7ff; padding:5px; border-radius:5px; margin-bottom:5px;'>
            <summary style='font-weight:bold; color:#0066cc;'>📱 DMB 채널 보기</summary>
            <div style='margin-top:8px; font-size:12px;'>{dmb_h if dmb_h else '제원 없음'}</div>
        </details>
        <details style='cursor:pointer; background:#eee; padding:5px; border-radius:5px;'>
            <summary style='font-weight:bold; color:#333;'>📻 FM 라디오 주파수 보기</summary>
            <div style='margin-top:8px; font-size:12px;'>{fm_h if fm_h else '제원 없음'}</div>
        </details>
    </div>"""
    folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=folium.Popup(p_html, max_width=400)).add_to(m)

map_res = st_folium(m, use_container_width=True, height=950, key=f"map_{sd.map_key}")
if map_res and map_res.get("center"):
    sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

# [데이터 현황 및 다운로드]
st.subheader("📊 데이터 현황 (기본 위치 정보)")
if not res_df.empty:
    view_df = res_df[['지역', '구분', '이름', '위도', '경도', '주소']].copy()
    view_df['구글어스 좌표'] = res_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    styled = view_df.style.apply(lambda row: [f"background-color: {'#fff0f0' if row['구분']=='송신소' else '#f0f7ff'}; color: {'#cc0000' if row['구분']=='송신소' else '#0066cc'}; font-weight: bold; border-bottom: 1px solid #ccc;" for _ in row], axis=1)
    st.dataframe(styled, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        # 🚩 CSV 다운로드 시 한글 깨짐 방지(utf-8-sig) 적용
        csv_data = res_df.to_csv(index=False, encoding='utf-8-sig')
        if st.download_button("📥 현재 리스트 CSV 저장", data=csv_data, file_name="stations.csv", use_container_width=True):
             sd.msg_dl = True # 알림 예약
    with c2: 
        kml_str = '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        for _, r in res_df.iterrows():
            kml_str += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><Point><coordinates>{r['경도']},{r['위도']},0</coordinates></Point></Placemark>"
        kml_str += "</Document></kml>"
        if st.download_button("🌍 구글어스용 KML 저장", data=kml_str, file_name="stations.kml", use_container_width=True):
             sd.msg_dl = True # 알림 예약
