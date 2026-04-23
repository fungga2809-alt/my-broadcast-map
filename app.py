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

# 세션 상태 초기화 (v70 순정 방식 최적화)
defaults = {
    'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "새로 등록", 'target_nm': None, 'last_loaded_nm': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [CSS] 최신 스타일 디자인
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-size: 18px !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    .leaflet-popup-content { font-size: 14px !important; width: 250px !important; line-height: 1.6; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: v70 레이아웃 및 시스템
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    sd.sel_reg = st.selectbox("🗺️ 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    # 검색 및 내 위치
    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색", key="addr_input")
    if st.button("📍 위치 검색"):
        if search_addr:
            try:
                geolocator = Nominatim(user_agent="broadcasting_v121")
                loc = geolocator.geocode(search_addr)
                if loc:
                    sd.center = [loc.latitude, loc.longitude]
                    sd.t_la, sd.t_lo = loc.latitude, loc.longitude
                    sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
                    sd.map_key += 1; st.rerun()
            except: st.error("검색 오류")

    c1, c2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    if c1.button("🎯 내 위치"):
        if my_p: 
            sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]
            sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
            sd.map_key += 1; st.rerun()
    if c2.button("↩️ 되돌리기"):
        if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()

    # 모드 및 데이터 로드
    sd.m_mode = st.radio("📍 모드 설정", ["새로 등록", "정보 수정"], index=0 if sd.m_mode == "새로 등록" else 1, horizontal=True)
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    names = f_df['이름'].tolist()
    
    if sd.m_mode == "정보 수정" and names:
        target_idx = names.index(sd.target_nm) if sd.target_nm in names else 0
        sd.target_nm = st.selectbox("수정 대상 선택", names, index=target_idx)
        
        if sd.last_loaded_nm != sd.target_nm:
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = row['지역'], row['구분'], row['이름']
            # 수정 모드 진입 시 마커 클릭/검색 좌표가 없다면 시설 좌표 사용
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
    
    # 좌표 입력 (v121 핵심: 세션 우선 순위 조정)
    disp_la = float(sd.t_la if sd.t_la is not None else sd.center[0])
    disp_lo = float(sd.t_lo if sd.t_lo is not None else sd.center[1])
    
    new_la = st.number_input("위도", value=disp_la, format="%.6f")
    new_lo = st.number_input("경도", value=disp_lo, format="%.6f")
    
    # 지도를 건드리지 않고 숫자를 직접 칠 때만 업데이트
    if new_la != disp_la or new_lo != disp_lo:
        sd.t_la, sd.t_lo = new_la, new_lo

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
# [3] 본문: 지도 제어 (v70 순정 & 마커 이동 자유화)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        
        # v70 팝업창
        dt_t = " | ".join([f"{s}:{r[s]}" for s in SL_DTV])
        uh_t = " | ".join([f"{s}:{r[s]}" for s in SL_UHD])
        p_html = f"<div style='width:250px;'><b>[{r['구분']}] {r['이름']}</b><br><hr>DTV: {dt_t}<br>UHD: {uh_t}</div>"
        
        # 이름표 디자인
        l_html = f'''<div style="display: inline-block; padding: 4px 10px; background-color: white; border: 2px solid {color}; border-radius: 6px; color: {color}; font-size: 10pt; font-weight: bold; white-space: nowrap; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); transform: translate(15px, -35px); pointer-events: none;">[{r["구분"]}] {r["이름"]}</div>'''
        folium.Marker(p, icon=folium.DivIcon(html=l_html, icon_anchor=(0,0))).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, max_width=300)).add_to(m)
    except: pass

# 녹색 마커 (t_la 기준 - 이동의 주인공)
if sd.t_la is not None:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='star', prefix='fa')).add_to(m)

# 지도 출력 (v121: 클릭 신호를 즉각적으로 처리)
map_data = st_folium(m, width="100%", height=700, key=f"map_v121_{sd.map_key}")

# [지능형 클릭 감지] 마커 근처 클릭 vs 빈 땅 클릭
if map_data.get("last_clicked"):
    cla, clo = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    
    # 1. 주변 100m 이내 시설 검색
    match = disp_df[(disp_df['위도'].astype(float).sub(cla).abs() < 0.001) & (disp_df['경도'].astype(float).sub(clo).abs() < 0.001)]
    
    if not match.empty: # 기존 시설 클릭 시
        sel_row = match.iloc[0]
        if sd.target_nm != sel_row['이름']:
            sd.m_mode, sd.target_nm, sd.last_loaded_nm = "정보 수정", sel_row['이름'], None
            sd.t_la, sd.t_lo = None, None # 기존 시설 선택 시엔 녹색 마커 해제
            sd.center = [float(sel_row['위도']), float(sel_row['경도'])]
            st.rerun()
    else: # 빈 땅 클릭 시 ➡️ 무조건 녹색 마커 이동 (자유도 확보)
        sd.t_la, sd.t_lo = cla, clo
        sd.m_mode, sd.target_nm, sd.last_loaded_nm = "새로 등록", None, "NEW"
        st.rerun()

# ---------------------------------------------------------
# [4] 하단: 데이터 관리 현황
# ---------------------------------------------------------
st.divider()
st.subheader("📊 데이터 관리 현황")

def style_row(row):
    if row['구분'] == '송신소':
        return ['background-color: #ffebee; color: #d32f2f; font-weight: bold; text-align: center;'] * len(row)
    return ['background-color: #e3f2fd; color: #1976d2; text-align: center;'] * len(row)

styled_df = disp_df[CL].style.apply(style_row, axis=1)

event = st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    if sd.target_nm != sel_row['이름']:
        sd.center, sd.m_mode, sd.target_nm, sd.last_loaded_nm = [float(sel_row['위도']), float(sel_row['경도'])], "정보 수정", sel_row['이름'], None
        sd.t_la, sd.t_lo = None, None
        sd.map_key += 1; st.rerun()

st.download_button("📥 전체 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
