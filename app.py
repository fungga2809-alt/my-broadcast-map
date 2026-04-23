import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Infrastructure Master", layout="wide")
DB = 'stations.csv'

# [정의] 채널 및 컬럼
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

sd = st.session_state

# [도구] 구글용 DMS 통합 좌표 생성 함수
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

# [1] 데이터 로드
def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except:
        return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

# 세션 상태 초기화
defaults = {
    'center': [35.1796, 129.0756], 'zoom': 14, 't_la': None, 't_lo': None, 
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "신규 등록", 'target_nm': None, 'last_loaded_nm': None, 'v_addr': ""
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [CSS] UI 스타일
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-size: 18px !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; }
    .leaflet-popup-content { font-size: 14px !important; width: 420px !important; line-height: 1.6; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: 관제 도구
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    existing_regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + existing_regs)

    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색", key="addr_input")
    c_loc = st.columns([1, 1, 1], gap="small")
    geolocator = Nominatim(user_agent="broadcasting_v295")

    with c_loc[0]:
        if st.button("📍검색"):
            if search_addr:
                try:
                    loc = geolocator.geocode(search_addr)
                    if loc:
                        sd.center, sd.t_la, sd.t_lo, sd.v_addr = [loc.latitude, loc.longitude], loc.latitude, loc.longitude, loc.address
                        sd.m_mode, sd.map_key = "신규 등록", sd.map_key + 1; st.rerun()
                except: st.error("오류")
    with c_loc[1]:
        if st.button("🎯위치"):
            gps = get_geolocation()
            if gps and 'coords' in gps:
                p = [gps['coords']['latitude'], gps['coords']['longitude']]
                sd.center, sd.t_la, sd.t_lo = p, p[0], p[1]
                try:
                    rev = geolocator.reverse(f"{p[0]}, {p[1]}")
                    if rev: sd.v_addr = rev.address
                except: pass
                sd.m_mode, sd.map_key = "신규 등록", sd.map_key + 1; st.rerun()
    with c_loc[2]:
        if st.button("↩️복구"):
            if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    if st.button("🎯 지도 중앙을 등록 위치로 지정", type="primary"):
        sd.t_la, sd.t_lo = sd.center[0], sd.center[1]
        try:
            rev = geolocator.reverse(f"{sd.t_la}, {sd.t_lo}")
            if rev: sd.v_addr = rev.address
        except: pass
        sd.m_mode = "신규 등록"; st.rerun()

    st.divider()
    st.subheader("📋 정보 원클릭 복사")
    cur_la = sd.t_la if sd.t_la is not None else sd.center[0]
    cur_lo = sd.t_lo if sd.t_lo is not None else sd.center[1]
    st.code(get_google_format(cur_la, cur_lo), language=None)
    st.code(sd.v_addr if sd.v_addr else "위치를 지정하세요", language=None)

    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], horizontal=True)

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 시설 등록")
        reg_opts = ["+ 직접 입력"] + existing_regs
        sel_reg = st.selectbox("1. 지역 선택", reg_opts)
        final_reg = st.text_input("📝 새 지역 명칭", "") if sel_reg == "+ 직접 입력" else sel_reg
        v_nm = st.text_input("2. 시설 이름")
        v_cat = st.radio("3. 시설 구분", ["송신소", "중계소"], horizontal=True)
        
        addr_api_query = st.text_input("4. 주소 검색(API)", "")
        if st.button("🏠 주소 자동 찾기"):
            if addr_api_query:
                try:
                    loc = geolocator.geocode(addr_api_query)
                    if loc:
                        sd.v_addr, sd.t_la, sd.t_lo = loc.address, loc.latitude, loc.longitude
                        sd.center = [loc.latitude, loc.longitude]; sd.map_key += 1; st.rerun()
                except: st.error("검색 실패")
        
        sd.v_addr = st.text_area("5. 주소 확인/수정", value=sd.v_addr)
        
        c_la, c_lo = st.columns(2)
        sd.t_la = c_la.number_input("6. 위도(Dec)", value=float(sd.t_la if sd.t_la is not None else sd.center[0]), format="%.6f")
        sd.t_lo = c_lo.number_input("7. 경도(Dec)", value=float(sd.t_lo if sd.t_lo is not None else sd.center[1]), format="%.6f")

    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        names = sd.df[sd.df['지역'] == sd.sel_reg]['이름'].tolist() if sd.sel_reg != "전체" else sd.df['이름'].tolist()
        if names:
            sd.target_nm = st.selectbox("대상 선택", names)
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            v_nm, final_reg = st.text_input("시설 이름", value=row['이름']), st.text_input("지역 명칭", value=row['지역'])
            v_cat = st.radio("구분", ["송신소", "중계소"], index=0 if row['구분']=="송신소" else 1, horizontal=True)
            sd.v_addr = st.text_area("주소 수정", value=str(row['주소']))
            
            if sd.last_loaded_nm != sd.target_nm:
                sd.t_la, sd.t_lo = float(row['위도']), float(row['경도'])
                sd.last_loaded_nm = sd.target_nm
                
            c_la, c_lo = st.columns(2)
            sd.t_la = c_la.number_input("위도(Dec)", value=float(sd.t_la), format="%.6f")
            sd.t_lo = c_lo.number_input("경도(Dec)", value=float(sd.t_lo), format="%.6f")
        else: st.warning("데이터 없음"); final_reg, v_cat, v_nm = "", "중계소", ""

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider()
        st.info("📺 물리 채널 설정")
        d_cols = st.columns(3); st.markdown("**📡 DTV**")
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        u_cols = st.columns(3); st.markdown("**✨ UHD**")
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

        if st.button("✅ 데이터 저장"):
            if v_nm and final_reg:
                sd.history.append(sd.df.copy())
                save_la = str(sd.t_la if sd.t_la is not None else sd.center[0])
                save_lo = str(sd.t_lo if sd.t_lo is not None else sd.center[1])
                v = [final_reg, v_cat, v_nm] + [sd[f"ch_{s}"] for s in SL] + [save_la, save_lo, sd.v_addr]
                if sd.m_mode == "정보 수정": sd.df.loc[sd.df['이름'] == sd.target_nm] = v
                else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                sd.t_la, sd.t_lo, sd.v_addr = None, None, ""; st.success("저장 완료!"); st.rerun()

# ---------------------------------------------------------
# [3] 본문: 지도 및 데이터 현황
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제 마스터")

disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

map_container = st.container()
with map_container:
    crosshair_html = """
    <style>
    .map-crosshair {
        position: absolute; top: 50%; left: 50%;
        margin-left: -20px; margin-top: -20px;
        width: 40px; height: 40px;
        border: 2px solid #ff4b4b; border-radius: 50%;
        z-index: 9999; pointer-events: none;
    }
    .map-crosshair::before { content: ''; position: absolute; top: 18px; left: -10px; width: 56px; height: 2px; background: #ff4b4b; }
    .map-crosshair::after { content: ''; position: absolute; left: 18px; top: -10px; height: 56px; width: 2px; background: #ff4b4b; }
    </style>
    <div class="map-crosshair"></div>
    """
    m = folium.Map(location=sd.center, zoom_start=sd.zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(crosshair_html))

    for _, r in disp_df.iterrows():
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        dt_pop, uh_pop = "|".join([f"{s}:{r[s]}" for s in SL_DTV]), "|".join([f"{s}:{r[s]}" for s in SL_UHD])
        p_html = f"<div style='width:400px; padding: 5px;'><b style='font-size:18px;'>[{r['구분']}] {r['이름']}</b><br><span style='color:gray;'>{r['주소']}</span><hr><b>📡 DTV:</b> {dt_pop}<br><b>✨ UHD:</b> {uh_pop}</div>"
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=500)).add_to(m)

    if sd.m_mode == "신규 등록" and sd.t_la:
        folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='star', prefix='fa')).add_to(m)

    # [핵심] returned_objects를 제한하여 클릭 이벤트를 원천 차단
    map_data = st_folium(
        m, 
        use_container_width=True, 
        height=700, 
        key=f"map_v295_{sd.map_key}",
        returned_objects=["center", "zoom"]
    )

# 지도 중심 이동 및 확대 배율 저장 (클릭 이벤트는 이제 무시됨)
if map_data:
    if map_data.get("center"): sd.center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom"): sd.zoom = map_data["zoom"]

st.divider()
st.subheader("📊 데이터 현황")
view_df = disp_df.copy()
view_df['통합 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
event = st.dataframe(view_df[['지역', '구분', '이름'] + SL + ['통합 좌표', '주소']], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]; sel = disp_df.iloc[idx]
    if sd.target_nm != sel['이름']:
        sd.center, sd.m_mode, sd.target_nm = [float(sel['위도']), float(sel['경도'])], "정보 수정", sel['이름']
        sd.v_addr, sd.t_la, sd.t_lo = str(sel['주소']), float(sel['위도']), float(sel['경도']); sd.map_key += 1; st.rerun()

st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
