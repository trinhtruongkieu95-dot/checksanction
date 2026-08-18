import streamlit as st
import os
import subprocess
import google.generativeai as genai
from playwright.sync_api import sync_playwright

# --- 1. CẤU HÌNH AI (Thay mã API của bạn) ---
GEMINI_API_KEY = "DÁN_MÃ_API_CỦA_BẠN_VÀO_ĐÂY" 
genai.configure(api_key=GEMINI_API_KEY)

# --- 2. HÀM TỰ CÀI TRÌNH DUYỆT (Chỉ chạy 1 lần duy nhất) ---
def install_playwright():
    if not os.path.exists("/home/appuser/.cache/ms-playwright"):
        subprocess.run(["python", "-m", "playwright", "install", "chromium"])

# --- 3. HÀM CHÍNH LẤY DỮ LIỆU ---
def run_check_sync(name, imo):
    results = {}
    with sync_playwright() as p:
        # Khởi động trình duyệt
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 1200})
        page = context.new_page()

        # Check OFAC
        try:
            st.write("🔍 Đang kiểm tra OFAC...")
            page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
            page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
            page.fill('input#ctl00_MainContent_txtID', imo)
            page.click('input#ctl00_MainContent_btnSearch')
            page.wait_for_timeout(5000) # Đợi 5 giây
            page.screenshot(path="ofac.png", full_page=True)
            results['ofac'] = "ofac.png"
        except Exception as e:
            results['ofac_err'] = f"Lỗi OFAC: {str(e)}"

        # Check OpenSanctions
        try:
            st.write("🔍 Đang kiểm tra OpenSanctions...")
            url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path="os.png", full_page=True)
            results['os'] = "os.png"
        except Exception as e:
            results['os_err'] = f"Lỗi OpenSanctions: {str(e)}"

        browser.close()
    return results

def ask_gemini(name, imo):
    try:
        st.write("🤖 Đang hỏi ý kiến AI...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Research vessel {name} IMO {imo}. Is it sanctioned? Visited Russia in last 12 months? Answer 1 English sentence."
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI Error: Could not connect to Gemini."

# --- 4. GIAO DIỆN ---
st.set_page_config(page_title="Vessel Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")

# Input ở sidebar
v_name = st.sidebar.text_input("Vessel Name")
v_imo = st.sidebar.text_input("IMO Number")

if st.sidebar.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        # Bước 1: Cài trình duyệt (nếu cần)
        install_playwright()
        
        # Bước 2: Chạy kiểm tra
        with st.status("Đang xử lý dữ liệu...", expanded=True) as status:
            conclusion = ask_gemini(v_name, v_imo)
            data = run_check_sync(v_name, v_imo)
            status.update(label="Kiểm tra hoàn tất!", state="complete", expanded=False)

        # Bước 3: Hiển thị kết quả
        st.subheader("📝 Kết luận từ AI:")
        st.success(conclusion)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("📸 Ảnh chụp OFAC:")
            if 'ofac' in data: st.image("ofac.png")
            else: st.error(data.get('ofac_err'))
            
        with col2:
            st.write("📸 Ảnh chụp OpenSanctions:")
            if 'os' in data: st.image("os.png")
            else: st.error(data.get('os_err'))
    else:
        st.sidebar.warning("Vui lòng điền đủ Tên và IMO!")
