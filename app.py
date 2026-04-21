import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Infrastructure Master", layout="wide")
DB = 'stations.csv'

# [정의] 채널 그룹 및 컬럼
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

# [중요] 채널 입력값 세션 보존용 초기화 (최초 1회만)
for s in SL:
    if f"ch_{s}" not in sd: sd[f"ch_{s}"] = ""

# [CSS] v82 스타일 대형 폰트 및 UI 정돈
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-size: 18px !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [2] 사이드바: v70 디자인 + v98 데이터 박제 로직
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    # 지역 필터
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    sd.sel_reg = st.selectbox("🗺️ 관리 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)

    # 주소 검색 (v98: 검색 시 채널 데이터는 건드리지 않음)
    st.subheader("🔍 주소/지명 검색")
    search_addr = st.text_input("검색할 주소 또는 건물명", key="addr_input")
    if st.button("📍 위치 검색"):
        if search_addr:
            try:
                geolocator = Nominatim(user_agent="broadcasting_master_v98")
                location = geolocator.geocode(search_addr)
                if location:
                    sd.center = [location.latitude, location.longitude]
                    sd.t_la, sd.t_lo = location.latitude, location.longitude
                    sd.map_key += 1
                    # 검색 시에는 채널 데이터를 초기화하지 않음!
                    st.rerun()
            except: st.error("검색 엔진 오류")

    c1, c2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    if c1.button("🎯 내 위치"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]; sd.map_key += 1; st.rerun()
    if c2.button("↩️ 되돌리기"):
        if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

    st.divider()

    # 모드 설정
    sd.m_mode = st.radio("📍 모드 설정", ["새로 등록", "정보 수정"], index=0 if sd.m_mode == "새로 등록" else 1, horizontal=True)
    
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    names = f_df['이름'].tolist()
    
    # 정보 수정 모드일 때 데이터 로딩 (최초 1회만 불러오기)
    if sd.m_mode == "정보 수정" and names:
        target_idx = names.index(sd.target_nm) if sd.target_nm in names else 0
        sd.target_nm = st.selectbox("관리 대상 선택", names, index=target_idx)
        
        # 선택한 시설이 바뀌었을 때만 채널 정보를 새로 불러옴
        if sd.last_loaded_nm != sd.target_nm:
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = row['지역'], row['구분'], row['이름']
            # 좌표는 t_la(검색좌표)가 없으면 원본 좌표 사용
            if not sd.t_la: sd.t_la, sd.t_lo = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"ch_{s}"] = str(row[s])
            sd.last_loaded_nm = sd.target_nm
    else:
        # 새로 등록 모드일 때 (새로운 등록으로 넘어온 경우만 초기화)
        if sd.last_loaded_nm != "NEW":
            sd["v_reg"], sd["v_cat"], sd["v_nm"] = sd.sel_reg if sd.sel_reg != "전체" else "부산광역시", "중계소", ""
            for s in SL: sd[f"ch_{s}"] = ""
            sd.last_loaded_nm = "NEW"

    # 시설 정보 입력 (key를 사용하여 세션 상태와 직접 연결)
    new_reg = st.text_input("지역", key="v_reg")
    new_cat = st.radio("구분", ["송신소", "중계소"], index=0 if sd.get("v_cat")=="송신소" else 1, key="v_cat_radio")
    # 라디오 버튼의 결과를 v_cat 세션에 저장
    sd["v_cat"] = new_cat
    new_nm = st.text_input("시설 명칭", key="v_nm")
    
    # 위도/경도 입력 (t_la 검색 좌표와 연동)
    final_la = st.number_input("위도", value=float(sd.t_la if sd.t_la else sd.center[0]), format="%.6f", key="inp_la")
    final_lo = st.number_input("경도", value=float(sd.t_lo if sd.t_lo else sd.center[1]), format="%.6f", key="inp_lo")
    # 입력 시 세션 업데이트
    sd.t_la, sd.t_lo = final_la, final_lo

    # [v70 스타일] 채널 정보 그룹화 입력 (key를 활용해 데이터 박제)
    st.subheader("📺 채널 정보 (그룹화)")
    st.info("📡 **DTV 채널**")
    dtv_cols = st.columns(3)
    for i, s in enumerate(SL_DTV):
        # key를 "ch_SBS" 등으로 지정하면 사용자가 입력할 때마다 sd["ch_SBS"]에 자동 저장됨
        dtv_cols[i%3].text_input(s, key=f"ch_{s}")
        
    st.warning("✨ **UHD 채널**")
    uhd_cols = st.columns(3)
    for i, s in enumerate(SL_UHD):
        uhd_cols[i%3].text_input(s, key=f"ch_{s}")

    if st.button("✅ 데이터 저장"):
        if sd["v_nm"]:
            sd.history.append(sd.df.copy())
            ch_vals = [sd[f"ch_{s}"] for s in SL]
            v = [sd["v_reg"], sd["v_cat"], sd["v_nm"]] + ch_vals + [str(sd.t_la), str(sd.t_lo), ""]
            
            if sd.m_mode == "정보 수정" and sd.target_nm:
                idx = sd.df[sd.df['이름'] == sd.target_nm].index[0]
                sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            # 저장 후에는 검색 마커와 채널 데이터 초기화
            sd.t_la, sd.t_lo, sd.target_nm, sd.last_loaded_nm = None, None, None, None
            for s in SL: sd[f"ch_{s}"] = ""
            st.success("저장 완료!"); st.rerun()

    # 시설 삭제
    st.divider()
    del_target = st.selectbox("삭제 시설 선택", ["선택 안 함"] + sd.df['이름'].tolist(), key="del_box")
    if st.button("🚨 시설 삭제"):
        if del_target != "선택 안 함":
            sd.history.append(sd.df.copy())
            sd.df = sd.df[sd.df['이름'] != del_target]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

# ---------------------------------------------------------
# [3] 본문: 지도 및 데이터 관리 (v82 스타일)
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 마스터")

disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
m = folium.Map(location=sd.center, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')

for _, r in disp_df.iterrows():
    try:
        p, color = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="font-size: 11pt; color: {color}; font-weight: bold; background: rgba(255,255,255,0.8); padding: 2px 5px; border-radius: 3px; border: 1px solid {color}; white-space: nowrap;">{r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

# 검색된 녹색 마커는 t_la가 있을 때 항상 표시
if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='star', prefix='fa')).add_to(m)

map_data = st_folium(m, width="100%", height=500, key=f"map_v98_{sd.map_key}")

# 지도 클릭 시 좌표 획득 (입력값 유지)
if map_data.get("last_clicked"):
    cla, clo = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if sd.t_la != cla:
        sd.t_la, sd.t_lo = cla, clo
        st.rerun()

st.divider()
st.markdown(f"### 📊 <span style='color:red'>송신소</span> / <span style='color:blue'>중계소</span> 데이터 관리 현황", unsafe_allow_html=True)

cfg = {col: st.column_config.TextColumn(col, alignment="center") for col in CL}
def style_row(row):
    color = 'color: red;' if row['구분'] == '송신소' else 'color: blue;'
    return [color for _ in row]

styled_df = disp_df[CL].style.apply(style_row, axis=1)

event = st.dataframe(styled_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=cfg, key="main_table")

# 표 클릭 시 수정 모드 전환
if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    if sd.target_nm != sel_row['이름']:
        sd.center, sd.m_mode, sd.target_nm = [float(sel_row['위도']), float(sel_row['경도'])], "정보 수정", sel_row['이름']
        sd.t_la, sd.t_lo = None, None # 표 클릭 시에는 검색 마커 해제
        sd.map_key += 1; st.rerun()

st.download_button(label="📥 전체 데이터 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
