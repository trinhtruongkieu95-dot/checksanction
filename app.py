import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import google.generativeai as genai
import os

# --- 1. ĐIỀN MÃ API CỦA BẠN VÀO ĐÂY ---
GEMINI_API_KEY = "AQ.Ab8RN6JVNRldaH4hz2ECZeyWfptwIkdws7eh-_Ijdo575yI96A" 
genai.configure(api_key=GEMINI_API_KEY)

async def check_vessel(name, imo):
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Check OFAC
        try:
            await page.goto("https://sanctionssearch.ofac.treas.gov/")
            await page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
            await page.fill('input#ctl00_MainContent_txtID', imo)
            await page.click('input#ctl00_MainContent_btnSearch')
            await asyncio.sleep(3)
            await page.screenshot(path="ofac_result.png")
            results['ofac'] = "ofac_result.png"
        except: results['ofac_err'] = "Lỗi kết nối OFAC"
        # Check OpenSanctions
        try:
            url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
            await page.goto(url)
            await asyncio.sleep(4)
            await page.screenshot(path="os_result.png")
            results['os'] = "os_result.png"
        except: results['os_err'] = "Lỗi kết nối OpenSanctions"
        await browser.close()
    return results

def get_ai_answer(name, imo):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Check vessel {name} (IMO: {imo}). Is it on any sanction list? Did it visit Russia in the last 12 months? Answer in 1 English sentence."
    response = model.generate_content(prompt)
    return response.text

# Giao diện Web
st.set_page_config(page_title="Vessel Checker", layout="wide")
st.title("🚢 Vessel Sanction Checker")

v_name = st.sidebar.text_input("Tên tàu (Vessel Name)")
v_imo = st.sidebar.text_input("Số IMO")

if st.sidebar.button("Bắt đầu kiểm tra"):
    if v_name and v_imo:
        with st.spinner("Đang lấy dữ liệu và hỏi AI, vui lòng chờ..."):
            screenshots = asyncio.run(check_vessel(v_name, v_imo))
            ai_conclusion = get_ai_answer(v_name, v_imo)
            
            st.subheader("🤖 Kết luận từ AI (Gemini):")
            st.info(ai_conclusion)
            
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.write("📸 Ảnh chụp từ OFAC:")
                if 'ofac' in screenshots: st.image("ofac_result.png")
                else: st.error(screenshots.get('ofac_err'))
            with col2:
                st.write("📸 Ảnh chụp từ OpenSanctions:")
                if 'os' in screenshots: st.image("os_result.png")
                else: st.error(screenshots.get('os_err'))
    else:
        st.error("Vui lòng nhập đầy đủ Tên tàu và IMO!")