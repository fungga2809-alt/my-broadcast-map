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
SL = ['SBS','SBS(U)','KBS2','KBS2(U)','KBS1','KBS1(U)','EBS','EBS(U)','MBC','MBC(U)']
CL = ['구분','이름'] + SL + ['위도','경도','메모']

sd = st.session_state

# [1] 데이터 로드
if 'df' not in sd:
    try:
        sd.df = pd.read_csv(DB, dtype=str).fillna("")
        if '구분' not in sd.df.columns: sd.df.insert(0, '구분', '중계소')
        for c in CL:
            if c not in sd.df.columns: sd.df[c] = ""
    except:
        sd.df = pd.DataFrame(columns=CL, dtype=str)

defaults = {'center': [35.1796, 129.0756], 't_la': None, 't_lo': None, 
            'layer': "위성+도로", 'last_target': None, 'last_mode': "새로 등록", 'history': []}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

for s in SL:
    if f"i_{s}" not in sd: sd[f"i_{s}"] = ""

def save_history():
    sd.history.append(sd.df.copy())
    if len(sd.history) > 10: sd.history.pop(0)

def parse_dms(dms_str):
    try:
        pattern = r"(\d+)°(\d+)'([\d.]+)\"([NSEW])"
        parts = re.findall(pattern, dms_str)
        if len(parts) != 2: return None, None
        results = []
        for d, m, s, h in parts:
            dd = float(d) + float(m)/60 + float(s)/3600
            if h in ['S', 'W']: dd = -dd
            results.append(round(dd, 6))
        return results[0], results[1]
    except: return None, None

st.markdown("## 📡 DTV/UHD 방송 인프라 마스터")

# [2] 사이드바 도구
with st.sidebar:
    st.header("⚙️ 도구")
    
    t_c1, t_c2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    
    if t_c1.button("🎯 내 위치로"):
        if my_p: 
            sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]
            st.rerun()
        
    if t_c2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop()
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.last_target = None, None, None; st.rerun()

    st.divider()
    sd.layer = st.radio("🗺️ 지도 모드", ["위성+도로", "순수 위성", "일반 지도"], horizontal=True)

    st.divider()
    sq = st.text_input("📍 주소/DMS 좌표 검색", help="예: 35°07'30\"N 128°53'27\"E")
    if st.button("🔍 찾기"):
        d_la, d_lo = parse_dms(sq)
        if d_la and d_lo:
            # 좌표 고정력 강화
            sd.t_la, sd.t_lo = d_la, d_lo
            sd.center = [d_la, d_lo]
            st.success(f"좌표 변환: {d_la}, {d_lo}")
            st.rerun()
        else:
            try:
                l = Nominatim(user_agent="v61_mgr").geocode(sq)
                if l:
                    sd.t_la, sd.t_lo, sd.center = l.latitude, l.longitude, [l.latitude, l.longitude]
                    st.rerun()
            except: st.error("검색 결과가 없습니다.")

    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    
    target_nm = None
    if m_mode == "정보 수정" and not sd.df.empty:
        target_nm = st.selectbox("수정할 시설 선택", sd.df['이름'].tolist())
        
    if sd.last_mode != m_mode or sd.last_target != target_nm:
        sd.t_la, sd.t_lo = None, None
        if m_mode == "정보 수정" and target_nm:
            row = sd.df[sd.df['이름'] == target_nm].iloc[0]
            sd["i_cat"], sd["i_nm"] = row['구분'], row['이름']
            sd["i_la_val"], sd["i_lo_val"] = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"i_{s}"] = str(row[s])
        else:
            sd["i_cat"], sd["i_nm"] = "중계소", ""
            sd["i_la_val"], sd["i_lo_val"] = float(sd.center[0]), float(sd.center[1])
            for s in SL: sd[f"i_{s}"] = ""
        sd.last_mode, sd.last_target = m_mode, target_nm

    cat = st.radio("구분", ["송신소", "중계소"], key="i_cat", horizontal=True)
    nm = st.text_input("시설 명칭", key="i_nm")
    
    # 좌표 결정 우선순위: 1. 클릭/검색된 좌표(t_la) -> 2. 기존 데이터 좌표(i_la_val) -> 3. 기본 중심점
    final_la = sd.t_la if sd.t_la is not None else sd.get("i_la_val", sd.center[0])
    final_lo = sd.t_lo if sd.t_lo is not None else sd.get("i_lo_val", sd.center[1])
    
    fla = st.number_input("위도", value=float(final_la), format="%.6f")
    flo = st.number_input("경도", value=float(final_lo), format="%.6f")

    st.write("📺 채널 (DTV | UHD)")
    for i in range(0, len(SL), 2):
        c1, c2 = st.columns(2)
        c1.text_input(SL[i], key=f"i_{SL[i]}")
        c2.text_input(SL[i+1], key=f"i_{SL[i+1]}")

    if st.button("✅ 저장"):
        if nm:
            save_history()
            v = [cat, nm] + [sd[f"i_{s}"] for s in SL] + [str(fla), str(flo), ""]
            if m_mode == "정보 수정" and target_nm:
                idx = sd.df[sd.df['이름'] == target_nm].index[0]
                sd.df.loc[idx] = v
            else:
                sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.last_target = None, None, None; st.rerun()

    if not sd.df.empty:
        st.divider()
        del_tg = st.selectbox("삭제", sd.df['이름'].tolist(), key="del_box")
        if st.button("🚨 삭제"):
            save_history(); sd.df = sd.df[sd.df['이름'] != del_tg]
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

# [3] 지도 출력
ly = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "위성+도로" else \
     'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "순수 위성" else \
     'https://mt1.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}'

m = folium.Map(location=sd.center, zoom_start=14, tiles=ly, attr='G')
if my_p: folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p, clr = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        d = f"<br>📏 {round(geodesic(my_p, p).km, 2)}km" if my_p else ""
        dt = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" not in s and str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in SL if "(U)" in s and str(r[s]).strip() != ""])
        txt = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}{d}"
        folium.Marker(p, popup=folium.Popup(txt, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

# 임시 마커 고정 로직: t_la 값이 있으면 무조건 그립니다.
if sd.t_la is not None:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='location-crosshairs', prefix='fa')).add_to(m)

res = st_folium(m, width="100%", height=800, key="map_v61")

# 지도 클릭 시 좌표 갱신 (지도가 데이터를 보고할 때 t_la를 유지합니다)
if res and res.get('last_clicked'):
    la, lo = round(res['last_clicked']['lat'], 6), round(res['last_clicked']['lng'], 6)
    if sd.t_la != la:
        sd.t_la, sd.t_lo, sd.center = la, lo, [la, lo]; st.rerun()

st.dataframe(sd.df, use_container_width=True)
