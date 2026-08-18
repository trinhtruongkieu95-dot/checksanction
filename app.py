import streamlit as st
import asyncio
import os
import subprocess
import google.generativeai as genai
from playwright.async_api import async_playwright

# --- 1. CẤU HÌNH AI (Thay mã API của bạn vào đây) ---
GEMINI_API_KEY = "DÁN_MÃ_API_CỦA_BẠN_VÀO_ĐÂY" 
genai.configure(api_key=GEMINI_API_KEY)

# --- 2. TỰ ĐỘNG CÀI TRÌNH DUYỆT KHI MỞ APP ---
@st.cache_resource
def install_playwright():
    subprocess.run(["python", "-m", "playwright", "install", "chromium"])

install_playwright()

# --- 3. HÀM LẤY ẢNH VÀ KẾT LUẬN ---
async def run_check(name, imo):
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = await context.new_page()

        # Check OFAC
        try:
            await page.goto("https://sanctionssearch.ofac.treas.gov/", timeout=60000)
            await page.select_option('select#ctl00_MainContent_ddlType', value='Vessel')
            await page.fill('input#ctl00_MainContent_txtID', imo)
            await page.click('input#ctl00_MainContent_btnSearch')
            await asyncio.sleep(6)
            await page.screenshot(path="ofac.png", full_page=True)
            results['ofac'] = "ofac.png"
        except: results['ofac_err'] = "OFAC không phản hồi"

        # Check OpenSanctions
        try:
            url = f"https://www.opensanctions.org/advancedsearch/?caption={name}&schema=Vessel&properties.imoNumber={imo}"
            await page.goto(url, timeout=60000)
            await asyncio.sleep(6)
            await page.screenshot(path="os.png", full_page=True)
            results['os'] = "os.png"
        except: results['os_err'] = "OpenSanctions không phản hồi"

        await browser.close()
    return results

def ask_gemini(name, imo):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Research vessel {name} IMO {imo}. Is it sanctioned? Visited Russia in last 12 months? Answer 1 English sentence."
        return model.generate_content(prompt).text
    except: return "AI Error: Could not connect to Gemini."

# --- 4. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Vessel Checker", layout="wide")
st.title("🚢 Vessel Sanction Checker")

v_name = st.sidebar.text_input("Vessel Name")
v_imo = st.sidebar.text_input("IMO Number")

if st.sidebar.button("Check Now"):
    if v_name and v_imo:
        with st.spinner("Processing... Please wait about 30 seconds."):
            # Chạy AI trước
            conclusion = ask_gemini(v_name, v_imo)
            st.subheader("📝 Gemini Conclusion:")
            st.info(conclusion)
            
            st.divider()
            
            # Chụp ảnh sau
            data = asyncio.run(run_check(v_name, v_imo))
            col1, col2 = st.columns(2)
            with col1:
                st.write("🌐 OFAC:")
                if 'ofac' in data: st.image("ofac.png")
                else: st.error(data.get('ofac_err'))
            with col2:
                st.write("🌐 OpenSanctions:")
                if 'os' in data: st.image("os.png")
                else: st.error(data.get('os_err'))
    else:
        st.sidebar.warning("Please enter Name and IMO.")
