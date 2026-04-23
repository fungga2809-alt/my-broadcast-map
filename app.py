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
    
    lat_dms = to_dms(lat, True)
    lon_dms = to_dms(lon, False)
    if lat_dms and lon_dms:
        return f"{lat_dms} {lon_dms}"
    return ""

# [1] 데이터 로드 및 세션 최적화
def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except:
        return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()
else:
    if '주소' not in sd.df.columns:
        if '메모' in sd.df.columns: sd.df.rename(columns={'메모': '주소'}, inplace=True)
        sd.df = sd.df.reindex(columns=CL, fill_value="")

# 세션 상태 초기화
defaults = {
    'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
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
    th { text-align: center !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] { gap: 5px !important; }
    .leaflet-popup-content { font-size: 14px !important; width: 280px !important; line-height: 1.6; }
    /* 복사 가능 텍스트 스타일 */
    .copy-box { background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 14px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: 관제 도구
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    existing_regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + existing_regs, 
                             index=0 if sd.sel_reg == "전체" else (existing_regs.index(sd.sel_reg)+1 if sd.sel_reg in existing_regs else 0))

    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색", key="addr_input")
    c_loc = st.columns([1, 1, 1])
    with c_loc[0]:
        if st.button("📍검색"):
            if search_addr:
                try:
                    geolocator = Nominatim(user_agent="broadcasting_v175")
                    loc = geolocator.geocode(search_addr)
                    if loc:
                        sd.center, sd.t_la, sd.t_lo = [loc.latitude, loc.longitude], loc.latitude, loc.longitude
                        sd.m_mode, sd.target_nm, sd.last_loaded_nm = "신규 등록", None, "NEW"
                        sd.map_key += 1; st.rerun()
                except: st.error("오류")
    with c_loc[1]:
        if st.button("🎯위치"):
            gps = get_geolocation()
            my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
            if my_p: 
                sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]
                sd.m_mode, sd.target_nm, sd.last_loaded_nm = "신규 등록", None, "NEW"
                sd.map_key += 1; st.rerun()
    with c_loc[2]:
        if st.button("↩️복구"):
            if sd.history: 
                sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    sd.m_mode = st.radio("🛠️ 작업 모드", ["신규 등록", "정보 수정", "데이터 삭제"], horizontal=True)
    
    f_df_sb = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    names = f_df_sb['이름'].tolist()

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 등록")
        reg_opts = ["+ 직접 입력"] + existing_regs
        sel_reg_name = st.selectbox("지역 선택", reg_opts, index=reg_opts.index(sd.sel_reg) if sd.sel_reg in existing_regs else 0)
        final_reg = st.text_input("지역 명칭", "") if sel_reg_name == "+ 직접 입력" else sel_reg_name
        v_cat = st.radio("구분", ["송신소", "중계소"], horizontal=True)
        v_nm = st.text_input("시설 이름")
        
    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 정보 수정")
        if names:
            sd.target_nm = st.selectbox("수정 대상", names, index=names.index(sd.target_nm) if sd.target_nm in names else 0)
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            final_reg, v_cat, v_nm = st.text_input("지역", value=row['지역']), st.radio("구분", ["송신소", "중계소"], index=0 if row['구분']=="송신소" else 1, horizontal=True), st.text_input("시설 이름", value=row['이름'])
            if sd.last_loaded_nm != sd.target_nm:
                sd.t_la, sd.t_lo, sd.v_addr = float(row['위도']), float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.last_loaded_nm = sd.target_nm
        else: st.warning("데이터 없음"); final_reg, v_cat, v_nm = "", "중계소", ""

    elif sd.m_mode == "데이터 삭제":
        st.subheader("🗑️ 데이터 삭제")
        if names:
            del_target = st.selectbox("삭제 시설", names)
            if st.button("🚨 삭제 실행", type="primary"):
                sd.history.append(sd.df.copy()); sd.df = sd.df[sd.df['이름'] != del_target]; sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        # 좌표 입력 및 구글 지도용 원클릭 복사 칸
        st.subheader("📍 위치 좌표 (구글 지도용)")
        current_google_pos = get_google_format(sd.t_la if sd.t_la else sd.center[0], sd.t_lo if sd.t_lo else sd.center[1])
        st.code(current_google_pos, language=None)
        st.caption("위 박스 우측 버튼을 눌러 좌표를 한 번에 복사하세요.")

        c_la, c_lo = st.columns(2)
        sd.t_la = c_la.number_input("위도(Dec)", value=float(sd.t_la if sd.t_la is not None else sd.center[0]), format="%.6f")
        sd.t_lo = c_lo.number_input("경도(Dec)", value=float(sd.t_lo if sd.t_lo is not None else sd.center[1]), format="%.6f")
        
        st.subheader("📝 시설 주소")
        if sd.v_addr:
            st.code(sd.v_addr, language=None)
            st.caption("주소 복사용 박스")
        sd.v_addr = st.text_area("주소 입력/수정", value=sd.v_addr)

        st.info("📺 채널 설정")
        d_cols = st.columns(3); [d_cols[i%3].text_input(s, key=f"ch_{s}") for i, s in enumerate(SL_DTV)]
        u_cols = st.columns(3); [u_cols[i%3].text_input(s, key=f"ch_{s}") for i, s in enumerate(SL_UHD)]

        if st.button("✅ 데이터 저장"):
            if v_nm:
                sd.history.append(sd.df.copy())
                v = [final_reg, v_cat, v_nm] + [sd[f"ch_{s}"] for s in SL] + [str(sd.t_la), str(sd.t_lo), sd.v_addr]
                if sd.m_mode == "정보 수정" and sd.target_nm:
                    idx = sd.df[sd.df['이름'] == sd.target_nm].index[0]; sd.df.loc[idx] = v
                else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                sd.t_la, sd.t_lo, sd.target_nm, sd.last_loaded_nm, sd.v_addr = None, None, None, None, ""
                st.success("저장 완료!"); st.rerun()

# ---------------------------------------------------------
# [3] 본문: 지도 및 데이터 현황
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        google_pos = get_google_format(r['위도'], r['경도'])
        p_html = f"<div style='width:260px;'><b>[{r['구분']}] {r['이름']}</b><br><span style='color:gray; font-size:12px;'>{r['주소']}</span><hr><b>통합 좌표:</b><br>{google_pos}<br><b>DTV:</b> {'|'.join([f'{s}:{r[s]}' for s in SL_DTV])}</div>"
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);pointer-events:none;">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=300)).add_to(m)
    except: pass

if sd.t_la is not None: folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='star', prefix='fa')).add_to(m)

map_data = st_folium(m, width="100%", height=700, key=f"map_v175_{sd.map_key}")

if map_data.get("last_clicked"):
    cla, clo = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if sd.t_la != cla:
        sd.t_la, sd.t_lo = cla, clo
        sd.m_mode, sd.target_nm, sd.last_loaded_nm = "신규 등록", None, "NEW"; sd.map_key += 1; st.rerun()

st.divider()
st.subheader("📊 데이터 현황")

# 표 디자인 통합 (위도/경도 컬럼을 '통합 좌표' 하나로 합쳐서 표시)
view_df = disp_df.copy()
view_df['통합 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
# 표시용 컬럼 정의
V_CL = ['지역', '구분', '이름'] + SL + ['통합 좌표', '주소']

styled_df = view_df[V_CL].style.apply(lambda r: ['background-color:#ffebee;color:#d32f2f;font-weight:bold;text-align:center;']*len(r) if r['구분']=='송신소' else ['background-color:#e3f2fd;color:#1976d2;text-align:center;']*len(r), axis=1)
event = st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    sd.center, sd.m_mode, sd.target_nm, sd.last_loaded_nm = [float(sel_row['위도']), float(sel_row['경도'])], "정보 수정", sel_row['이름'], None
    sd.t_la, sd.t_lo = None, None; sd.map_key += 1; st.rerun()

st.download_button("📥 전체 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
