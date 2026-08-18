import streamlit as st
import os
import subprocess
import ssl
from playwright.sync_api import sync_playwright
from duckduckgo_search import DDGS

# --- CẤU HÌNH HỆ THỐNG ---
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# --- HÀM CÀI TRÌNH DUYỆT ---
def ensure_playwright_installed():
    if 'playwright_ready' not in st.session_state:
        try:
            subprocess.run(["playwright", "install", "chromium"], check=True)
            subprocess.run(["playwright", "install-deps"], check=True)
            st.session_state['playwright_ready'] = True
        except:
            pass

# --- HÀM LẤY ẢNH CHỤP MÀN HÌNH ---
def get_vessel_screenshots(name, imo):
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={'width': 1280, 'height': 1600})
            page = context.new_page()

            # --- 1. OFAC (Hoạt động tốt) ---
            try:
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(5000)
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = str(e)

            # --- 2. OPENSANCTIONS (SỬA LỖI TIMEOUT) ---
            try:
                # Truy cập thẳng link search kèm tham số để tránh lỗi không tìm thấy ô nhập
                os_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_url, timeout=60000)
                
                # Chờ trang load rồi tìm nút "Match" (thường là nút duy nhất màu xanh lá)
                page.wait_for_timeout(5000)
                
                # Nhấn Enter để submit form nếu nút bị che
                page.keyboard.press("Enter")
                
                # Cố gắng click vào nút có chữ Match
                try:
                    page.click('button:has-text("Match")', timeout=5000)
                except:
                    pass
                
                # Đợi kết quả đối soát hiện ra
                page.wait_for_timeout(10000)
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = str(e)

            browser.close()
    except Exception as e:
        results['system_err'] = str(e)
    return results

# --- HÀM AI (DÙNG DUCKDUCKGO AI - KHÔNG CẦN KEY) ---
def ask_free_ai(name, imo):
    prompt = f"Research vessel {name} (IMO {imo}). Is it on any international sanction lists? Did it visit Russia in the last 12 months? Answer in exactly one English sentence."
    try:
        with DDGS() as ddgs:
            # Gọi AI của DuckDuckGo (Miễn phí, không cần Key)
            response = ddgs.chat(prompt, model='gpt-4o-mini')
            return response
    except Exception as e:
        return f"AI temporary unavailable (Search mode). Based on common data, please check the official screenshots below for {name} ({imo})."

# --- GIAO DIỆN ---
st.set_page_config(page_title="Vessel Sanction Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")
st.caption("Phiên bản tự động hóa - Không cần API Key")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        ensure_playwright_installed()
        
        with st.spinner("Đang thực hiện kiểm tra (vui lòng đợi 30-45 giây)..."):
            # 1. Chụp ảnh trước (Ưu tiên bằng chứng)
            imgs = get_vessel_screenshots(v_name, v_imo)
            
            # 2. AI Conclusion (Dùng bản không Key)
            conclusion = ask_free_ai(v_name, v_imo)
            st.subheader("📝 AI Conclusion:")
            st.success(conclusion)
            
            st.divider()
            
            # 3. Hiển thị ảnh
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🌐 OFAC Result")
                if 'ofac' in imgs: st.image("ofac.png")
                else: st.error(f"Lỗi OFAC: {imgs.get('ofac_err')}")
            with col2:
                st.subheader("🌐 OpenSanctions Result")
                if 'os' in imgs: st.image("os.png")
                else: st.error("Lỗi: OpenSanctions không phản hồi hoặc đang bận. Vui lòng thử lại.")
    else:
        st.warning("Vui lòng nhập đủ Tên tàu và IMO!")
