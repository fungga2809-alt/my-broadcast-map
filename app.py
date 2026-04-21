import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import os, json
import streamlit.components.v1 as components

st.set_page_config(page_title="중계소 관리 PRO", layout="wide")

# [데이터 로직 생략 - 이전과 동일]
DB, ST_LIST = 'stations.csv', ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
COLS = ['이름'] + ST_LIST + ['위도', '경도', '메모']
if 'df' not in st.session_state:
    if os.path.exists(DB):
        try: st.session_state.df = pd.read_csv(DB)
        except: st.session_state.df = pd.DataFrame(columns=COLS)
    else: st.session_state.df = pd.DataFrame(columns=COLS)

for k, v in {'map_center':[35.1796, 129.0756], 'my_loc':None, 'my_heading':0, 'temp_lat':None, 'temp_lon':None}.items():
    if k not in st.session_state: st.session_state[k] = v

st.title("📡 중계소 통합 관리 (GPS/방향)")

# --- [시스템] 초강력 센서 브릿지 + 진단 모드 ---
debug_js = """
<div id="box" style="background:#262730; padding:15px; border-radius:10px; color:white; font-family:sans-serif;">
    <button id="btn" style="width:100%; padding:15px; background:#FF4B4B; color:white; border:none; border-radius:8px; font-weight:bold; font-size:18px; cursor:pointer; margin-bottom:10px;">
        🧭 센서/GPS 강제 활성화
    </button>
    <div id="log" style="font-size:12px; color:#aaa; line-height:1.6; border-top:1px solid #444; padding-top:10px;">
        준비 상태: 버튼을 눌러주세요.
    </div>
</div>

<script>
const btn = document.getElementById('btn');
const log = document.getElementById('log');

function writeLog(txt) {
    log.innerHTML += "<br>• " + txt;
}

function send(data) {
    window.parent.postMessage({type:'streamlit:setComponentValue', value:JSON.stringify(data)}, '*');
}

btn.onclick = async function() {
    log.innerHTML = "작동 시작...";
    
    // 1. GPS 테스트
    writeLog("GPS 요청 중...");
    if (!navigator.geolocation) {
        writeLog("❌ GPS 미지원 브라우저");
    } else {
        navigator.geolocation.getCurrentPosition(
            (p) => {
                send({lat:p.coords.latitude, lon:p.coords.longitude, t:'l'});
                writeLog("✅ GPS 좌표 획득 성공");
            },
            (e) => {
                writeLog("❌ GPS 오류: " + e.message);
                alert("위치 권한이 차단되어 있습니다. 브라우저 설정에서 허용해주세요.");
            },
            {enableHighAccuracy:true, timeout: 5000}
        );
    }

    // 2. 나침반(방향) 테스트
    writeLog("방향 센서 요청 중...");
    if (typeof DeviceOrientationEvent !== 'undefined') {
        if (typeof DeviceOrientationEvent.requestPermission === 'function') {
            // iOS 대응
            try {
                const permission = await DeviceOrientationEvent.requestPermission();
                writeLog("iOS 권한 상태: " + permission);
                if (permission === 'granted') {
                    startOri();
                }
            } catch (e) {
                writeLog("❌ iOS 센서 에러: " + e);
            }
        } else {
            // 안드로이드/PC 대응
            writeLog("일반 센서 모드 진입");
            startOri();
        }
    } else {
        writeLog("❌ 기기가 방향 센서를 지원하지 않음");
    }
};

function startOri() {
    window.addEventListener('deviceorientationabsolute', (e) => {
        if (e.alpha !== null) {
            send({a:e.alpha, t:'o'});
            log.style.color = "#4CAF50";
        }
    }, true);
    // iOS 전용 추가 보정
    window.addEventListener('deviceorientation', (e) => {
        if (e.webkitCompassHeading) {
            send({a:360-e.webkitCompassHeading, t:'o'});
            log.style.color = "#4CAF50";
        }
    }, true);
    writeLog("🧭 나침반 작동 중...");
}
</script>
"""

with st.sidebar:
    st.header("⚙️ 하드웨어 연결")
    sensor_result = components.html(debug_js, height=220)
    if sensor_result:
        try:
            r = json.loads(sensor_result)
            if r.get('t') == 'l': st.session_state.my_loc = [r['lat'], r['lon']]
            elif r.get('t') == 'o': st.session_state.my_heading = 360 - r['a']
        except: pass
    
    if st.session_state.my_loc and st.button("🎯 내 위치로 지도이동"):
        st.session_state.map_center = st.session_state.my_loc
        st.rerun()
    st.divider()
    # [이후 등록/삭제 코드는 이전과 동일]
    # (에러 방지를 위해 이번에는 등록 부분 코드를 줄여서 안전하게 포함했습니다)
    st.header("📍 등록")
    n = st.text_input("중계소 이름")
    chs = {}
    for s in ST_LIST: chs[s] = st.text_input(s)
    flat = st.number_input("위도", value=float(st.session_state.map_center[0]), format="%.6f")
    flon = st.number_input("경도", value=float(st.session_state.map_center[1]), format="%.6f")
    if st.button("✅ 저장"):
        if n:
            new_r = [n] + [chs[s] for s in ST_LIST] + [flat, flon, ""]
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_r], columns=COLS)], ignore_index=True)
            st.session_state.df.to_csv(DB, index=False, encoding='utf-8-sig')
            st.rerun()

# [지도 그리기 부분은 이전과 동일]
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G', name='위성').add_to(m)

if st.session_state.my_loc:
    deg = st.session_state.my_heading
    cone = f'<div style="position:relative;"><div style="width:0;height:0;border-left:50px solid transparent;border-right:50px solid transparent;border-bottom:100px solid rgba(0,150,255,0.4);position:absolute;top:-90px;left:-50px;transform-origin:50% 100%;transform:rotate({deg}deg);pointer-events:none;"></div><div style="width:16px;height:16px;background:#007AFF;border:3px solid white;border-radius:50%;box-shadow:0 0 10px rgba(0,0,0,0.5);"></div></div>'
    folium.Marker(location=st.session_state.my_loc, icon=folium.DivIcon(html=cone)).add_to(m)

for _, r in st.session_state.df.iterrows():
    try:
        p = [float(r['위도']), float(r['경도'])]
        dist = f"<br>📏 {round(geodesic(st.session_state.my_loc, p).km, 2)}km" if st.session_state.my_loc else ""
        ch = " | ".join([f"{s}:{r[s]}" for s in ST_LIST if pd.notna(r[s]) and str(r[s]).strip() != ""])
        folium.Marker(location=p, popup=f"<b>{r['이름']}</b><br>{ch}{dist}", icon=folium.Icon(color='red', icon='tower-broadcast', prefix='fa')).add_to(m)
    except: pass

st_folium(m, width=1000, height=600, key="m_v21")
st.subheader("📋 전체 목록")
st.dataframe(st.session_state.df, use_container_width=True)
