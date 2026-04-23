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
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '메모']

sd = st.session_state

# [1] 데이터 로드
def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except:
        return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

# 세션 상태 초기화
defaults = {
    'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "새로 등록", 'target_nm': None, 'last_loaded_nm': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# ---------------------------------------------------------
# [CSS] 전문가용 버튼 커스텀 설정 (여기서 숫자를 조절하세요!)
# ---------------------------------------------------------
st.markdown(f"""
    <style>
    html, body, [class*="css"] {{ font-size: 18px !important; }}
    th {{ text-align: center !important; background-color: #f0f2f6 !important; font-size: 18px !important; font-weight: bold !important; }}
    
    /* [버튼 커스텀 영역] */
    .stButton > button {{ 
        width: 100%; 
        border-radius: 10px;        /* 테두리 곡률 */
        font-weight: bold; 
        font-size: 16px !important; /* 버튼 글자 크기 */
        white-space: nowrap !important; 
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 0.7rem 0.5rem !important; /* 버튼 위아래/좌우 여백 (숫자 키우면 버튼이 커짐) */
        min-height: 50px;           /* 버튼 최소 높이 */
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
    }}
    
    .leaflet-popup-content {{ font-size: 14px !important; width: 250px !important; line-height: 1.6; }}
    [data-testid="stDataFrame"] td {{ text-align: center !important; }}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: 버튼 위치 제어 (Columns 비율)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    sd.sel_reg = st.selectbox("🗺️ 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색", key="addr_input")
    
    # 1. 위치 검색 버튼 (상단 단독 배치 또는 비율 조정 가능)
    if st.button("📍 위치 검색"):
        if search_addr:
            try:
                geolocator = Nominatim(user_agent="broadcasting_master_v127")
                loc = geolocator.geocode(search_addr)
                if loc:
                    sd.center = [loc.latitude, loc.longitude]
                    sd.t_la, sd.t_lo = loc.latitude, loc.longitude
                    sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
                    sd.map_key += 1; st.rerun()
            except: st.error("검색 오류")

    # 2. 내 위치 & 되돌리기 버튼 (가로 위치 및 크기 비율 조정)
    # [1, 1.2] 숫자를 [1, 1]로 바꾸면 똑같은 크기, [0.8, 1.2]로 바꾸면 되돌리기가 더 길어짐
    c1, c2 = st.columns([1, 1.2], gap="small") 
    with c1:
        if st.button("🎯 내 위치"):
            gps = get_geolocation()
            my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
            if my_p: 
                sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]
                sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
                sd.map_key += 1; st.rerun()
    with c2:
        if st.button("↩️ 되돌리기"):
            if sd.history: 
                sd.df = sd.history.pop()
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                st.rerun()

    st.divider()

    # 모드 설정 및 데이터 로드 (v122 안정 로직)
    sd.m_mode = st.radio("📍 모드 설정", ["새로 등록", "정보 수정"], index=0 if sd.m_mode == "새로 등록" else 1, horizontal=True)
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    names = f_df['이름'].tolist()
    
    if sd.m_mode == "정보 수정" and names:
        target_idx = names.index(sd.target_nm) if sd.target_nm in names else 0
        sd.target_nm = st.selectbox("수정 대상 선택", names, index=target_idx)
        if sd.last_loaded_nm != sd.target_nm:
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = row['지역'], row['구분'], row['이름']
            if sd.t_la is None: sd.t_la, sd.t_lo = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"ch_{s}"] = str(row[s])
            sd.last_loaded_nm = sd.target_nm
    else:
        if sd.last_loaded_nm != "NEW":
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = sd.sel_reg if sd.sel_reg != "전체" else "부산광역시", "중계소", ""
            for s in SL: sd[f"ch_{s}"] = "" 
            sd.last_loaded_nm = "NEW"

    st.text_input("지역 명칭", key="v_reg")
    sd["v_cat"] = st.radio("시설 구분", ["송신소", "중계소"], index=0 if sd.get("v_cat")=="송신소" else 1)
    st.text_input("송신소/중계소 이름", key="v_nm")
    
    # 좌표 입력
    disp_la = float(sd.t_la if sd.t_la is not None else sd.center[0])
    disp_lo = float(sd.t_lo if sd.t_lo is not None else sd.center[1])
    la_v = st.number_input("위도", value=disp_la, format="%.6f", key="inp_la")
    lo_v = st.number_input("경도", value=disp_lo, format="%.6f", key="inp_lo")
    if la_v != disp_la or lo_v != disp_lo:
        sd.t_la, sd.t_lo = la_v, lo_v

    # 채널 설정 (v70 그룹화)
    st.subheader("📺 물리 채널 설정")
    st.info("📡 **DTV 채널**")
    d_cols = st.columns(3)
    for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
    st.warning("✨ **UHD 채널**")
    u_cols = st.columns(3)
    for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

    if st.button("✅ 데이터 저장"):
        if sd["v_nm"]:
            sd.history.append(sd.df.copy())
            v = [sd["v_reg"], sd["v_cat"], sd["v_nm"]] + [sd[f"ch_{s}"] for s in SL] + [str(sd.t_la), str(sd.t_lo), ""]
            if sd.m_mode == "정보 수정" and sd.target_nm:
                idx = sd.df[sd.df['이름'] == sd.target_nm].index[0]; sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.target_nm, sd.last_loaded_nm = None, None, None, None
            st.success("저장 완료!"); st.rerun()

# ---------------------------------------------------------
# [3] 본문: 지도 및 데이터 현황 (디자인 유지)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        dt_t = " | ".join([f"{s}:{r[s]}" for s in SL_DTV])
        uh_t = " | ".join([f"{s}:{r[s]}" for s in SL_UHD])
        p_html = f"<div style='width:250px;'><b>[{r['구분']}] {r['이름']}</b><br><hr>DTV: {dt_t}<br>UHD: {uh_t}</div>"
        
        l_html = f'''<div style="display: inline-block; padding: 4px 10px; background-color: white; border: 2px solid {color}; border-radius: 6px; color: {color}; font-size: 10pt; font-weight: bold; white-space: nowrap; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); transform: translate(15px, -35px); pointer-events: none;">[{r["구분"]}] {r["이름"]}</div>'''
        folium.Marker(p, icon=folium.DivIcon(html=l_html, icon_anchor=(0,0))).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=300)).add_to(m)
    except: pass

if sd.t_la is not None:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='star', prefix='fa')).add_to(m)

map_data = st_folium(m, width="100%", height=700, key=f"map_v127_{sd.map_key}")

# v70 순정 클릭 로직 (안정 버전)
if map_data.get("last_clicked"):
    cla, clo = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if sd.t_la != cla:
        sd.t_la, sd.t_lo = cla, clo
        sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
        sd.map_key += 1; st.rerun()

# [하단 데이터 표]
st.divider()
def style_table(row):
    if row['구분'] == '송신소':
        return ['background-color: #ffebee; color: #d32f2f; font-weight: bold; text-align: center;'] * len(row)
    return ['background-color: #e3f2fd; color: #1976d2; text-align: center;'] * len(row)

styled_df = disp_df[CL].style.apply(style_table, axis=1)
column_cfg = {"이름": st.column_config.TextColumn("📡 송신소/중계소 이름", alignment="center", width="medium")}
for c in CL: 
    if c != "이름": column_cfg[c] = st.column_config.TextColumn(c, alignment="center")

event = st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=column_cfg, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    if sd.target_nm != sel_row['이름']:
        sd.center, sd.m_mode, sd.target_nm, sd.last_loaded_nm = [float(sel_row['위도']), float(sel_row['경도'])], "정보 수정", sel_row['이름'], None
        sd.t_la, sd.t_lo = None, None
        sd.map_key += 1; st.rerun()

st.download_button("📥 전체 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
