import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os, json
import streamlit.components.v1 as components

# [1] 기본 설정
st.set_page_config(page_title="중계소 관리", layout="wide")
DB = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 로직
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 세션 변수 초기화
for k, v in {'map_center':[35.1796, 129.0756], 'my_loc':None, 'my_heading':0, 'temp_lat':None, 'temp_lon':None}.items():
    if k not in st.session_state: st.session_state[k] = v

st.title("📡 중계소 통합 관리 시스템 (GPS/방향)")

# [4] 센서 제어 자바스크립트
ui_js = """
<div style="background:#f0f2f6;padding:10px;border-radius:10px;text-align:center;">
<button id="b" style="width:100%;padding:12px;background:#FF4B4B;color:white;border:none;border-radius:5px;font-weight:bold;">🧭 센서/GPS 켜기</button>
<p id="m" style="font-size:11px;margin-top:8px;">부채꼴이 안 보이면 버튼을 누르세요.</p>
</div>
<script>
const b=document.getElementById('b'), m=document.getElementById('m');
b.onclick=function(){
navigator.geolocation.watchPosition((p)=>{
const d={lat:p.coords.latitude,lon:p.coords.longitude,t:'l'};
window.parent.postMessage({type:'streamlit:setComponentValue',value:JSON.stringify(d)},'*');
m.innerText="📍 GPS 연결됨";
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
    st.header("⚙️ 설정")
    sd = components.html(ui_js, height=140)
    if sd:
        try:
            r = json.loads(sd)
            if r.get('t') == 'l': st.session_state.my_loc = [r['lat'], r['lon']]
            elif r.get('t') == 'o': st.session_state.my_heading = 360 - r['a']
        except: pass

    if st.session_state.my_loc and st.button("🎯 내 위치로 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("📍 등록")
    n = st.text_input("이름")
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i%2==0 else c2).text_input(s)
    
    lat_v = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    lon_v = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    flat, flon = st.number_input("위도", value=float(lat_v), format="%.6f"), st.number_input("경도", value=float(lon_v), format="%.6f")
    txt = st.text_area("메모")

    if st.button("✅ 저장"):
        if n:
            new_row = [n] + [chs[s] for s in ST_LIST] + [flat, flon, txt]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row], columns=COLS)], ignore_index=True)
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

# [6] 지도 그리기
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G', name='위성').add_to(m)

if st.session_state.my_loc:
    deg = st.session_state.my_heading
    cone = f'<div style="position:relative;"><div style="width:0;height:0;border-left:50px solid transparent;border-right:50px solid transparent;border-bottom:100px solid rgba(0,150,255,0.4);position:absolute;top:-90px;left:-50px;transform-origin:50% 100%;transform:rotate({deg}deg);pointer-events:none;"></div><div style="width:16px;height:16px;background:#007AFF;border:3px solid white;border-radius:50%;box-shadow:0 0 10px rgba(0,0,0,0.5);"></div></div>'
    folium.Marker(location=st.session_state.my_loc, icon=folium.DivIcon(html=cone)).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist = ""
        if st.session_state.my_loc:
            dist = f"<br>📏 {round(geodesic(st.session_state.my_loc, p).km, 2)}km"
        ch = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if pd.notna(r[s]) and str(r[s]).strip() != ""])
        folium.Marker(location=p, popup=f"<b>{r['이름']}</b><br>{ch}{dist}", icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

if st.session_state.temp_lat:
    folium.Marker(location=[st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

res = st_folium(m, width=1000, height=600, key="m_v20")
if res and res.get('last_clicked'):
    lat, lon = round(res['last_clicked']['lat'], 6), round(res['last_clicked']['lng'], 6)
    if st.session_state.temp_lat != lat:
        st.session_state.temp_lat, st.session_state.temp_lon = lat, lon
        st.rerun()

st.subheader("📋 전체 목록")
st.dataframe(st.session_state.df, use_container_width=True)
