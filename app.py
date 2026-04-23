import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

# [설정] 페이지 및 파일 경로
st.set_page_config(page_title="Broadcasting Infrastructure Master", layout="wide")
DB = 'stations.csv'

# [정의] 채널 및 컬럼 세팅
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '메모']

sd = st.session_state

# [1] 데이터 로드 및 초기화
def init_db():
    if not os.path.exists(DB):
        df_empty = pd.DataFrame(columns=CL)
        df_empty.to_csv(DB, index=False, encoding='utf-8-sig')

def load_data():
    try:
        if not os.path.exists(DB): return pd.DataFrame(columns=CL)
        df = pd.read_csv(DB, dtype=str).fillna("")
        # 필수 컬럼 보장
        for c in CL:
            if c not in df.columns: df[c] = ""
        return df[CL]
    except Exception as e:
        st.error(f"데이터 로딩 실패: {e}")
        return pd.DataFrame(columns=CL)

init_db()
if 'df' not in sd: sd.df = load_data()

# 세션 상태 초기화 (기본값 설정)
defaults = {
    'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "새로 등록", 'target_nm': None, 'last_loaded_nm': None
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

# 채널 입력 필드 초기화
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [CSS] UI 개선 (Streamlit 최신 버전 대응)
st.markdown("""
    <style>
    .stButton > button { 
        width: 100%; border-radius: 8px; font-weight: bold; height: 45px;
    }
    .leaflet-popup-content { font-size: 13px !important; line-height: 1.5; }
    [data-testid="stMetricValue"] { font-size: 20px; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바 관리
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 인프라 관리 도구")
    
    # 지역 필터링
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체", "부산광역시", "서울특별시"]
    sd.sel_reg = st.selectbox("🗺️ 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    # 위치 검색 (Nominatim)
    st.subheader("🔍 위치 검색")
    search_addr = st.text_input("주소 또는 시설명", key="addr_input", placeholder="예: 부산타워")
    if st.button("📍 검색 실행"):
        if search_addr:
            try:
                geolocator = Nominatim(user_agent="broadcasting_admin_v122")
                loc = geolocator.geocode(search_addr, timeout=10)
                if loc:
                    sd.center = [loc.latitude, loc.longitude]
                    sd.t_la, sd.t_lo = loc.latitude, loc.longitude
                    sd.map_key += 1
                    st.rerun()
                else: st.warning("결과를 찾을 수 없습니다.")
            except GeopyError: st.error("네트워크 오류")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎯 내 위치"):
            gps = get_geolocation()
            if gps and 'coords' in gps:
                lat, lon = gps['coords']['latitude'], gps['coords']['longitude']
                sd.center, sd.t_la, sd.t_lo = [lat, lon], lat, lon
                sd.map_key += 1; st.rerun()
    with c2:
        if st.button("↩️ 복구"):
            if sd.history:
                sd.df = sd.history.pop()
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                st.rerun()

    st.divider()
    
    # 입력 폼 모드 전환
    sd.m_mode = st.radio("🛠️ 편집 모드", ["새로 등록", "정보 수정"], horizontal=True)
    
    # 정보 로드 로직
    if sd.m_mode == "정보 수정" and not sd.df.empty:
        names = sd.df['이름'].tolist()
        sd.target_nm = st.selectbox("수정할 시설", names, index=names.index(sd.target_nm) if sd.target_nm in names else 0)
        
        if sd.last_loaded_nm != sd.target_nm:
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = row['지역'], row['구분'], row['이름']
            sd.t_la, sd.t_lo = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"ch_{s}"] = str(row[s])
            sd.last_loaded_nm = sd.target_nm
    else:
        if sd.last_loaded_nm != "NEW":
            sd["v_reg"] = sd.sel_reg if sd.sel_reg != "전체" else ""
            sd["v_nm"], sd["v_cat"] = "", "중계소"
            for s in SL: sd[f"ch_{s}"] = ""
            sd.last_loaded_nm = "NEW"

    # 세부 입력 UI
    st.text_input("📍 지역(시/군/구)", key="v_reg")
    sd["v_cat"] = st.radio("🏢 시설 구분", ["송신소", "중계소"], index=0 if sd.get("v_cat")=="송신소" else 1)
    st.text_input("📝 시설 명칭", key="v_nm")
    
    curr_la = st.number_input("위도(Lat)", value=float(sd.t_la or sd.center[0]), format="%.6f")
    curr_lo = st.number_input("경도(Lon)", value=float(sd.t_lo or sd.center[1]), format="%.6f")
    sd.t_la, sd.t_lo = curr_la, curr_lo

    with st.expander("📺 물리 채널 설정", expanded=True):
        st.caption("DTV 채널")
        d_cols = st.columns(3)
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        st.caption("UHD 채널")
        u_cols = st.columns(3)
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

    if st.button("💾 시설 정보 저장", type="primary"):
        if sd["v_nm"] and sd["v_reg"]:
            sd.history.append(sd.df.copy())
            new_data = [sd["v_reg"], sd["v_cat"], sd["v_nm"]] + [sd[f"ch_{s}"] for s in SL] + [f"{sd.t_la:.6f}", f"{sd.t_lo:.6f}", ""]
            
            if sd.m_mode == "정보 수정" and sd.target_nm:
                idx = sd.df[sd.df['이름'] == sd.target_nm].index[0]
                sd.df.loc[idx] = new_data
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([new_data], columns=CL)], ignore_index=True)
            
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.success("데이터가 성공적으로 저장되었습니다.")
            st.rerun()
        else:
            st.warning("명칭과 지역을 입력해주세요.")

# ---------------------------------------------------------
# [3] 메인 화면: 지도 및 시각화
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 맵")

# 지도 생성
m = folium.Map(
    location=sd.center, 
    zoom_start=11, 
    tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', 
    attr='Google Satellite'
)

# 데이터 마커 표시
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

for _, r in disp_df.iterrows():
    try:
        pos = [float(r['위도']), float(r['경도'])]
        color = 'red' if r['구분'] == '송신소' else 'blue'
        
        # 팝업 HTML 구성
        p_html = f"""
        <div style='font-family: sans-serif;'>
            <b>[{r['구분']}] {r['이름']}</b><br>
            <small>{r['지역']}</small><hr>
            <b>DTV:</b> {r['SBS']}|{r['KBS1']}|{r['MBC']}<br>
            <b>UHD:</b> {r['SBS(U)']}|{r['KBS1(U)']}|{r['MBC(U)']}
        </div>
        """
        
        # 라벨 (DivIcon)
        l_html = f'<div style="color:{color}; font-weight:bold; background:white; padding:2px 5px; border-radius:3px; border:1px solid {color}; font-size:9pt; white-space:nowrap;">{r["이름"]}</div>'
        
        folium.Marker(pos, icon=folium.DivIcon(html=l_html, icon_anchor=(0,30))).add_to(m)
        folium.Marker(pos, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), 
                      popup=folium.Popup(p_html, max_width=250)).add_to(m)
    except: continue

# 클릭 지점 표시 (녹색 별)
if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='plus', prefix='fa')).add_to(m)

map_res = st_folium(m, width="100%", height=600, key=f"map_{sd.map_key}")

# 지도 클릭 이벤트 처리
if map_res.get("last_clicked"):
    la, lo = map_res["last_clicked"]["lat"], map_res["last_clicked"]["lng"]
    if sd.t_la != la:
        sd.t_la, sd.t_lo = la, lo
        sd.m_mode, sd.last_loaded_nm = "새로 등록", "NEW"
        st.rerun()

# ---------------------------------------------------------
# [4] 데이터 테이블 및 내보내기
# ---------------------------------------------------------
st.divider()
st.subheader("📊 인프라 상세 목록")

# 데이터프레임 스타일링
def style_fn(row):
    color = '#fff5f5' if row['구분'] == '송신소' else '#f0f7ff'
    return [f'background-color: {color}'] * len(row)

st.dataframe(
    disp_df.style.apply(style_fn, axis=1),
    use_container_width=True,
    hide_index=True,
    column_config={"위도": None, "경도": None} # 위경도는 표에서 숨김 처리(선택사항)
)

st.download_button("📥 CSV 데이터 백업", 
                   data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), 
                   file_name='broadcasting_stations.csv',
                   mime='text/csv')
