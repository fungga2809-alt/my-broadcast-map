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
if 'df' not in sd:
    try:
        sd.df = pd.read_csv(DB)
        if '구분' not in sd.df.columns: sd.df.insert(0, '구분', '중계소')
        for c in CL:
            if c not in sd.df.columns: sd.df[c] = ""
    except:
        sd.df = pd.DataFrame(columns=CL)

if 'center' not in sd: sd.center = [35.1796, 129.0756]
if 't_la' not in sd: sd.t_la = None
if 't_lo' not in sd: sd.t_lo = None
if 'layer' not in sd: sd.layer = "위성+도로"

st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

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
            l = Nominatim(user_agent="v54_mgr").geocode(sq)
            if l:
                sd.t_la, sd.t_lo = l.latitude, l.longitude
                sd.center = [l.latitude, l.longitude]
                st.rerun()
        except: pass

    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    
    edit_idx = None
    curr_data = {c: "" for c in CL}
    curr_data['위도'], curr_data['경도'] = (sd.t_la if sd.t_la else sd.center[0]), (sd.t_lo if sd.t_lo else sd.center[1])

    if m_mode == "정보 수정" and not sd.df.empty:
        target_nm = st.selectbox("수정할 시설 선택", sd.df['이름'].tolist())
        edit_idx = sd.df[sd.df['이름'] == target_nm].index[0]
        for c in CL: curr_data[c] = sd.df.at[edit_idx, c]
    
    cat = st.radio("구분", ["송신소", "중계소"], index=0 if curr_data['구분'] == "송신소" else 1, horizontal=True)
    nm = st.text_input("시설 명칭", value=str(curr_data['이름']))
    fla = st.number_input("위도", value=float(curr_data['위도']), format="%.6f")
    flo = st.number_input("경도", value=float(curr_data['경도']), format="%.6f")

    chs = {}
    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(SL), 2):
        c1, c2 = st.columns(2)
        chs[SL[i]] = c1.text_input(SL[i], value=str(curr_data[SL[i]]), key=f"i_{SL[i]}")
        chs[SL[i+1]] = c2.text_input(SL[i+1], value=str(curr_data[SL[i+1]]), key=f"i_{SL[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            v = [cat, nm] + [chs[s] for s in SL] + [fla, flo, ""]
            if m_mode == "정보 수정" and edit_idx is not None:
                # 에러 해결 핵심: 표를 한 줄 통째로 엎지 않고, 각 칸을 하나씩 안전하게 수정합니다.
                for col_idx, col_name in enumerate(CL):
                    sd.df.at[edit_idx, col_name] = v[col_idx]
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo = None, None
            st.rerun()

    if not sd.df.empty:
        st.divider()
        del_tg = st.selectbox("삭제", sd.df['이름'].tolist(), key="del_box")
        if st.button("🚨 삭제"):
            sd.df = sd.df[sd.df['이름'] != del_tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# 지도 레이어 설정
ly = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "위성+도로" else \
     'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "순수 위성" else \
     'https://mt1.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}'

m = folium.Map(location=sd.center, zoom_start=14, tiles=ly, attr='G')

if my_p:
    folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        clr = 'red' if r['구분'] == '송신소' else 'blue'
        d = f"<br>📏 {round(geodesic(my_p, p).km, 2)}km" if my_p else ""
        dt = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" not in s and str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" in s and str(r[s]).strip() != ""])
        txt = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}{d}"
        folium.Marker(p, popup=folium.Popup(txt, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if sd.t_la:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green')).add_to(m)

res = st_folium(m, width="100%", height=800, key="map_v54")

if res and res.get('last_clicked'):
    la, lo = round(res['last_clicked']['lat'], 6), round(res['last_clicked']['lng'], 6)
    if sd.t_la != la:
        sd.t_la, sd.t_lo, sd
