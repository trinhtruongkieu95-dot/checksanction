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
        subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
    except:
        os.system("python -m playwright install chromium")

# --- HÀM LẤY ẢNH CHỤP MÀN HÌNH ---
def get_vessel_screenshots(name, imo):
    results = {}
    try:
        with sync_playwright() as p:
            # Khởi chạy trình duyệt
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={'width': 1280, 'height': 1600})
            page = context.new_page()

            # --- 1. THAO TÁC OFAC ---
            try:
                st.write("🔄 Đang kiểm tra OFAC...")
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(6000)
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = f"OFAC Error: {e}"

            # --- 2. THAO TÁC OPENSANCTIONS (ẤN MATCH) ---
            try:
                st.write("🔄 Đang đối soát OpenSanctions (Match)...")
                # Truy cập link có sẵn dữ liệu điền vào ô
                os_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_url, timeout=60000)
                
                # Đợi nút Match (nút submit) hiện ra và nhấn vào
                page.wait_for_selector('button[type="submit"]')
                page.click('button[type="submit"]')
                
                # CHỜ ĐỢI KẾT QUẢ HIỆN RA (Đây là phần bạn cần)
                # Đợi 8 giây để hệ thống tính toán điểm Match
                page.wait_for_timeout(8000)
                
                # Chụp ảnh sau khi đã có kết quả
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = f"OpenSanctions Error: {e}"

            browser.close()
    except Exception as e:
        st.error(f"Lỗi trình duyệt: {e}")
    return results

# --- HÀM HỎI AI MIỄN PHÍ ---
def ask_free_ai(name, imo):
    prompt = f"Act as a maritime expert. Research vessel {name} (IMO {imo}). Is it sanctioned? Visited Russia in last 12 months? Answer in exactly one English sentence."
    try:
        # Cách gọi mới nhất của thư viện DDGS
        with DDGS() as ddgs:
            response = ddgs.chat(prompt, model='gpt-4o-mini')
            return response
    except Exception as e:
        # Nếu chat lỗi, thử dùng tìm kiếm văn bản thông thường làm dự phòng
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(f"vessel {name} IMO {imo} sanctions Russia", max_results=1))
                if search_results:
                    return f"AI Conclusion (Search-based): {search_results[0]['body'][:200]}..."
        except:
            pass
        return "AI temporary unavailable. Please verify manually via the screenshots below."

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Vessel Sanction Tool", layout="wide")
st.title("🚢 Vessel Sanction Tool")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        install_playwright()
        
        # 1. AI Conclusion
        st.subheader("📝 AI Conclusion:")
        with st.spinner("Đang phân tích dữ liệu..."):
            conclusion = ask_free_ai(v_name, v_imo)
            st.success(conclusion)
        
        st.divider()
        
        # 2. Screenshots
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
        st.warning("Vui lòng nhập đủ Tên tàu và IMO!")
