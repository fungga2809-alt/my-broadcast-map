import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
import re
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Master", layout="wide")
DB = 'stations.csv'

# [채널 및 컬럼 정의]
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
# 전문가님이 수정하신 '지역' 포함 컬럼 순서
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '메모']

sd = st.session_state

# [1] 데이터 로드 및 최적화
if 'df' not in sd:
    try:
        temp_df = pd.read_csv(DB, dtype=str).fillna("")
        # 불러온 데이터의 컬럼 순서를 CL과 동일하게 강제 교정합니다.
        sd.df = temp_df.reindex(columns=CL, fill_value="")
    except:
        sd.df = pd.DataFrame(columns=CL, dtype=str)

defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'layer': "위성+도로", 'last_target': None, 'last_mode': "새로 등록", 
            'history': [], 'map_key': 0, 'sel_reg': "전체"}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"i_{s}" not in sd: sd[f"i_{s}"] = ""

def save_history():
    sd.history.append(sd.df.copy())
    if len(sd.history) > 10: sd.history.pop(0)

st.markdown(f"## 📡 전국 방송 인프라 마스터 (현재 지역: {sd.sel_reg})")

# ---------------------------------------------------------
# [2] 사이드바: 지역 필터 및 도구 (가장 먼저 실행)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 전국 지역 필터")
    
    # 지역 목록 추출 (데이터가 있으면 추출, 없으면 기본값)
    regs = ["전체"] + sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else ["전체"]
    new_reg = st.selectbox("🗺️ 관리 지역 선택", regs, index=regs.index(sd.sel_reg) if sd.sel_reg in regs else 0)
    
    # 지역 필터가 바뀌면 지도를 해당 지역의 첫 번째 데이터로 이동
    if new_reg != sd.sel_reg:
        sd.sel_reg = new_reg
        reg_df = sd.df[sd.df['지역'] == new_reg] if new_reg != "전체" else sd.df
        if not reg_df.empty:
            sd.center = [float(reg_df.iloc[0]['위도']), float(reg_df.iloc[0]['경도'])]
            sd.map_key += 1
        st.rerun()

    btn_col1, btn_col2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    
    if btn_col1.button("🎯 내 위치"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]; sd.map_key += 1; st.rerun()
        
    if btn_col2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo = None, None; st.rerun()

    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    
    # 현재 필터링된 지역의 시설만 수정 대상으로 표시
    f_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]
    target_nm = st.selectbox("수정 대상 선택", f_df['이름'].tolist()) if m_mode == "정보 수정" else None
        
    if sd.last_mode != m_mode or sd.last_target != target_nm:
        if m_mode == "정보 수정" and target_nm:
            row = sd.df[sd.df['이름'] == target_nm].iloc[0]
            sd["i_reg"], sd["i_cat"], sd["i_nm"] = row['지역'], row['구분'], row['이름']
            sd["i_la_fixed"], sd["i_lo_fixed"] = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"i_{s}"] = str(row[s])
            sd.center = [sd["i_la_fixed"], sd["i_lo_fixed"]]
        else:
            sd["i_reg"] = sd.sel_reg if sd.sel_reg != "전체" else "부산광역시"
            sd["i_cat"], sd["i_nm"] = "중계소", ""
            for s in SL: sd[f"i_{s}"] = ""
        sd.last_mode, sd.last_target = m_mode, target_nm

    # 입력 폼
    st.text_input("지역", key="i_reg")
    st.radio("구분", ["송신소", "중계소"], key="i_cat", horizontal=True)
    st.text_input("시설 명칭", key="i_nm")
    la_val = sd.t_la if sd.t_la else sd.get("i_la_fixed", sd.center[0])
    lo_val = sd.t_lo if sd.t_lo else sd.get("i_lo_fixed", sd.center[1])
    fla, flo = st.number_input("위도", value=float(la_val), format="%.6f"), st.number_input("경도", value=float(lo_val), format="%.6f")

    st.write("📺 **채널 정보**")
    for s in SL: st.text_input(s, key=f"i_{s}")

    if st.button("✅ 데이터 저장"):
        if sd["i_nm"]:
            save_history()
            v = [sd["i_reg"], sd["i_cat"], sd["i_nm"]] + [sd[f"i_{s}"] for s in SL] + [str(fla), str(flo), ""]
            if m_mode == "정보 수정" and target_nm:
                idx = sd.df[sd.df['이름'] == target_nm].index[0]; sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo = None, None; st.rerun()

# ---------------------------------------------------------
# [3] 본문: 표 선택 로직을 지도보다 먼저 배치 (중요!)
# ---------------------------------------------------------
disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

st.subheader(f"📊 {sd.sel_reg} 시설 목록 (클릭 시 지도 이동)")
event = st.dataframe(
    disp_df[CL], 
    use_container_width=True, 
    on_select="rerun", 
    selection_mode="single-row",
    hide_index=True,
    key="main_table"
)

# 표에서 시설을 클릭했는지 확인하고, 클릭했다면 지도 중심점(sd.center)을 미리 바꿉니다.
if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]
    sel_row = disp_df.iloc[idx]
    new_la, new_lo = float(sel_row['위도']), float(sel_row['경도'])
    if sd.center != [new_la, new_lo]:
        sd.center = [new_la, new_lo]
        sd.t_la, sd.t_lo = new_la, new_lo
        sd.map_key += 1 # 지도를 새로 그리게 함
        st.rerun()

# ---------------------------------------------------------
# [4] 본문: 지도 출력 (변경된 sd.center가 즉시 반영됨)
# ---------------------------------------------------------
ly = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}'
m = folium.Map(location=sd.center, zoom_start=14, tiles=ly, attr='G')

for _, r in disp_df.iterrows():
    try:
        p, clr = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        txt = f"<b>[{r['지역']}] {r['이름']}</b>"
        folium.Marker(p, popup=folium.Popup(txt, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if sd.t_la: folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green')).add_to(m)

# 지도를 표 아래에 배치하여 시각적 흐름 완성
st_folium(m, width="100%", height=600, key=f"map_v74_{sd.map_key}")

csv_data = sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
st.download_button(label="📥 전체 데이터 CSV 백업", data=csv_data, file_name='stations.csv', mime='text/csv')
