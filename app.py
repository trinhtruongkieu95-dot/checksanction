import streamlit as st
import os
import subprocess
import ssl
from playwright.sync_api import sync_playwright
from duckduckgo_search import DDGS

# --- CẤU HÌNH HỆ THỐNG ---
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# --- HÀM CÀI TRÌNH DUYỆT (ÉP BUỘC) ---
def ensure_playwright_installed():
    # Kiểm tra xem trình duyệt đã tồn tại chưa, nếu chưa thì cài
    # Lệnh này sẽ chạy mỗi khi app khởi động để đảm bảo trình duyệt luôn sẵn sàng
    if 'playwright_ready' not in st.session_state:
        try:
            # Cài đặt chromium và các thành phần liên quan
            subprocess.run(["playwright", "install", "chromium"], check=True)
            # Ép buộc cài đặt các thành phần Linux cần thiết
            subprocess.run(["playwright", "install-deps"], check=True)
            st.session_state['playwright_ready'] = True
        except Exception as e:
            st.error(f"Lỗi khởi tạo trình duyệt: {e}")

# --- HÀM LẤY ẢNH CHỤP MÀN HÌNH ---
def get_vessel_screenshots(name, imo):
    results = {}
    try:
        with sync_playwright() as p:
            # Khởi chạy trình duyệt với chế độ chống lỗi trên Cloud
            browser = p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(viewport={'width': 1280, 'height': 1600})
            page = context.new_page()

            # --- 1. OFAC ---
            try:
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(8000) # Đợi web xử lý
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = str(e)

            # --- 2. OPENSANCTIONS (ẤN MATCH) ---
            try:
                os_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_url, timeout=60000)
                
                # Tìm và nhấn nút Match/Search
                # Chúng ta nhấn nút có thuộc tính type="submit"
                try:
                    page.wait_for_selector('button[type="submit"]', timeout=10000)
                    page.click('button[type="submit"]')
                except:
                    page.keyboard.press("Enter")
                
                # Đợi kết quả hiển thị (Tăng thời gian chờ lên 10 giây)
                page.wait_for_timeout(10000)
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = str(e)

            browser.close()
    except Exception as e:
        results['system_err'] = str(e)
    return results

# --- HÀM AI MIỄN PHÍ ---
def ask_ai_conclusion(name, imo):
    prompt = f"As a maritime expert, check if vessel {name} (IMO {imo}) is sanctioned or visited Russia in the last 12 months. Answer in exactly one English sentence."
    try:
        with DDGS() as ddgs:
            # Sử dụng phương thức chat mới nhất
            results = ddgs.chat(prompt, model='gpt-4o-mini')
            return results
    except:
        return "AI temporary unavailable. Please check the screenshots below for manual verification."

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Vessel Sanction Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        # Cài đặt trình duyệt ngay khi nhấn nút
        with st.spinner("Đang chuẩn bị trình duyệt hệ thống..."):
            ensure_playwright_installed()
        
        # 1. AI Conclusion
        st.subheader("📝 AI Conclusion:")
        with st.spinner("AI đang phân tích..."):
            conclusion = ask_ai_conclusion(v_name, v_imo)
            st.success(conclusion)
        
        st.divider()
        
        # 2. Screenshots
        with st.spinner("Đang chụp ảnh thực tế..."):
            imgs = get_vessel_screenshots(v_name, v_imo)
            
            if 'system_err' in imgs:
                st.error(f"Lỗi hệ thống trình duyệt: {imgs['system_err']}")
                st.info("Mẹo: Hãy nhấn 'Reboot App' trong menu Manage App nếu lỗi này lặp lại.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🌐 OFAC Result")
                if 'ofac' in imgs: st.image("ofac.png")
                else: st.error(f"Lỗi OFAC: {imgs.get('ofac_err')}")
            with col2:
                st.subheader("🌐 OpenSanctions Result")
                if 'os' in imgs: st.image("os.png")
                else: st.error(f"Lỗi OpenSanctions: {imgs.get('os_err')}")
    else:
        st.warning("Vui lòng nhập đủ Tên tàu và IMO!")
