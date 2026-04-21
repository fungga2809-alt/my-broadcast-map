import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Broadcasting Master", layout="wide")
DB = 'stations.csv'
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

sd = st.session_state

# [1] 데이터 로드 및 초기화
if 'df' not in sd:
    try:
        sd.df = pd.read_csv(DB, dtype=str).fillna("")
        if '구분' not in sd.df.columns: sd.df.insert(0, '구분', '중계소')
        for c in CL:
            if c not in sd.df.columns: sd.df[c] = ""
    except:
        sd.df = pd.DataFrame(columns=CL, dtype=str)

# 세션 상태 변수들
defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'layer': "위성+도로", 'last_target': None, 'last_mode': "새로 등록"}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

# 채널 입력값 메모리 초기화
for s in SL:
    if f"i_{s}" not in sd: sd[f"i_{s}"] = ""

st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

# [2] 사이드바 도구
with st.sidebar:
    st.header("⚙️ 도구")
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    if my_p:
        st.success("📍 GPS 연결됨")
        if st.button("🎯 내 위치로"):
            sd.center, sd.t_la, sd.t_lo = my_p, None, None
            st.rerun()

    st.divider()
    sd.layer = st.radio("🗺️ 지도 모드", ["위성+도로", "순수 위성", "일반 지도"], horizontal=True)

    st.divider()
    sq = st.text_input("주소 검색")
    if st.button("📍 주소 찾기"):
        try:
            l = Nominatim(user_agent="v57_mgr").geocode(sq)
            if l:
                sd.t_la, sd.t_lo, sd.center = l.latitude, l.longitude, [l.latitude, l.longitude]
                st.rerun()
        except: pass

    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    
    # 모드가 바뀌거나 수정 대상이 바뀌면 입력창 자동 초기화
    target_nm = None
    if m_mode == "정보 수정" and not sd.df.empty:
        target_nm = st.selectbox("수정할 시설 선택", sd.df['이름'].tolist())
        
    if sd.last_mode != m_mode or sd.last_target != target_nm:
        sd.t_la, sd.t_lo = None, None
        if m_mode == "정보 수정" and target_nm:
            row = sd.df[sd.df['이름'] == target_nm].iloc[0]
            sd["i_cat"] = row['구분']
            sd["i_nm"] = row['이름']
            sd["i_la_val"] = float(row['위도'])
            sd["i_lo_val"] = float(row['경도'])
            for s in SL: sd[f"i_{s}"] = str(row[s])
        else:
            sd["i_cat"] = "중계소"
            sd["i_nm"] = ""
            sd["i_la_val"] = float(sd.center[0])
            sd["i_lo_val"] = float(sd.center[1])
            for s in SL: sd[f"i_{s}"] = ""
        sd.last_mode, sd.last_target = m_mode, target_nm

    # 입력 UI
    cat = st.radio("구분", ["송신소", "중계소"], key="i_cat", horizontal=True)
    nm = st.text_input("시설 명칭", key="i_nm")
    
    # 지도 클릭 시 좌표 갱신 (메모리 유지)
    final_la = sd.t_la if sd.t_la else sd.get("i_la_val", sd.center[0])
    final_lo = sd.t_lo if sd.t_lo else sd.get("i_lo_val", sd.center[1])
    
    fla = st.number_input("위도", value=float(final_la), format="%.6f")
    flo = st.number_input("경도", value=float(final_lo), format="%.6f")

    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(SL), 2):
        c1, c2 = st.columns(2)
        c1.text_input(SL[i], key=f"i_{SL[i]}")
        c2.text_input(SL[i+1], key=f"i_{SL[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [sd[f"i_{s}"] for s in SL] + [str(fla), str(flo), ""]
            if m_mode == "정보 수정" and target_nm:
                idx = sd.df[sd.df['이름'] == target_nm].index[0]
                sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.last_target = None, None, None
            st.rerun()

    if not sd.df.empty:
        st.divider()
        del_tg = st.selectbox("삭제", sd.df['이름'].tolist(), key="del_box")
        if st.button("🚨 삭제"):
            sd.df = sd.df[sd.df['이름'] != del_tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [3] 지도 출력
ly = '
