import streamlit as st
import os
import subprocess
import ssl
import google.generativeai as genai
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH HỆ THỐNG ---
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# --- LẤY API KEY TỪ SECRETS (Để không phải nhập lại) ---
# Nếu bạn chưa cài Secrets, nó sẽ báo lỗi hoặc dùng chế độ chờ
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- HÀM CÀI TRÌNH DUYỆT ---
def ensure_playwright_installed():
    if 'playwright_ready' not in st.session_state:
        try:
            subprocess.run(["playwright", "install", "chromium"], check=True)
            subprocess.run(["playwright", "install-deps"], check=True)
            st.session_state['playwright_ready'] = True
        except:
            pass

# --- HÀM LẤY ẢNH CHỤP MÀN HÌNH (Mô phỏng người dùng thật) ---
def get_vessel_screenshots(name, imo):
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={'width': 1280, 'height': 1600})
            page = context.new_page()

            # --- 1. OFAC ---
            try:
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(5000)
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = str(e)

            # --- 2. OPENSANCTIONS (Gõ phím thủ công) ---
            try:
                page.goto("https://www.opensanctions.org/advancedsearch/", timeout=60000)
                # Đợi form hiện ra
                page.wait_for_selector('input[name="caption"]')
                
                # Chọn loại thực thể là Vessel
                page.select_option('select[name="schema"]', value='Vessel')
                
                # Gõ tên tàu
                page.type('input[name="caption"]', name, delay=100)
                
                # Gõ số IMO - Chúng ta tìm ô input có name chứa imoNumber
                page.type('input[name="properties.imoNumber"]', imo, delay=100)
                
                # Nhấn nút Match
                page.click('button:has-text("Match"), button[type="submit"]')
                
                # Đợi bảng kết quả hiện ra (quan trọng)
                page.wait_for_timeout(10000)
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = str(e)

            browser.close()
    except Exception as e:
        results['system_err'] = str(e)
    return results

# --- HÀM AI (Dùng Gemini ổn định) ---
def ask_ai_conclusion(name, imo):
    if not GEMINI_KEY:
        return "⚠️ API Key chưa được cài đặt trong Secrets. Vui lòng cài đặt để dùng AI."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Research vessel {name} (IMO {imo}). Is it sanctioned? Visited Russia in last 12 months? Answer in exactly one English sentence."
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Lỗi AI: {str(e)}"

# --- GIAO DIỆN ---
st.set_page_config(page_title="Vessel Sanction Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        ensure_playwright_installed()
        
        with st.spinner("Hệ thống đang làm việc..."):
            # 1. Chụp ảnh
            imgs = get_vessel_screenshots(v_name, v_imo)
            
            # 2. AI Conclusion
            conclusion = ask_ai_conclusion(v_name, v_imo)
            st.subheader("📝 AI Conclusion:")
            st.success(conclusion)
            
            st.divider()
            
            # 3. Hiển thị ảnh
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🌐 OFAC Result")
                if 'ofac' in imgs: st.image("ofac.png")
                else: st.error(f"Lỗi: {imgs.get('ofac_err')}")
            with col2:
                st.subheader("🌐 OpenSanctions Result")
                     if 'os' in imgs: st.image("os.png")
                else: st.error(f"Lỗi: {imgs.get('os_err')}")
    else:
        st.warning("Vui lòng nhập đủ Tên tàu và IMO!")
