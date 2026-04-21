import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Master", layout="wide")
DB = 'stations.csv'

# [채널 및 컬럼 정의]
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '메모']

sd = st.session_state

# [1] 데이터 로드 로직
def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        df = df.reindex(columns=CL, fill_value="")
        return df
    except:
        return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd or '지역' not in sd.df.columns:
    sd.df = load_data()

# 세션 상태 초기화
defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'layer': "위성+도로", 'last_target': None, 'last_mode': "새로 등록", 
            'history': [], 'map_key': 0, 'sel_reg': "전체"}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"i_{s}" not in sd: sd[f"i_{s}"] = ""

# [CSS 주입] 표의 헤더와 셀을 강제로 중앙 정렬하는 초강력 코드
st.markdown("""
    <style>
    /* 1. 표 전체 글자 크기 및 폰트 설정 */
    [data-testid="stDataFrame"] {
        font-family: 'Malgun Gothic', sans-serif !important;
    }
    /* 2. 헤더(th)와 셀(td) 모두 가리지 않고 중앙 정렬 */
    th, td {
        text-align: center !important;
        vertical-align: middle !important;
    }
    /* 3. 사이드바는 깔끔하게 유지 */
    .stSidebar {
        font-size: 15px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바 및 지도 출력 (기존 기능 유지)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 지역 및 도구")
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    new_reg = st.selectbox("🗺️ 관리 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)
    
    if new_reg != sd.sel_reg:
        sd.sel_reg = new_reg
        reg_df = sd.df[sd.df['지역'] == new_reg] if new_reg != "전체" else sd.df
        if not reg_df.empty:
            sd.center = [float(reg_df.iloc[0]['위도']), float(reg_df.iloc[0]['경도'])]
            sd.map_key += 1
        st.rerun()

    # ... (기존 GPS 및 버튼 로직 동일)
    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    # ... (데이터 저장 로직 생략, 기존 코드 활용)

# 지도 출력
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
# ... (마커 표시 로직 동일)
st_folium(m, width="100%", height=500, key=f"map_v88_{sd.map_key}")

# ---------------------------------------------------------
# [4] 하단: 데이터 관리 현황 (전체 중앙 정렬의 핵심!)
# ---------------------------------------------------------
st.divider()
st.markdown(f"### 📊 <span style='color:red'>송신소</span> / <span style='color:blue'>중계소</span> 데이터 관리 현황", unsafe_allow_html=True)

def apply_final_style(df):
    def style_logic(row):
        # 송신소=적색, 중계소=청색 + [중요] 모든 셀을 중앙 정렬(text-align: center)
        text_color = 'color: red;' if row['구분'] == '송신소' else 'color: blue;'
        base_style = f"{text_color} text-align: center; vertical-align: middle;"
        
        styles = [base_style] * len(row)
        
        # 채널 번호만 24px로 키우고 굵게!
        large_font_style = base_style + " font-size: 24px; font-weight: bold;"
        
        for i, col_name in enumerate(df.columns):
            if col_name in SL:
                styles[i] = large_font_style
        return styles
    
    # 1. 본문 데이터 스타일링
    styler = df.style.apply(style_logic, axis=1)
    
    # 2. [비장의 무기] 제목(Header)까지 강제로 중앙 정렬 및 폰트 설정
    styler = styler.set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-size', '18px'), ('font-weight', 'bold')]},
        {'selector': 'td', 'props': [('text-align', 'center')]}
    ])
    return styler

# 스타일이 적용된 데이터프레임
styled_df = apply_final_style(disp_df[CL])

# [팁] config_dict에서도 center를 한 번 더 강조합니다.
config_dict = {col: st.column_config.TextColumn(col, alignment="center") for col in CL}

event = st.dataframe(
    styled_df, 
    use_container_width=True, 
    on_select="rerun", 
    selection_mode="single-row", 
    hide_index=True, 
    column_config=config_dict, 
    key="main_table"
)

# 시설 클릭 시 이동 로직 (기존 동일)
if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    sd.center = [float(sel_row['위도']), float(sel_row['경도'])]
    sd.map_key += 1; st.rerun()

st.download_button(label="📥 전체 데이터 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv', mime='text/csv')
