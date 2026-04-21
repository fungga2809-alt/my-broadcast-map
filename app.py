import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# 앱 설정 및 제목
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

# [프리미엄 UI 디자인 CSS]
st.markdown("""
    <style>
    /* 전체 폰트 및 배경 정돈 */
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; font-size: 16px; }
    
    /* 사이드바 버튼 이쁘게 만들기 */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #d1d1d1;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
        background-color: #fffafa;
    }
    
    /* 표 헤더 정돈 */
    th {
        background-color: #f0f2f6 !important;
        color: #31333f !important;
        text-align: center !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: 전문가용 도구함
# ---------------------------------------------------------
with st.sidebar:
    st.title("📡 관제 도구")
    
    # 지역 선택
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    sd.sel_reg = st.selectbox("🗺️ 관리 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    # 버튼 가로 배치 (image_9180bc 디자인 개선)
    col1, col2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    
    if col1.button("🎯 내 위치"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]; sd.map_key += 1; st.rerun()
        
    if col2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()
    
    # 시설 관리 모드
    m_mode = st.radio("📍 모드 설정", ["새로 등록", "정보 수정"], horizontal=True)
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    target_nm = st.selectbox("수정 시설 선택", f_df['이름'].tolist()) if m_mode == "정보 수정" and not f_df.empty else None
    
    # 필드 초기화 및 세팅
    if m_mode == "정보 수정" and target_nm:
        row = sd.df[sd.df['이름'] == target_nm].iloc[0]
        i_reg, i_cat, i_nm = row['지역'], row['구분'], row['이름']
        la_v, lo_v = float(row['위도']), float(row['경도'])
        for s in SL: sd[f"v_{s}"] = str(row[s])
    else:
        i_reg, i_cat, i_nm = sd.sel_reg if sd.sel_reg != "전체" else "부산광역시", "중계소", ""
        la_v, lo_v = sd.center[0], sd.center[1]
        for s in SL: sd[f"v_{s}"] = ""

    # 입력 폼 정돈
    new_reg = st.text_input("지역명", value=i_reg)
    new_cat = st.radio("구분", ["송신소", "중계소"], index=0 if i_cat=="송신소" else 1, horizontal=True)
    new_nm = st.text_input("시설명", value=i_nm)
    new_la = st.number_input("위도", value=la_v, format="%.6f")
    new_lo = st.number_input("경도", value=lo_v, format="%.6f")

    st.write("📺 **채널 정보**")
    ch_cols = st.columns(2)
    new_ch_vals = []
    for i, s in enumerate(SL):
        new_ch_vals.append(ch_cols[i%2].text_input(s, value=sd.get(f"v_{s}", "")))

    if st.button("✅ 데이터 저장"):
        if new_nm:
            sd.history.append(sd.df.copy())
            v = [new_reg, new_cat, new_nm] + new_ch_vals + [str(new_la), str(new_lo), ""]
            if m_mode == "정보 수정" and target_nm:
                idx = sd.df[sd.df['이름'] == target_nm].index[0]; sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

# ---------------------------------------------------------
# [3] 본문: 지도 및 데이터 통합 대시보드
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")

# 지도 영역
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="font-size: 10pt; color: {color}; font-weight: bold; background: white; padding: 2px 5px; border: 1px solid {color}; border-radius: 4px; white-space: nowrap;">{r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

st_folium(m, width="100%", height=500, key=f"map_v90_{sd.map_key}")

# [4] 데이터 관리 현황 표
st.divider()
st.subheader("📊 데이터 관리 현황")

# 표 중앙 정렬 및 가독성 설정
config = {col: st.column_config.Column(alignment="center") for col in CL}
def style_row(row):
    color = 'color: #e63946;' if row['구분'] == '송신소' else 'color: #1d3557;'
    return [f"{color} font-weight: 500;" for _ in row]

styled_df = disp_df[CL].style.apply(style_row, axis=1)

event = st.dataframe(
    styled_df, 
    use_container_width=True, 
    on_select="rerun", 
    selection_mode="single-row", 
    hide_index=True, 
    column_config=config,
    key="main_table"
)

# 표 클릭 시 이동
if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    sd.center = [float(sel_row['위도']), float(sel_row['경도'])]
    sd.map_key += 1; st.rerun()

st.download_button("📥 전체 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
