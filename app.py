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

# [채널 그룹화 정의]
SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['구분','이름'] + SL + ['위도','경도','메모']

sd = st.session_state

# [1] 데이터 로드
if 'df' not in sd:
    try:
        temp_df = pd.read_csv(DB, dtype=str).fillna("")
        sd.df = temp_df.reindex(columns=CL, fill_value="")
        if '구분' not in sd.df.columns: sd.df.insert(0, '구분', '중계소')
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
    btn_col1, btn_col2 = st.columns(2)
    gps = get_geolocation()
    my_p = [gps['coords']['latitude'], gps['coords']['longitude']] if gps and 'coords' in gps else None
    
    if btn_col1.button("🎯 내 위치"):
        if my_p: sd.center, sd.t_la, sd.t_lo = my_p, my_p[0], my_p[1]; st.rerun()
        
    if btn_col2.button("↩️ 되돌리기"):
        if sd.history:
            sd.df = sd.history.pop()
            sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
            sd.t_la, sd.t_lo, sd.last_target = None, None, None; st.rerun()

    st.divider()
    sd.layer = st.radio("🗺️ 지도 모드", ["위성+도로", "순수 위성", "일반 지도"], horizontal=True)

    st.divider()
    sq = st.text_input("📍 주소/DMS 좌표 검색")
    if st.button("🔍 찾기"):
        d_la, d_lo = parse_dms(sq)
        if d_la and d_lo:
            sd.t_la, sd.t_lo, sd.center = d_la, d_lo, [d_la, d_lo]; st.rerun()
        else:
            try:
                l = Nominatim(user_agent="v68_mgr").geocode(sq)
                if l: sd.t_la, sd.t_lo, sd.center = l.latitude, l.longitude, [l.latitude, l.longitude]; st.rerun()
            except: st.error("검색 결과가 없습니다.")

    st.divider()
    m_mode = st.radio("📍 시설 관리", ["새로 등록", "정보 수정"], horizontal=True)
    
    target_nm = None
    if m_mode == "정보 수정" and not sd.df.empty:
        target_nm = st.selectbox("수정할 시설 선택", sd.df['이름'].tolist())
        
    if sd.last_mode != m_mode or sd.last_target != target_nm:
        if m_mode == "정보 수정" and target_nm:
            row = sd.df[sd.df['이름'] == target_nm].iloc[0]
            sd["i_cat"], sd["i_nm"] = row['구분'], row['이름']
            sd["i_la_fixed"], sd["i_lo_fixed"] = float(row['위도']), float(row['경도'])
            for s in SL: sd[f"i_{s}"] = str(row[s])
            if sd.t_la is None: sd.center = [sd["i_la_fixed"], sd["i_lo_fixed"]]
        else:
            if sd.t_la is None:
                sd["i_cat"], sd["i_nm"] = "중계소", ""
                for s in SL: sd[f"i_{s}"] = ""
        sd.last_mode, sd.last_target = m_mode, target_nm

    cat = st.radio("구분", ["송신소", "중계소"], key="i_cat", horizontal=True)
    nm = st.text_input("시설 명칭", key="i_nm")
    curr_la = sd.t_la if sd.t_la is not None else sd.get("i_la_fixed", sd.center[0])
    curr_lo = sd.t_lo if sd.t_lo is not None else sd.get("i_lo_fixed", sd.center[1])
    fla, flo = st.number_input("위도", value=float(curr_la), format="%.6f"), st.number_input("경도", value=float(curr_lo), format="%.6f")

    st.divider()
    st.write("📺 **DTV 채널 (디지털)**")
    dtv_cols = st.columns(3)
    for idx, s in enumerate(SL_DTV): dtv_cols[idx % 3].text_input(s, key=f"i_{s}")
    st.write("✨ **UHD 채널**")
    uhd_cols = st.columns(3)
    for idx, s in enumerate(SL_UHD): uhd_cols[idx % 3].text_input(s, key=f"i_{s}")

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
        del_tg = st.selectbox("삭제 시설 선택", sd.df['이름'].tolist(), key="del_box")
        if st.button("🚨 시설 삭제"):
            save_history(); sd.df = sd.df[sd.df['이름'] != del_tg]; sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); st.rerun()

# [3] 지도 출력
ly = 'https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "위성+도로" else \
     'https://mt1.google.com/vt/lyrs=s&hl=ko&x={x}&y={y}&z={z}' if sd.layer == "순수 위성" else \
     'https://mt1.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}'

m = folium.Map(location=sd.center, zoom_start=14, tiles=ly, attr='G')
if my_p: folium.Marker(my_p, icon=folium.Icon(color='orange', icon='person')).add_to(m)

for _, r in sd.df.iterrows():
    try:
        p, clr = [float(r['위도']), float(r['경도'])], ('red' if r['구분'] == '송신소' else 'blue')
        dt = " | ".join([f"{s}:{r[s]}" for s in SL_DTV if str(r[s]).strip() != ""])
        uh = " | ".join([f"{s}:{r[s]}" for s in SL_UHD if str(r[s]).strip() != ""])
        txt = f"<b>[{r['구분']}] {r['이름']}</b><br>DTV: {dt}<br>UHD: {uh}"
        folium.Marker(p, popup=folium.Popup(txt, max_width=300), icon=folium.Icon(color=clr, icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if sd.t_la is not None:
    folium.Marker([sd.t_la, sd.t_lo], icon=folium.Icon(color='green', icon='location-dot', prefix='fa')).add_to(m)

res = st_folium(m, width="100%", height=800, key="map_v68")
if res and res.get('last_clicked'):
    la, lo = round(res['last_clicked']['lat'], 6), round(res['last_clicked']['lng'], 6)
    if sd.t_la != la: sd.t_la, sd.t_lo, sd.center = la, lo, [la, lo]; st.rerun()

# [4] 하단 데이터 관리 및 클릭 동기화
st.divider()
c1, c2 = st.columns([8, 2])
c1.subheader("📊 데이터 관리 현황")
csv_data = sd.df[CL].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
c2.download_button(label="📥 최신 CSV 받기", data=csv_data, file_name='stations.csv', mime='text/csv')

# [핵심] 표에서 행을 클릭하면 지도를 이동시키는 설정
selected = st.dataframe(
    sd.df[CL], 
    use_container_width=True, 
    on_select="rerun", 
    selection_mode="single_row"
)

# 표에서 특정 행이 선택되었을 때의 동작
if selected and len(selected["selection"]["rows"]) > 0:
    idx = selected["selection"]["rows"][0]
    sel_row = sd.df.iloc[idx]
    try:
        new_lat, new_lon = float(sel_row['위도']), float(sel_row['경도'])
        # 지도의 중심과 초록색 마커를 선택된 시설 위치로 이동
        if sd.center != [new_lat, new_lon]:
            sd.center = [new_lat, new_lon]
            sd.t_la, sd.t_lo = new_lat, new_lon
            st.rerun()
    except: pass
