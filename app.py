import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Infrastructure Control", layout="wide")
DB = 'stations.csv'

# [컬럼 정의]
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
defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'history': [], 'map_key': 0, 'sel_reg': "전체"}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

# [UI 디자인 CSS]
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; font-size: 16px; }
    .stButton > button { width: 100%; border-radius: 8px; border: 1px solid #d1d1d1; }
    th { background-color: #f0f2f6 !important; text-align: center !important; font-weight: bold !important; }
    /* 입력창 그룹 강조 */
    .channel-group { background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: 전문가용 도구함
# ---------------------------------------------------------
with st.sidebar:
    st.title("📡 관제 도구")
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    sd.sel_reg = st.selectbox("🗺️ 관리 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    col1, col2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    if col1.button("🎯 내 위치"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]; sd.map_key += 1; st.rerun()
    if col2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    m_mode = st.radio("📍 모드 설정", ["새로 등록", "정보 수정"], horizontal=True)
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    target_nm = st.selectbox("수정 시설 선택", f_df['이름'].tolist()) if m_mode == "정보 수정" and not f_df.empty else None
    
    if m_mode == "정보 수정" and target_nm:
        row = sd.df[sd.df['이름'] == target_nm].iloc[0]
        i_reg, i_cat, i_nm = row['지역'], row['구분'], row['이름']
        la_v, lo_v = float(row['위도']), float(row['경도'])
        current_vals = {s: str(row[s]) for s in SL}
    else:
        i_reg, i_cat, i_nm = sd.sel_reg if sd.sel_reg != "전체" else "부산광역시", "중계소", ""
        la_v, lo_v = sd.center[0], sd.center[1]
        current_vals = {s: "" for s in SL}

    new_reg = st.text_input("지역명", value=i_reg)
    new_cat = st.radio("구분", ["송신소", "중계소"], index=0 if i_cat=="송신소" else 1, horizontal=True)
    new_nm = st.text_input("시설명", value=i_nm)
    new_la = st.number_input("위도", value=la_v, format="%.6f")
    new_lo = st.number_input("경도", value=lo_v, format="%.6f")

    # [수정포인트] 채널 정보를 DTV와 UHD로 명확히 구분
    st.subheader("📺 채널 정보 설정")
    
    all_new_vals = {}
    
    st.info("🔹 **Digital TV (DTV)**")
    for s in SL_DTV:
        all_new_vals[s] = st.text_input(f"{s}", value=current_vals[s], key=f"dtv_{s}")
        
    st.info("🔸 **UHD TV**")
    for s in SL_UHD:
        all_new_vals[s] = st.text_input(f"{s}", value=current_vals[s], key=f"uhd_{s}")

    if st.button("✅ 데이터 저장"):
        if new_nm:
            sd.history.append(sd.df.copy())
            v = [new_reg, new_cat, new_nm] + [all_new_vals[s] for s in SL] + [str(new_la), str(new_lo), ""]
            if m_mode == "정보 수정" and target_nm:
                idx = sd.df[sd.df['이름'] == target_nm].index[0]; sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

# ---------------------------------------------------------
# [3] 본문 및 하단 표 (기존 v90의 안정된 기능 유지)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="font-size: 10pt; color: {color}; font-weight: bold; background: white; padding: 2px 5px; border: 1px solid {color}; border-radius: 4px; white-space: nowrap;">{r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

st_folium(m, width="100%", height=500, key=f"map_v91_{sd.map_key}")

st.divider()
st.subheader("📊 데이터 관리 현황")
config = {col: st.column_config.Column(alignment="center") for col in CL}
def style_row(row):
    color = 'color: #e63946;' if row['구분'] == '송신소' else 'color: #1d3557;'
    return [f"{color} font-weight: 500;" for _ in row]

styled_df = disp_df[CL].style.apply(style_row, axis=1)
event = st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    sd.center = [float(sel_row['위도']), float(sel_row['경도'])]
    sd.map_key += 1; st.rerun()

st.download_button("📥 전체 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
