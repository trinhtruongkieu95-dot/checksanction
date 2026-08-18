import streamlit as st
import os
import subprocess
import requests
import google.generativeai as genai
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
            # Tham số args bắt buộc để chạy trên Cloud Linux
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={'width': 1280, 'height': 1400})
            page = context.new_page()

            # --- 1. QUY TRÌNH OFAC ---
            try:
                st.write("🛰️ Đang thao tác trên trang OFAC...")
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                # Đợi bảng kết quả hiện lên
                page.wait_for_timeout(7000)
                page.screenshot(path="ofac_web.png", full_page=True)
                results['ofac'] = "ofac_web.png"
            except Exception as e: 
                results['ofac_err'] = f"Lỗi OFAC: {str(e)}"

            # --- 2. QUY TRÌNH OPENSANCTIONS (Điền và Click Match) ---
            try:
                st.write("🛰️ Đang thao tác trên trang OpenSanctions...")
                # Truy cập thẳng trang advanced search
                page.goto("https://www.opensanctions.org/advancedsearch/", timeout=60000)
                
                # Chọn Schema là Vessel
                page.select_option('select[name="schema"]', value='Vessel')
                # Điền tên tàu
                page.fill('input[name="caption"]', name)
                # Điền số IMO (Tìm ô nhập có chứa từ khóa imo)
                # OpenSanctions dùng cấu trúc động, điền qua URL là chắc chắn nhất sau đó click
                os_fill_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_fill_url)
                
                # QUAN TRỌNG: Nhấn nút Search/Match để kích hoạt kết quả
                # Tìm nút Submit của form
                page.keyboard.press("Enter") 
                page.click('button[type="submit"]')
                
                # Đợi cho đến khi danh sách kết quả (hoặc thông báo không tìm thấy) hiện ra
                page.wait_for_timeout(8000) 
                
                # Chụp toàn bộ trang kết quả
                page.screenshot(path="os_web.png", full_page=True)
                results['os'] = "os_web.png"
            except Exception as e: 
                results['os_err'] = f"Lỗi OpenSanctions: {str(e)}"

            browser.close()
    except Exception as e:
        st.error(f"Lỗi hệ thống trình duyệt: {e}")
    return results

# --- HÀM HỎI AI (Hỗ trợ cả mã AQ. và AIzaSy) ---
def ask_gemini_hybrid(name, imo, key):
    if not key:
        return "⚠️ Vui lòng nhập API Key hoặc Token ở cột bên trái."
    
    prompt = f"Research vessel {name} (IMO {imo}). Is it sanctioned? Visited Russia in last 12 months? Answer 1 English sentence."
    
    # Dùng phương thức POST trực tiếp để chấp nhận cả Token tạm thời (AQ.)
    if key.startswith("AQ."):
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            return f"❌ Token AQ. đã hết hạn (Lỗi {response.status_code})."
        except: return "❌ Không thể kết nối AI."

    elif key.startswith("AIza"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            return f"❌ API Key sai (Lỗi {response.status_code})."
        except: return "❌ Lỗi kết nối AI."
    
    return "⚠️ Định dạng mã không đúng (Phải là AQ. hoặc AIzaSy)."

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="Vessel Sanction Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")

with st.sidebar:
    st.header("Nhập liệu")
    user_key = st.text_input("Nhập Gemini API Key / Token", type="password")
    v_name = st.text_input("Tên tàu (Vessel Name)")
    v_imo = st.text_input("Số IMO")
    btn_check = st.button("Bắt đầu kiểm tra")

if btn_check:
    if v_name and v_imo:
        install_playwright()
        
        # 1. AI Conclusion
        st.subheader("📝 AI Conclusion:")
        with st.spinner("AI đang tra cứu..."):
            ai_info = ask_gemini_hybrid(v_name, v_imo, user_key)
            st.success(ai_info) if "❌" not in ai_info else st.error(ai_info)
        
        st.divider()
        
        # 2. Screenshots
        with st.spinner("Đang chụp ảnh thực tế từ các website..."):
            imgs = get_vessel_screenshots(v_name, v_imo)
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🌐 OFAC Result")
                if 'ofac' in imgs: st.image(imgs['ofac'], use_container_width=True)
                else: st.error(imgs.get('ofac_err'))
            with col2:
                st.subheader("🌐 OpenSanctions Result")
                if 'os' in imgs: st.image(imgs['os'], use_container_width=True)
                else: st.error(imgs.get('os_err'))
    else:
        st.sidebar.error("Vui lòng nhập đủ thông tin!")
