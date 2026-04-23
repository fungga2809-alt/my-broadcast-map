import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import re

st.set_page_config(page_title="Broadcasting Infrastructure Master", layout="wide")
DB = 'stations.csv'

SL_DTV = ['SBS', 'KBS2', 'KBS1', 'EBS', 'MBC']
SL_UHD = ['SBS(U)', 'KBS2(U)', 'KBS1(U)', 'EBS(U)', 'MBC(U)']
SL = SL_DTV + SL_UHD
CL = ['지역', '구분', '이름'] + SL + ['위도', '경도', '주소']

sd = st.session_state

def safe_rerun():
    sd.temp_channels = {s: sd.get(f"ch_{s}", "") for s in SL}
    st.rerun()

if 'temp_channels' in sd:
    for s in SL:
        sd[f"ch_{s}"] = sd.temp_channels.get(s, "")
    del sd.temp_channels

def get_google_format(lat, lon):
    def to_dms(deg, is_lat):
        try:
            if not deg or str(deg).strip() == "": return ""
            deg = float(deg)
            d = int(abs(deg))
            m = int((abs(deg) - d) * 60)
            s = round((abs(deg) - d - m/60) * 3600, 2)
            suffix = (("N" if deg >= 0 else "S") if is_lat else ("E" if deg >= 0 else "W"))
            return f"{d}°{m}'{s}\"{suffix}"
        except: return ""
    return f"{to_dms(lat, True)} {to_dms(lon, False)}"

def clean_kr_address(addr_str):
    if not addr_str: return ""
    parts = [p.strip() for p in addr_str.split(',')]
    filtered = []
    for p in parts:
        if p == "대한민국" or re.match(r'^\d{4,5}$', p): 
            continue
        if re.search(r'(도|광역시|특별시|자치시|시|군|구)$', p) and len(p) <= 7:
            continue
        filtered.append(p)
    filtered.reverse()
    return " ".join(filtered)

def load_data():
    try:
        df = pd.read_csv(DB, dtype=str).fillna("")
        if '메모' in df.columns: df.rename(columns={'메모': '주소'}, inplace=True)
        if '지역' not in df.columns: df.insert(0, '지역', '미지정')
        return df.reindex(columns=CL, fill_value="")
    except:
        return pd.DataFrame(columns=CL, dtype=str)

if 'df' not in sd: sd.df = load_data()

defaults = {
    'base_center': [35.1796, 129.0756], 
    'base_zoom': 14,                    
    'crosshair_center': None,           
    't_la': None, 't_lo': None, 
    'history': [], 'map_key': 0, 'sel_reg': "전체", 
    'm_mode': "신규 등록", 'target_nm': None, 'last_loaded_nm': None, 'v_addr': ""
}
for k, v in defaults.items():
    if k not in sd: sd[k] = v

st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    th { text-align: center !important; background-color: #f0f2f6 !important; font-size: 18px !important; font-weight: bold !important; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; min-height: 45px; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    
    div.element-container:has(.btn-red) + div.element-container button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
    div.element-container:has(.btn-blue) + div.element-container button { background-color: #3498db !important; color: white !important; border: none !important; }
    div.element-container:has(.btn-green) + div.element-container button { background-color: #2ecc71 !important; color: white !important; border: none !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 관제 및 관리")
    
    existing_regs = sorted(sd.df['지역'].unique().tolist()) if not sd.df.empty else []
    filter_idx = existing_regs.index(sd.sel_reg) + 1 if sd.sel_reg in existing_regs else 0
    sd.sel_reg = st.selectbox("🗺️ 관제 지역 필터", ["전체"] + existing_regs, index=filter_idx)

    st.subheader("🔍 위치 제어")
    search_addr = st.text_input("주소/건물명 검색", key="addr_input")
    c_loc = st.columns([1, 1, 1], gap="small")
    geolocator = Nominatim(user_agent="broadcasting_v370")

    with c_loc[0]:
        if st.button("📍검색"):
            if search_addr:
                try:
                    loc = geolocator.geocode(search_addr)
                    if loc:
                        sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                        sd.t_la, sd.t_lo, sd.v_addr = loc.latitude, loc.longitude, clean_kr_address(loc.address)
                        safe_rerun()
                except: st.error("오류")
    with c_loc[1]:
        if st.button("🎯위치"):
            gps = get_geolocation()
            if gps and 'coords' in gps:
                p = [gps['coords']['latitude'], gps['coords']['longitude']]
                sd.base_center, sd.base_zoom, sd.t_la, sd.t_lo = [p[0], p[1]], 16, p[0], p[1]
                try:
                    rev = geolocator.reverse(f"{p[0]}, {p[1]}")
                    if rev: sd.v_addr = clean_kr_address(rev.address)
                except: pass
                safe_rerun()
    with c_loc[2]:
        if st.button("↩️복구"):
            if sd.history: sd.df = sd.history.pop(); sd.df.to_csv(DB, index=False, encoding='utf-8-sig'); safe_rerun()

    st.divider()
    
    # 1. 신규 위치 지정 버튼 (적색)
    st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 신규 위치로 지정"):
        sd.m_mode = "신규 등록"
        sd.target_nm = None  
        sd.last_loaded_nm = None
        for s in SL: sd[f"ch_{s}"] = ""
        target_loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.t_la, sd.t_lo = target_loc[0], target_loc[1]
        
        # [핵심 고정] 지도가 튕기지 않도록 베이스 센터를 조준경 위치로 즉시 고정
        sd.base_center = [target_loc[0], target_loc[1]] 
        
        try:
            rev = geolocator.reverse(f"{sd.t_la}, {sd.t_lo}")
            if rev: sd.v_addr = clean_kr_address(rev.address)
        except: pass
        safe_rerun()

    # 2. 수정 위치 지정 버튼 (청색)
    st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
    if st.button("🎯 지도 중앙을 수정 위치로 지정"):
        sd.m_mode = "정보 수정"
        target_loc = sd.crosshair_center if sd.crosshair_center else sd.base_center
        sd.t_la, sd.t_lo = target_loc[0], target_loc[1]
        
        # [핵심 고정] 수정 시 지도가 원래 자리로 튕겨 돌아가지 않도록 고정
        sd.base_center = [target_loc[0], target_loc[1]]
        
        try:
            rev = geolocator.reverse(f"{sd.t_la}, {sd.t_lo}")
            if rev: sd.v_addr = clean_kr_address(rev.address)
        except: pass
        safe_rerun() 

    # 3. 데이터 등록 예약석 (녹색 버튼)
    save_btn_placeholder = st.empty()

    st.divider()

    st.subheader("📋 정보 원클릭 복사")
    cur_la = sd.t_la if sd.t_la is not None else sd.base_center[0]
    cur_lo = sd.t_lo if sd.t_lo is not None else sd.base_center[1]
    st.code(get_google_format(cur_la, cur_lo), language=None)
    st.code(sd.v_addr if sd.v_addr else "위치를 지정하세요", language=None)

    st.divider()
    
    prev_mode = sd.m_mode
    mode_opts = ["신규 등록", "정보 수정", "데이터 삭제"]
    m_idx = mode_opts.index(sd.m_mode) if sd.m_mode in mode_opts else 0
    sd.m_mode = st.radio("🛠️ 현재 작업 모드 상태", mode_opts, index=m_idx, horizontal=True)
    
    if prev_mode != sd.m_mode:
        if sd.m_mode == "신규 등록":
            sd.t_la, sd.t_lo, sd.v_addr, sd.last_loaded_nm = None, None, "", None
            for s in SL: sd[f"ch_{s}"] = ""
        else: sd.t_la, sd.t_lo = None, None

    v_nm, final_reg, v_cat = "", "", "중계소"

    if sd.m_mode == "신규 등록":
        st.subheader("🆕 신규 시설 등록")
        reg_opts = ["+ 직접 입력"] + existing_regs
        sel_reg = st.selectbox("1. 지역 선택", reg_opts)
        final_reg = st.text_input("📝 새 지역 명칭", "") if sel_reg == "+ 직접 입력" else sel_reg
        v_nm = st.text_input("2. 시설 이름")
        v_cat = st.radio("3. 시설 구분", ["송신소", "중계소"], horizontal=True)
        
        addr_api_query = st.text_input("4. 주소 검색(API)", "")
        if st.button("🏠 주소 자동 찾기"):
            if addr_api_query:
                try:
                    loc = geolocator.geocode(addr_api_query)
                    if loc:
                        sd.v_addr, sd.t_la, sd.t_lo = clean_kr_address(loc.address), loc.latitude, loc.longitude
                        sd.base_center, sd.base_zoom = [loc.latitude, loc.longitude], 16
                        safe_rerun()
                except: st.error("검색 실패")
        
        sd.v_addr = st.text_area("5. 주소 확인/수정", value=sd.v_addr)
        c_la, c_lo = st.columns(2)
        sd.t_la = c_la.number_input("6. 위도(Dec)", value=float(cur_la), format="%.6f")
        sd.t_lo = c_lo.number_input("7. 경도(Dec)", value=float(cur_lo), format="%.6f")

    elif sd.m_mode == "정보 수정":
        st.subheader("⚙️ 시설 정보 수정")
        names = sd.df[sd.df['지역'] == sd.sel_reg]['이름'].tolist() if sd.sel_reg != "전체" else sd.df['이름'].tolist()
        if names:
            tgt_idx = names.index(sd.target_nm) if sd.target_nm in names else 0
            sd.target_nm = st.selectbox("대상 선택", names, index=tgt_idx)
            row = sd.df[sd.df['이름'] == sd.target_nm].iloc[0]
            
            v_nm = st.text_input("시설 이름", value=row['이름'])
            final_reg = st.text_input("지역 명칭", value=row['지역'])
            v_cat = st.radio("구분", ["송신소", "중계소"], index=0 if row['구분']=="송신소" else 1, horizontal=True)
            
            if sd.last_loaded_nm != sd.target_nm:
                sd.t_la, sd.t_lo, sd.v_addr = float(row['위도']), float(row['경도']), str(row['주소'])
                for s in SL: sd[f"ch_{s}"] = str(row[s])
                sd.last_loaded_nm = sd.target_nm
            
            sd.v_addr = st.text_area("주소 수정", value=sd.v_addr)    
                
            c_la, c_lo = st.columns(2)
            safe_la = float(sd.t_la) if sd.t_la is not None else float(row['위도'])
            safe_lo = float(sd.t_lo) if sd.t_lo is not None else float(row['경도'])
            
            sd.t_la = c_la.number_input("위도(Dec)", value=safe_la, format="%.6f")
            sd.t_lo = c_lo.number_input("경도(Dec)", value=safe_lo, format="%.6f")
        else: st.warning("데이터 없음"); final_reg, v_cat, v_nm = "", "중계소", ""
        
    elif sd.m_mode == "데이터 삭제":
        st.subheader("🗑️ 데이터 삭제")
        names = sd.df[sd.df['지역'] == sd.sel_reg]['이름'].tolist() if sd.sel_reg != "전체" else sd.df['이름'].tolist()
        if names:
            del_target = st.selectbox("삭제 시설 선택", names)
            if st.button("🚨 삭제 실행", type="primary"):
                sd.history.append(sd.df.copy())
                sd.df = sd.df[sd.df['이름'] != del_target]
                sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                st.success(f"[{del_target}] 시설이 삭제되었습니다."); st.rerun()

    if sd.m_mode in ["신규 등록", "정보 수정"]:
        st.divider()
        st.info("📺 물리 채널 설정")
        
        st.markdown("**📡 DTV 채널**")
        d_cols = st.columns(3)
        for i, s in enumerate(SL_DTV): d_cols[i%3].text_input(s, key=f"ch_{s}")
        
        st.markdown("**✨ UHD 채널**")
        u_cols = st.columns(3)
        for i, s in enumerate(SL_UHD): u_cols[i%3].text_input(s, key=f"ch_{s}")

        # [명칭 통일] 녹색 버튼의 텍스트를 모드 상관없이 "✅ 데이터 등록"으로 통일
        with save_btn_placeholder:
            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
            if st.button("✅ 데이터 등록"):
                if v_nm and final_reg:
                    sd.history.append(sd.df.copy())
                    v = [final_reg, v_cat, v_nm] + [sd[f"ch_{s}"] for s in SL] + [str(cur_la), str(cur_lo), sd.v_addr]
                    if sd.m_mode == "정보 수정": sd.df.loc[sd.df['이름'] == sd.target_nm] = v
                    else: sd.df = pd.concat([sd.df, pd.DataFrame([v], columns=CL)], ignore_index=True)
                    sd.df.to_csv(DB, index=False, encoding='utf-8-sig')
                    sd.t_la, sd.t_lo, sd.v_addr, sd.last_loaded_nm = None, None, "", None 
                    st.success("데이터가 안전하게 등록되었습니다!"); st.rerun() 

# ---------------------------------------------------------
# 본문: 지도 및 데이터 현황
# ---------------------------------------------------------
st.title(f"📡 {sd.sel_reg} 방송 인프라 관제 마스터")

disp_df = sd.df if sd.sel_reg == "전체" else sd.df[sd.df['지역'] == sd.sel_reg]

map_container = st.container()
with map_container:
    css_injection = """
    <style>
    .map-crosshair { position: absolute; top: 50%; left: 50%; margin-left: -20px; margin-top: -20px; width: 40px; height: 40px; border: 2px solid #ff4b4b; border-radius: 50%; z-index: 9999; pointer-events: none; }
    .map-crosshair::before { content: ''; position: absolute; top: 18px; left: -10px; width: 56px; height: 2px; background: #ff4b4b; }
    .map-crosshair::after { content: ''; position: absolute; left: 18px; top: -10px; height: 56px; width: 2px; background: #ff4b4b; }
    .leaflet-popup-content-wrapper { min-width: 500px !important; width: 500px !important; }
    .leaflet-popup-content { min-width: 480px !important; width: 480px !important; margin: 13px !important; }
    </style>
    <div class="map-crosshair"></div>
    """
    
    m = folium.Map(location=sd.base_center, zoom_start=sd.base_zoom, tiles='https://mt1.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}', attr='G')
    m.get_root().html.add_child(folium.Element(css_injection))

    for _, r in disp_df.iterrows():
        is_editing_this = (sd.m_mode == "정보 수정" and sd.target_nm == r['이름'])
        lat = float(sd.t_la) if (is_editing_this and sd.t_la) else float(r['위도'])
        lon = float(sd.t_lo) if (is_editing_this and sd.t_lo) else float(r['경도'])
            
        p, color = [lat, lon], ('red' if r['구분'] == '송신소' else 'blue')
        dt_pop, uh_pop = "|".join([f"{s}:{r[s]}" for s in SL_DTV]), "|".join([f"{s}:{r[s]}" for s in SL_UHD])
        
        p_html = f"""
        <div style='font-family: sans-serif; padding-top: 5px;'>
            <div style='font-size:20px; font-weight:bold; color:#333; margin-bottom:6px;'>[{r['구분']}] {r['이름']}</div>
            <div style='color:#666; font-size:15px; margin-bottom:12px;'>{r['주소']}</div>
            <div style='font-size:17px; margin-bottom:8px; line-height:1.4;'><b>📡 DTV:</b><br>{dt_pop}</div>
            <div style='font-size:17px; line-height:1.4;'><b>✨ UHD:</b><br>{uh_pop}</div>
        </div>
        """
        
        folium.Marker(p, icon=folium.DivIcon(html=f'<div style="display:inline-block;padding:4px 10px;background:white;border:2px solid {color};border-radius:6px;color:{color};font-size:10pt;font-weight:bold;white-space:nowrap;transform:translate(15px,-35px);">[{r["구분"]}] {r["이름"]}</div>')).add_to(m)
        folium.Marker(p, icon=folium.Icon(color=color, icon='tower-broadcast', prefix='fa'), popup=folium.Popup(p_html, min_width=500, max_width=500)).add_to(m)

    # [핵심] 신규 등록 시 나타나던 임시 녹색 마커 코드 완전 삭제

    map_data = st_folium(m, use_container_width=True, height=900, key=f"map_v370_{sd.map_key}", returned_objects=["center"])

if map_data and map_data.get("center"):
    sd.crosshair_center = [map_data["center"]["lat"], map_data["center"]["lng"]]

st.divider()
st.subheader("📊 데이터 현황")
view_df = disp_df.copy()
view_df['통합 좌표'] = view_df.apply(lambda x: get_google_format(x['위도'], x['경도']), axis=1)
event = st.dataframe(view_df[['지역', '구분', '이름'] + SL + ['통합 좌표', '주소']], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, key="main_table")

if event and event.get("selection", {}).get("rows"):
    idx = event["selection"]["rows"][0]; sel = disp_df.iloc[idx]
    if sd.target_nm != sel['이름']:
        sd.base_center, sd.base_zoom = [float(sel['위도']), float(sel['경도'])], 16
        sd.m_mode, sd.target_nm = "정보 수정", sel['이름']
        sd.v_addr, sd.t_la, sd.t_lo = str(sel['주소']), float(sel['위도']), float(sel['경도'])
        
        sd.last_loaded_nm = None 
        safe_rerun()

st.download_button("📥 CSV 백업", data=sd.df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), file_name='stations.csv')
