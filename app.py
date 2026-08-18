import ssl
import os

# Bỏ qua kiểm tra chứng chỉ SSL để tránh lỗi kết nối trên Cloud
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_contextimport streamlit as st
import os
import subprocess
import google.generativeai as genai
from playwright.sync_api import sync_playwright

# --- 1. CẤU HÌNH AI ---
# DÁN MÃ API CỦA BẠN VÀO ĐÂY
GEMINI_API_KEY = "AQ.Ab8RN6JVNRldaH4hz2ECZeyWfptwIkdws7eh-_Ijdo575yI96A"
genai.configure(api_key=GEMINI_API_KEY)

# --- 2. HÀM CÀI TRÌNH DUYỆT (Chạy ngay khi khởi động) ---
def install_playwright():
    try:
        # Lệnh cài đặt trình duyệt cho Linux Cloud
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except:
        os.system("python -m playwright install chromium")

# Gọi hàm cài đặt ngay đầu app
if 'browser_installed' not in st.session_state:
    with st.spinner("Đang khởi tạo hệ thống trình duyệt..."):
        install_playwright()
        st.session_state['browser_installed'] = True

# --- 3. HÀM LẤY ẢNH ---
def get_vessel_images(name, imo):
    imgs = {}
    try:
        with sync_playwright() as p:
            # Các tham số args dưới đây là BẮT BUỘC để chạy trên Cloud
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(viewport={'width': 1280, 'height': 1000})
            page = context.new_page()

            # Check OFAC
            try:
                page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
                page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
                page.fill('input#ctl00_MainContent_txtID', imo)
                page.click('input#ctl00_MainContent_btnSearch')
                page.wait_for_timeout(5000)
                page.screenshot(path="ofac.png", full_page=True)
                imgs['ofac'] = "ofac.png"
            except Exception as e:
                imgs['ofac_err'] = f"OFAC: {str(e)}"

            # Check OpenSanctions
            try:
                url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
                page.goto(url, timeout=60000)
                page.wait_for_timeout(5000)
                page.screenshot(path="os.png", full_page=True)
                imgs['os'] = "os.png"
            except Exception as e:
                imgs['os_err'] = f"OpenSanctions: {str(e)}"

            browser.close()
    except Exception as e:
        st.error(f"Lỗi khởi động trình duyệt: {str(e)}")
    return imgs

# --- 4. HÀM AI ---
def ask_gemini(name, imo):
    try:
        # Sử dụng model có hỗ trợ tra cứu internet (Grounding)
        # Lưu ý: 'gemini-1.5-flash' hoặc 'gemini-1.5-pro' đều hỗ trợ
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            tools=[{"google_search_retrieval": {}}] # Kích hoạt khả năng tra cứu Google
        )
        
        prompt = f"""
        Search for recent news and AIS tracking data for the vessel '{name}' (IMO {imo}).
        Answer these 2 points clearly:
        1. Is this vessel currently on any international sanction lists (OFAC, EU, UN, etc.)?
        2. Based on tracking data, has this vessel visited any Russian ports or entered Russian territorial waters in the last 12 months?
        
        Conclusion: Provide a final answer in exactly one English sentence covering both points.
        """
        
        # Gọi AI và cho phép nó sử dụng công cụ tìm kiếm
        response = model.generate_content(prompt)
        
        # Nếu AI trả về kết quả
        if response.text:
            return response.text
        else:
            return "AI returned an empty response. Please check your API Key limits."
            
    except Exception as e:
        # In ra lỗi cụ thể để bạn dễ debug nếu vẫn lỗi
        return f"AI Error: {str(e)}"

# --- GIAO DIỆN ---
st.set_page_config(page_title="Vessel Tool", layout="wide")
st.title("🚢 Vessel Sanction Tool")

v_name = st.sidebar.text_input("Vessel Name")
v_imo = st.sidebar.text_input("IMO Number")

if st.sidebar.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        with st.spinner("Đang thu thập dữ liệu..."):
            # Lấy AI trước
            ai_text = ask_gemini(v_name, v_imo)
            st.subheader("📝 AI Conclusion:")
            st.success(ai_text)
            
            st.divider()
            
            # Lấy ảnh sau
            vessel_data = get_vessel_images(v_name, v_imo)
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("🌐 OFAC Results")
                if 'ofac' in vessel_data: st.image("ofac.png")
                else: st.error(vessel_data.get('ofac_err'))
            with c2:
                st.write("🌐 OpenSanctions Results")
                if 'os' in vessel_data: st.image("os.png")
                else: st.error(vessel_data.get('os_err'))
    else:
        st.sidebar.warning("Nhập đủ thông tin!")
