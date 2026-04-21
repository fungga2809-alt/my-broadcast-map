import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import os
import json
import streamlit.components.v1 as components

# [1] 기본 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")
DB = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            for c in COLS:
                if c not in st.session_state.df.columns:
                    st.session_state.df[c] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=COLS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 초기 변수
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state:
    st.session_state.my_loc = None
if 'my_heading' not in st.session_state:
    st.session_state.my_heading = 0
if 'temp_lat' not in st.session_state:
    st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state:
    st.session_state.temp_lon = None

st.title("📡 중계소 통합 관리 (GPS/방향)")

# [4] 센서 제어용 자바스크립트
ui_code = """
<div style="background:#f0f2f6;padding:10px;border-radius:10px;text-align:center;">
<button id="b" style="width:100%;padding:12px;background:#FF4B4B;color:white;border:none;border-radius:5px;font-weight:bold;">🧭 센서 켜기</button>
<p id="m" style="font-size:11px;margin-top:8px;">버튼을 누르면 부채꼴이 나옵니다.</p>
</div>
<script>
const b=document.getElementById('b'), m=document.getElementById('m');
b.onclick=function(){
navigator.geolocation.watchPosition((p)=>{
const d={lat:p.coords.latitude,lon:p.coords.longitude,t:'l'};
window.parent.postMessage({type:'streamlit:setComponentValue',value:JSON.stringify(d)},'*');
m.innerText="📍 위치 연결됨";
},{enableHighAccuracy:true});
if(typeof DeviceOrientationEvent.requestPermission==='function'){
DeviceOrientationEvent.requestPermission().then(s=>{if(s==='granted')st();});
}else{st();}
};
function st(){
window.addEventListener('deviceorientationabsolute',(e)=>{
if(e.alpha!==null){
const d={a:e.alpha,t:'o'};
window.parent.postMessage({type:'streamlit:setComponentValue',value:JSON.stringify(d)},'*');
m.innerText="🧭 방향 감지: "+Math.round(e.alpha)+"°";
}
},true);
}
</script>
"""

# [5] 사이드바 기능
with st.sidebar:
    st.header("⚙️ 도구")
    sd = components.html(ui_code, height=140)
    if sd:
        try:
            r = json.loads(sd)
            if r.get('t') == 'l':
                st.session_state.my_loc = [r['lat'], r['lon']]
            elif r.get('t') == 'o':
                st.session_state.my_heading = 360 - r['a']
        except: pass

    if st.session_state.my_loc and st.button("🎯 내 위치로 지도이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("🔍 검색")
    q = st.text_input("검색어")
    if q:
        f = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, na=False)).any(axis=1)]
        if not f.empty:
            sel = st.selectbox("결과", f['이름'].tolist())
            if st.button("📍 이동"):
                target = f[f['이름']==sel].iloc[0]
                st.session_state.map_center = [target['위도'], target['경도']]
                st.rerun()

    st.divider()
    st.header("📍 등록")
    n = st.text_input("이름")
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i%2==0 else c2).text_input(s)
    
    # 좌표 설정
    lat_val = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    lon_val = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    flat = st.number_input("위도", value=float(lat_val), format="%.6f")
    flon = st.number_input("경도", value=float(lon_val), format="%.6f")
    txt = st.text_area("메모")

    if st.button("✅ 저장"):
        if n:
            new_row = [n] + [chs[s] for s in ST_LIST] + [flat, flon, txt]
            new_df = pd.DataFrame([new_row], columns=COLS)
            st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.rerun()

    st.divider()
    if not st.session_state.df.empty:
        st.header("🗑️ 삭제")
        dt = st.selectbox("삭제대상", st.session_state.df['이름'].tolist())
        if st.button("🚨 삭제"):
            st.session_state.df = st.session_state.df[st.session_state.df['이름']!=dt]
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [6] 메인 지도
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G', name='위성').add_to(m)

# 내 위치 부채꼴 (줄 끊어짐 방지 처리)
if st.session_state.my_loc:
    deg = st.session_state.my_heading
    cone = f'<div style="position:relative;"><div style="width:0;height:0;border-left:50px solid transparent;border-right:50px solid transparent;border-bottom:100px solid rgba(0,150,255,0.4);position:absolute;top:-90px;left:-50px;transform-origin:50% 100%;transform:rotate({deg}deg);pointer-events:none;"></div><div style="width:16px;height:16px;background:#007AFF;border:3px solid white;border-radius:50%;box-shadow:0 0 10px rgba(0,0,0,0.5);"></div></div>'
    folium.Marker(location=st.session_state.my_loc, icon=folium.DivIcon(html=cone)).add_to(m)

# 중계소 마커 (줄 끊어짐 방지)
for _, r in st.session_state.df.iterrows():
    try:
        pos = [float(r['위도']), float(r['경도'])]
        dist = ""
        if st.session_state.my_loc:
            km = geodesic(st.session_state.my_loc, pos).km
            dist = f"<br>📏 {round(km, 2)}km"
        ch = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if pd.notna(r[s]) and str(r[s]).strip() != ""])
        txt = f"<b>{r['이름']}</b><br>{ch}{dist}"
        folium.Marker(location=pos, popup=txt, icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if st
