import streamlit as st
import os
import subprocess
from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright
import ssl

# --- CẤU HÌNH HỆ THỐNG ---
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# --- HÀM TỰ CÀI TRÌNH DUYỆT ---
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except:
        os.system("python -m playwright install chromium")

# --- HÀM LẤY ẢNH CHỤP MÀN HÌNH ---
def get_vessel_screenshots(name, imo):
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={'width': 1280, 'height': 1600})
            page = context.new_page()

            # --- 1. THAO TÁC OFAC ---
            try:
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(7000)
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = f"OFAC Error: {e}"

            # --- 2. THAO TÁC OPENSANCTIONS (CẢI TIẾN NÚT MATCH) ---
            try:
                # Truy cập trang tìm kiếm nâng cao
                os_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_url, timeout=60000)
                
                # Thao tác nhấn nút Match/Search
                # Chúng ta sẽ thử nhấn Enter và click nút Submit của hệ thống
                page.wait_for_selector('button[type="submit"]')
                page.click('button[type="submit"]')
                
                # Đợi kết quả đối soát (Matching) trong 8 giây
                page.wait_for_timeout(8000)
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = f"OpenSanctions Error: {e}"

            browser.close()
    except Exception as e:
        st.error(f"Browser Error: {e}")
    return results

# --- HÀM HỎI AI (SỬ DỤNG DUCKDUCKGO AI - KHÔNG CẦN KEY) ---
def ask_free_ai(name, imo):
    try:
        prompt = f"""
        Act as a maritime security expert. Research the vessel '{name}' with IMO number '{imo}'.
        1. Check if this vessel is currently on any international sanction lists (UN, US OFAC, EU, UK).
        2. Based on recent tracking data, has this vessel visited any Russian ports or territory in the last 12 months?
        Conclusion: Provide a final answer in exactly one English sentence covering both sanction status and Russian port visits.
        """
        # Sử dụng thư viện duckduckgo_search để gọi AI miễn phí
        with DDGS() as ddgs:
            response = ddgs.chat(prompt, model='gpt-4o-mini')
            return response
    except Exception as e:
        return f"AI Error: Can't get conclusion at this moment. Please check screenshots below. (Details: {e})"

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Vessel Sanction Tool", layout="wide")
st.title("🚢 Vessel Sanction Tool (Free AI Edition)")
st.caption("Công cụ sử dụng AI miễn phí và không yêu cầu API Key.")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        install_playwright()
        
        # 1. Hiển thị Kết luận AI
        st.subheader("📝 AI Conclusion:")
        with st.spinner("AI đang tra cứu dữ liệu thời gian thực..."):
            conclusion = ask_free_ai(v_name, v_imo)
            st.success(conclusion)
        
        st.divider()
        
        # 2. Hiển thị Screenshots
        with st.spinner("Hệ thống đang chụp ảnh bằng chứng..."):
            imgs = get_vessel_screenshots(v_name, v_imo)
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌐 OFAC Source")
                if 'ofac' in imgs: st.image("ofac.png", use_container_width=True)
                else: st.error(imgs.get('ofac_err'))
                
            with col2:
                st.subheader("🌐 OpenSanctions Source")
                if 'os' in imgs: st.image("os.png", use_container_width=True)
                else: st.error(imgs.get('os_err'))
    else:
        st.warning("Vui lòng điền đủ Tên tàu và mã IMO!")
