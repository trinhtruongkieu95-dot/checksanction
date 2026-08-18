import streamlit as st
import os
import subprocess
import requests
from openai import OpenAI
from playwright.sync_api import sync_playwright
import ssl

# --- CẤU HÌNH HỆ THỐNG ---
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# --- ĐIỀN API KEY CHATGPT TẠI ĐÂY (Mã bắt đầu bằng sk-...) ---
OPENAI_API_KEY = "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"

# Khởi tạo OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

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
                page.wait_for_timeout(6000) # Đợi kết quả
                page.screenshot(path="ofac.png", full_page=True)
                results['ofac'] = "ofac.png"
            except Exception as e: results['ofac_err'] = f"OFAC Error: {e}"

            # --- 2. THAO TÁC OPENSANCTIONS (ẤN MATCH/SEARCH) ---
            try:
                # Dùng URL chứa sẵn thông tin để điền nhanh
                os_url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(os_url, timeout=60000)
                
                # Tìm và nhấn nút Search/Submit để kích hoạt Match dữ liệu
                # Thử nhấn Enter trước
                page.keyboard.press("Enter")
                # Sau đó tìm nút có chữ Search hoặc type submit để click cho chắc chắn
                try:
                    page.click('button[type="submit"]', timeout=5000)
                except:
                    pass
                
                # Đợi trang web xử lý dữ liệu Matching
                page.wait_for_timeout(8000)
                page.screenshot(path="os.png", full_page=True)
                results['os'] = "os.png"
            except Exception as e: results['os_err'] = f"OpenSanctions Error: {e}"

            browser.close()
    except Exception as e:
        st.error(f"Browser Error: {e}")
    return results

# --- HÀM HỎI CHATGPT (OpenAI) ---
def ask_chatgpt(name, imo):
    try:
        prompt = f"""
        Research the vessel '{name}' with IMO number '{imo}'.
        1. Check if this vessel is on any international sanction lists (UN, US, EU, UK).
        2. Check if this vessel has visited any Russian ports or territory in the last 12 months.
        Provide a final conclusion in exactly one English sentence.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o", # Hoặc dùng "gpt-3.5-turbo" nếu muốn tiết kiệm
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ChatGPT Error: {str(e)}"

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Vessel Sanction Checker", layout="wide")
st.title("🚢 Vessel Sanction Checker (ChatGPT Edition)")

v_name = st.text_input("Tên tàu (Vessel Name)")
v_imo = st.text_input("Số IMO")

if st.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        install_playwright()
        
        # 1. Hiển thị Kết luận AI trước
        st.subheader("📝 AI Conclusion (ChatGPT):")
        with st.spinner("ChatGPT đang phân tích dữ liệu..."):
            conclusion = ask_chatgpt(v_name, v_imo)
            st.success(conclusion)
        
        st.divider()
        
        # 2. Hiển thị Screenshots
        with st.spinner("Hệ thống đang chụp ảnh bằng chứng thực tế..."):
            imgs = get_vessel_screenshots(v_name, v_imo)
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌐 OFAC Source")
                if 'ofac' in imgs: st.image(imgs['ofac'], use_container_width=True)
                else: st.error(imgs.get('ofac_err'))
                
            with col2:
                st.subheader("🌐 OpenSanctions Source")
                if 'os' in imgs: st.image(imgs['os'], use_container_width=True)
                else: st.error(imgs.get('os_err'))
    else:
        st.warning("Vui lòng điền đủ Tên tàu và mã IMO!")
