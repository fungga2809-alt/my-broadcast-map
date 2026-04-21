import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os, json
import streamlit.components.v1 as components

# [1] 페이지 기본 설정
st.set_page_config(page_title="중계소 관리 PRO", layout="wide")
DB = 'stations.csv'
ST_LIST = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']

# [2] 데이터 로드 (DB 파일 없으면 생성)
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try:
            st.session_state.df = pd.read_csv(DB)
            for col in COLS:
                if col not in st.session_state.df.columns:
                    st.session_state.df[col] = ""
        except:
            st.session_state.df = pd.DataFrame(columns=COLS)
    else:
        st.session_state.df = pd.DataFrame(columns=COLS)

# [3] 세션 상태 변수 초기화
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'my_loc' not in st.session_state: st.session_state.my_loc = None
if 'my_heading' not in st.session_state: st.session_state.my_heading = 0
if 'temp_lat' not in st.session_state: st.session_state.temp_lat = None
if 'temp_lon' not in st.session_state: st.session_state.temp_lon = None

st.title("📡 중계소 통합 관리 시스템 (GPS/방향)")

# [4] 센서 제어 자바스크립트 (간결한 버전)
js_ui = """
<div style="background:#f0f2f6;padding:12px;border-radius:10px;text-align:center;border:1px solid #ccc;">
<button id="b" style="width:100%;padding:15px;background:#FF4B4B;color:white;border:none;border-radius:8px;font-weight:bold;font-size:16px;">🧭 센서/GPS 활성화</button>
<p id="m" style="font-size:12px;margin-top:10px;">작동 안 할 시 브라우저 설정에서 위치를 허용하세요.</p>
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
            m.innerText="🧭 센서 작동 중";
        }
    },true);
}
</script>
"""

# [5] 사이드바 기능 (센서 및 등록 도구)
with st.sidebar:
    st.header("⚙️ 센서 제어")
    sensor_data = components.html(js_ui, height=150)
    if sensor_data:
        try:
            res = json.loads(sensor_data)
            if res.get('t') == 'l':
                st.session_state.my_loc = [res['lat'], res['lon']]
            elif res.get('t') == 'o':
                st.session_state.my_heading = 360 - res['a']
        except:
            pass

    if st.session_state.my_loc and st.button("🎯 내 위치로 지도 이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()

    st.divider()
    st.header("📍 중계소 등록")
    name = st.text_input("중계소 이름 (필수)")
    chs = {}
    c1, c2 = st.columns(2)
    for i, s in enumerate(ST_LIST):
        chs[s] = (c1 if i % 2 == 0 else c2).text_input(s)
    
    # 지도에서 클릭한 좌표 표시
    cur_lat = st.session_state.temp_lat if st.session_state.temp_lat else st.session_state.map_center[0]
    cur_lon = st.session_state.temp_lon if st.session_state.temp_lon else st.session_state.map_center[1]
    f_lat = st.number_input("위도", value=float(cur_lat), format="%.6f")
    f_lon = st.number_input("경도", value=float(cur_lon), format="%.6f")
    memo = st.text_area("메모")

    if st.button("✅ 데이터 저장"):
        if name:
            new_row = [name] + [chs[s] for s in ST_LIST] + [f_lat, f_lon, memo]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.session_state.temp_lat = None
            st.success(f"{name} 저장 완료!")
            st.rerun()

# [6] 메인 지도 영역
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G', name='위성').add_to(m)

# 내 위치 부채꼴 방향 표시
if st.session_state.my_loc:
    h = st.session_state.my_heading
    cone_html = f'<div style="position:relative;"><div style="width:0;height:0;border-left:45px solid transparent;border-right:45px solid transparent;border-bottom:90px solid rgba(0,150,255,0.4);position:absolute;top:-85px;left:-45px;transform-origin:50% 100%;transform:rotate({h}deg);"></div><div style="width:14px;height:14px;background:#007AFF;border:2px solid white;border-radius:50%;"></div></div>'
    folium.Marker(st.session_state.my_loc, icon=folium.DivIcon(html=cone_html)).add_to(m)

# 등록된 중계소 마커 표시
for _, row in st.session_state.df.iterrows():
    try:
        p = [float(row['위도']), float(row['경도'])]
        dist = f"<br>📏 {round(geodesic(st.session_state.my_loc, p).km, 2)}km" if st.session_state.my_loc else ""
        ch_info = " | ".join([f"{s}:{row[s]}" for s in ST_LIST if pd.notna(row[s]) and str(row[s]).strip() != ""])
        folium.Marker(p, popup=f"<b>{row['이름']}</b><br>{ch_info}{dist}", icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except:
        continue

# 지도 클릭 시 생성되는 임시 녹색 마커
if st.session_state.temp_lat:
    folium.Marker([st.session_state.temp_lat, st.session_state.temp_lon], icon=folium.Icon(color='green')).add_to(m)

# 지도 렌더링 및 터치 클릭 감지
map_out = st_folium(m, width=1000, height=600, key="fixed_v23_map")

if map_out and map_out.get('last_clicked'):
    clat, clon = round(map_out['last_clicked']['lat'], 6), round(map_out['last_clicked']['lng'], 6)
    # 기존 좌표와 다를 때만 업데이트 (무한 새로고침 방지)
    if st.session_state.temp_lat != clat:
        st.session_state.temp_lat, st.session_state.temp_lon = clat, clon
        st.rerun()

# [7] 하단 목록
st.subheader
