import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from branca.element import Template, MacroElement
from streamlit_gsheets import GSheetsConnection 
import time

# 1. 페이지 설정 및 가로 꽉 참 설정
st.set_page_config(page_title="Broadcasting Master v985.8", layout="wide")

# [V984 오리지널 디자인 CSS]
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

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

# [초기화 방지] 데이터 로드 로직
def load_db():
    if sd.get('gs_sync_on', False):
        try:
            st.cache_data.clear() 
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(ttl=0).astype(str).fillna("")
            for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True).replace('nan', '')
            return df
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Quota exceeded" in err_str:
                st.warning("⚠️ 구글 서버 요청 한도 초과(1분에 60회). 1분 뒤 자동으로 해제됩니다.")
            else:
                st.error(f"❌ 구글 시트 연결 실패. 로컬 데이터를 불러옵니다.")
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        for s in SL: df[s] = df[s].str.replace(r'\.0$', '', regex=True)
        return df
    except: return pd.DataFrame(columns=CL, dtype=str)

# [영구 저장] 데이터 저장 로직
def save_db(df):
    df.to_csv(DB, index=False, encoding='utf-8-sig') 
    if sd.get('gs_sync_on', False):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(data=df) 
            st.cache_data.clear() 
            st.sidebar.success("✅ 구글 시트 영구 저장 완료! (새로고침해도 유지됨)")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Quota exceeded" in err_str:
                st.warning("⚠️ 과도한 트래픽으로 구글 서버 일시 차단됨. 잠시 후 다시 시도해주세요.")
            else:
                st.error(f"❌ 시트 저장 실패: {e}")
    else: st.toast("💾 로컬 CSV 업데이트 완료!")

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

if 'df' not in sd:
    sd.df = load_db()

defaults = {
    'gs_sync_on': False, 'map_layer': "위성+이름", 'sel_reg': "전체", 'ch_search': "",
    'base_center': [35.1796, 129.0756], 'crosshair_center': [35.1796, 129.0756], 'base_zoom': 14, 'map_key': 7000,
    'm_mode': "신규 등록", 'target_nm': None,
    'in_v_nm': "", 'in_reg_box': "+ 새 지역 추가", 'in_reg_direct': "", 'in_v_cat': "송신소",
    'in_t_la': 35.1796, 'in_t_lo': 129.0756, 'in_v_addr': "", 'prev_sel': []
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
            for s in SL: sd[f"ch_{s}"] = str(sel[s])
            sd.base_center = [sd.in_t_la, sd.in_t_lo]
            sd.crosshair_center = [sd.in_t_la, sd.in_t_lo]
            sd.map_key += 1; st.rerun()

with st.sidebar:
    st.header("⚙️ 관제 설정")
    
    with st.expander("📁 로컬 CSV 파일 업데이트"):
        uploaded_file = st.file_uploader("stations.csv 업로드", type="csv")
        if uploaded_file:
            sd.df = pd.read_csv(uploaded_file, dtype=str).fillna("")
            save_db(sd.df); st.rerun()

    sync_toggle = st.toggle("🌐 구글 시트 실시간 연동", value=sd.gs_sync_on)
    if sync_toggle != sd.gs_sync_on:
        sd.gs_sync_on = sync_toggle
        if sd.gs_sync_on: 
            st.cache_data.clear() 
            sd.df = load_db()
        st.rerun()
        
    if sd.gs_sync_on:
        if st.button("🔄 시트 최신 데이터 불러오기"):
            st.cache_data.clear()
            sd.df = load_db()
            st.rerun()

    sd.map_layer = st.radio("🗺️ 레이어", ["일반", "위성", "위성+이름"], horizontal=True)
    st.divider()
    
    regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 지역 필터", ["전체"] + regs)
    sd.ch_search = st.text_input("🔎 통합 검색", placeholder="시설명, 지역, 물리번호 등")

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
            sd.map_key += 1
            st.toast("🎯 마커가 조준경 위치로 이동했습니다. 완료 후 [✅ 데이터 저장]을 꼭 눌러주세요!")
            st.rerun()

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
            save_db(sd.df); sd.target_nm = f_nm; st.rerun()

    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], index=["신규 등록", "정보 수정", "데이터 삭제"].index(sd.m_mode), horizontal=True)

    st.divider(); st.markdown("### 📝 시설 정보 입력")
    if sd.m_mode == "신규 등록":
        st.selectbox("지역 선택", ["+ 새 지역 추가"] + regs, key="in_reg_box")
        if sd.in_reg_box == "+ 새 지역 추가": st.text_input("새 지역 명칭 입력", key="in_reg_direct")
    else:
        st.text_input("지역 이름 수정", key="in_reg_direct")
    
    st.text_input("시설 이름", key="in_v_nm")
    st.radio("구분", ["송신소", "중계소"], key="in_v_cat", horizontal=True)
    
    st.text_area("주소 확인/수정", key="in_v_addr")
    st.caption("📋 클릭하여 주소 복사 (아래 칸 클릭)")
    st.code(sd.in_v_addr, language="text")
    st.caption("📍 현재 조준경 좌표 복사")
    st.code(f"{sd.in_t_la}, {sd.in_t_lo}", language="text")

    if sd.m_mode == "데이터 삭제":
        curr_names = (sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg])['이름'].tolist()
        if curr_names:
            del_t = st.selectbox("삭제 시설 선택", curr_names)
            if st.button("🚨 시설 삭제 실행"):
                sd.df = sd.df[sd.df['이름'] != del_t]
                save_db(sd.df); sd.target_nm = None; st.rerun()

    st.divider(); st.markdown("### 📡 물리 채널 설정")
    for section, icons, list_ch in [("DTV", "📡", SL_DTV), ("UHD", "✨", SL_UHD)]:
        st.write(f"{icons} {section}")
        cols = st.columns(3)
        for i, s in enumerate(list_ch):
            with cols[i % 3]: st.text_input(s, key=f"ch_{s}", label_visibility="collapsed")

# [메인 화면]
st.title(f"📡 {sd.sel_reg} 방송 관제 센터")
res_df = get_filtered_sorted_df(sd.df, sd.sel_reg, sd.ch_search)

l_map = {"일반": "m", "위성": "s", "위성+이름": "y"}
tile_url = f'https://mt1.google.com/vt/lyrs={l_map[sd.map_layer]}&hl=ko&x={{x}}&y={{y}}&z={{z}}'
m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles=tile_url, attr='Google')

cross_html = MacroElement()
cross_html._template = Template("""{% macro html(this, kwargs) %}<style>.crosshair { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 1000; pointer-events: none; }.crosshair::before, .crosshair::after { content: ''; position: absolute; background: #ff4b4b; }.crosshair::before { top: 18px; left: -10px; width: 60px; height: 4px; }.crosshair::after { left: 18px; top: -10px; height: 60px; width: 4px; }</style><div class="crosshair"></div>{% endmacro %}""")
m.get_root().add_child(cross_html)

for _, r in res_df.iterrows():
    is_t = (sd.target_nm == r['이름'])
    lat, lon = (safe_float(sd.in_t_la), safe_float(sd.in_t_lo)) if is_t else (safe_float(r['위도']), safe_float(r['경도']))
    if lat == 0.0: continue
    color = 'red' if r['구분'] == '송신소' else 'blue'
    
    dtv_tags = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'><span><b>{s}</b></span><span>: {sd.get(f'ch_{s}', r[s]) if is_t else r[s]}</span></div>" for s in SL_DTV])
    uhd_tags = "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:3px; color:#007bff;'><span><b>{s}</b></span><span>: {sd.get(f'ch_{s}', r[s]) if is_t else r[s]}</span></div>" for s in SL_UHD])
    
    p_html = f"""<div style='width:350px; font-family:sans-serif; font-size:15px; line-height:1.5;'>
        <div style='font-size:20px; font-weight:bold; color:#333; border-bottom:2px solid #ccc; padding-bottom:5px; margin-bottom:10px;'>
            [{r['구분']}] <span style='background-color:#ffff00; padding:2px 5px;'>{r['이름']}</span>
        </div>
        <div style='color:#666; margin-bottom:12px; font-size:13px;'>{r['주소']}</div>
        <div style='display:flex; justify-content:space-between;'>
            <div style='width:48%;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px;'>📡 DTV</div>{dtv_tags}</div>
            <div style='width:48%; border-left:1px solid #ddd; padding-left:12px;'><div style='font-weight:bold; border-bottom:1px solid #ddd; margin-bottom:5px; color:#007bff;'>✨ UHD</div>{uhd_tags}</div>
        </div>
    </div>"""
    folium.Marker([lat, lon], icon=folium.Icon(color=color), popup=folium.Popup(p_html, max_width=400)).add_to(m)

# 🚩 [세로 크기 확장]: 지도의 높이를 950px로 키웠습니다.
map_res = st_folium(m, use_container_width=True, height=950, key=f"map_{sd.map_key}")
if map_res and map_res.get("center"):
    sd.crosshair_center = [map_res["center"]["lat"], map_res["center"]["lng"]]

st.subheader("📊 데이터 현황")
if not res_df.empty:
    view_df = res_df.copy()
    view_df['구글어스 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
    def style_row(row):
        bg = '#fff0f0' if row['구분']=='송신소' else '#f0f7ff'
        fg = '#cc0000' if row['구분']=='송신소' else '#0066cc'
        return [f"background-color: {bg}; color: {fg}; font-weight: bold; border-bottom: 1px solid #ccc;" for _ in row]
    
    styled = view_df[CL + ['구글어스 좌표']].style.apply(style_row, axis=1)
    st.dataframe(styled, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

    st.divider()
    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 현재 리스트 CSV 저장", data=res_df.to_csv(index=False, encoding='utf-8-sig'), file_name="stations.csv", use_container_width=True)
    with c2: 
        kml_str = f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        for _, r in res_df.iterrows():
            kml_str += f"<Placemark><name>[{r['구분']}] {r['이름']}</name><Point><coordinates>{r['경도']},{r['위도']},0</coordinates></Point></Placemark>"
        kml_str += "</Document></kml>"
        st.download_button("🌍 구글어스용 KML 저장", data=kml_str, file_name='stations.kml', use_container_width=True)
