import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os, json
import streamlit.components.v1 as components

# [1] 기본 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")
DB = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 로직 (안전성 강화)
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            for c in COLS:
                if c not in st.session_state.df.columns: st.session_state.df[c] = ""
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 세션 상태 초기화
states = {
    'map_center': [35.1796, 129.0756],
    'my_loc': None,
    'my_heading': 0,
    'temp_lat': None,
    'temp_lon': None
}
for k, v in states.items():
    if k not in st.session_state: st.session_state[k] = v

st.title("📡 중계소 통합 관리 (현장 복구용)")

# [4] 센서 제어용 자바스크립트 (최소 간섭 모드)
js_code = """
<div style="background:#f0f2f6;padding:12px;border-radius:10px;text-align:center;border:1px solid #ccc;">
<button id="b" style="width:100%;padding:15px;background:#FF4B4B;color:white;border:none;border-radius:8px;font-weight:bold;font-size:16px;">🧭 센서/GPS 활성화</button>
<p id="m" style="font-size:12px;margin-top:10px;color:#333;">작동하지 않으면 브라우저 '위치' 권한을 확인하세요.</p>
</div>
<script>
const b=document.getElementById('b'), m=document.getElementById('m');
b.onclick=function(){
    m.innerText="⏳ 연결 시도 중...";
    navigator.geolocation.getCurrentPosition((p)=>{
        window.parent.postMessage({type:'streamlit:setComponentValue', value:JSON.stringify({lat:p.coords.latitude,lon:p.coords.longitude,t:'l'})}, '*');
        m.innerText="📍 GPS 연결 성공";
    }, (e)=>{ alert("GPS 권한 거부됨: " + e.message); }, {enableHighAccuracy:true});
    if(typeof DeviceOrientationEvent!=='undefined' && typeof DeviceOrientationEvent.requestPermission==='function'){
        DeviceOrientationEvent.requestPermission().then(s=>{if(s==='granted')start();});
    } else { start(); }
};
function start(){
    window.addEventListener('deviceorientationabsolute',(e)=>{
        if(e.alpha!==null){
            window.parent.postMessage({type:'streamlit:setComponentValue', value:JSON.stringify({a:e.alpha,t:'o'})}, '*');
            m.innerText="🧭 센서 작동 중 ("+Math.round(e.alpha)+"°)";
        }
    },true);
}
</script>
"""

# [5] 사이드바: 모든 도구 통합
with st.sidebar:
    st.header("⚙️ 센서 제어")
    sensor_val = components.html(js_code, height=150)
    if sensor_val:
        try:
            r = json.loads(sensor_val)
            if r.get('t') == 'l': st.session_state.my_loc = [r['lat'], r['lon']]
            elif r.get('t') == 'o': st.session_state.my_heading = 360 - r['a']
        except: pass

    if st.session_state.my_loc and st.button("🎯 내 위치로 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("📍 중계소 등록")
    name = st.text_input("중계소 이름")
    
    # 채널 입력 (2열 배치)
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i%2==0 else c2).text_input(s)
    
    # 좌표는 지도 클릭 시 자동 갱신됨
    cur_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    cur_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    flat = st.number_input("위도", value=float(cur_lat), format="%.6f")
    flon = st.number_input("경도", value=float(cur_lon), format="%.6f")
    memo = st.text_area("메모")

    if st.button("✅ 저장"):
        if name:
            new_row = [name] + [chs[s] for s in ST_LIST] + [flat, flon, memo]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success("저장 완료!")
            st.rerun()

# [6] 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G', name='위성').add_to(m)

# 부채꼴 방향 표시
if st.session_state.my_loc:
