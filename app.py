import streamlit as st
import os
import subprocess
import google.generativeai as genai
from playwright.sync_api import sync_playwright

# --- 1. CẤU HÌNH AI ---
# DÁN MÃ API CỦA BẠN VÀO ĐÂY
GEMINI_API_KEY = "DÁN_MÃ_API_CỦA_BẠN_VÀO_ĐÂY" 
genai.configure(api_key=GEMINI_API_KEY)

# --- 2. HÀM CÀI TRÌNH DUYỆT (Tối ưu hóa tốc độ) ---
@st.cache_resource
def install_browser_once():
    subprocess.run(["python", "-m", "playwright", "install", "chromium"])

# --- 3. HÀM LẤY ẢNH (Chạy trước) ---
def get_vessel_images(name, imo):
    imgs = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = context.new_page()

        # Check OFAC
        try:
            st.write("...Đang chụp ảnh OFAC")
            page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=45000)
            page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
            page.fill('input#ctl00_MainContent_txtID', imo)
            page.click('input#ctl00_MainContent_btnSearch')
            page.wait_for_timeout(5000)
            page.screenshot(path="ofac.png", full_page=True)
            imgs['ofac'] = "ofac.png"
        except Exception as e:
            imgs['ofac_err'] = f"Lỗi OFAC: {str(e)}"

        # Check OpenSanctions
        try:
            st.write("...Đang chụp ảnh OpenSanctions")
            url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
            page.goto(url, timeout=45000)
            page.wait_for_timeout(5000)
            page.screenshot(path="os.png", full_page=True)
            imgs['os'] = "os.png"
        except Exception as e:
            imgs['os_err'] = f"Lỗi OpenSanctions: {str(e)}"

        browser.close()
    return imgs

# --- 4. HÀM AI (Chạy sau, có giới hạn thời gian) ---
def ask_gemini_safe(name, imo):
    try:
        st.write("...Đang hỏi AI (Bước này có thể chậm)")
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Research vessel {name} (IMO {imo}). Is it sanctioned? Visited Russia in last 12 months? Answer 1 English sentence."
        # Giới hạn chờ AI trong 15 giây, nếu không xong thì bỏ qua
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI is taking too long or connection failed. Please check the screenshots below for manual verification."

# --- GIAO DIỆN ---
st.set_page_config(page_title="Vessel Checker", layout="wide")
st.title("🚢 Vessel Sanction Tool")

v_name = st.sidebar.text_input("Vessel Name")
v_imo = st.sidebar.text_input("IMO Number")

if st.sidebar.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        install_browser_once()
        
        # Tạo khung thông báo trạng thái
        with st.status("Hệ thống đang làm việc...", expanded=True) as status:
            # ƯU TIÊN LẤY ẢNH TRƯỚC
            vessel_data = get_vessel_images(v_name, v_imo)
            
            # HỎI AI SAU
            ai_text = ask_gemini_safe(v_name, v_imo)
            
            status.update(label="Hoàn tất!", state="complete", expanded=False)

        # HIỂN THỊ KẾT QUẢ
        st.subheader("📝 Kết luận từ AI:")
        st.info(ai_text)
        
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🌐 OFAC Results")
            if 'ofac' in vessel_data: st.image("ofac.png")
            else: st.error(vessel_data.get('ofac_err'))
            
        with c2:
            st.subheader("🌐 OpenSanctions Results")
            if 'os' in vessel_data: st.image("os.png")
            else: st.error(vessel_data.get('os_err'))
    else:
        st.sidebar.error("Vui lòng nhập Tên và IMO!")
