import os
import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import asyncio
import re
import requests
import logging
from openai import OpenAI

# ---------------------------
# CONFIG
# ---------------------------
logging.getLogger("pdfminer").setLevel(logging.ERROR)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ocr_key = os.getenv("OCR_API_KEY")

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

COMMON_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com"]

# ---------------------------
# OCR API
# ---------------------------
def ocr_space_image(image_bytes):
    url = "https://api.ocr.space/parse/image"

    payload = {
        'apikey': ocr_key,
        'language': 'eng',
        'scale': True,
        'OCREngine': 2
    }

    files = {'file': ('image.png', image_bytes)}

    try:
        res = requests.post(url, files=files, data=payload).json()
        if res.get("ParsedResults"):
            return res["ParsedResults"][0]["ParsedText"]
    except Exception as e:
        print("OCR API error:", e)

    return ""

# ---------------------------
# PDF TEXT EXTRACT
# ---------------------------
def extract_text_from_pdf(file):
    text = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                try:
                    t = page.extract_text()

                    if t and len(t.strip()) > 30:
                        text += t + "\n"
                        continue

                except Exception as e:
                    print("Text layer error:", e)

                # OCR fallback (high resolution)
                try:
                    img = page.to_image(resolution=450).original
                    buf = BytesIO()
                    img.save(buf, format="PNG")

                    ocr_text = ocr_space_image(buf.getvalue())
                    text += ocr_text + "\n"

                except Exception as e:
                    print("OCR fail:", e)

    except Exception as e:
        print("PDF open fail:", e)

    return text

# ---------------------------
# SMART EMAIL FIX (OCR SAFE)
# ---------------------------
def smart_fix_email(email: str):
    if not email:
        return email

    parts = email.split("@")
    if len(parts) != 2:
        return email

    local, domain = parts

    domain = domain.lower()

    # fix OCR domain mistakes
    domain = domain.replace("0", "o")
    domain = domain.replace("gmai1.com", "gmail.com")
    domain = domain.replace("gmai.com", "gmail.com")
    domain = domain.replace("gmali.com", "gmail.com")
    domain = domain.replace("gma1l.com", "gmail.com")

    # fix missing m
    if domain.endswith("gmail.co"):
        domain += "m"

    return f"{local}@{domain}"

# ---------------------------
# AI EMAIL EXTRACT
# ---------------------------
async def extract_email_ai(text):
    prompt = f"""
Extract the correct email from this CV.

Fix OCR mistakes:
- 1 ↔ l
- q ↔ g
- 0 ↔ o

Return ONLY 1 email.

{text[:2000]}
"""

    try:
        res = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        return res.choices[0].message.content.strip()

    except:
        return ""

# ---------------------------
# EMAIL ENGINE
# ---------------------------
async def extract_best_email(text):
    raw_candidates = list(set(re.findall(EMAIL_REGEX, text)))
    candidates = [smart_fix_email(e) for e in raw_candidates]

    if len(candidates) == 1:
        return candidates[0]

    ai_email = await extract_email_ai(text)

    if ai_email:
        return smart_fix_email(ai_email)

    return candidates[0] if candidates else ""

# ---------------------------
# EMAIL CONFIDENCE
# ---------------------------
def email_confidence(email):
    if not email:
        return 0

    score = 100

    if re.search(r'[1lIqg0o]', email):
        score -= 20

    if any(d in email for d in COMMON_DOMAINS):
        score += 5

    if not re.match(EMAIL_REGEX, email):
        score -= 40

    return max(0, min(score, 100))

# ---------------------------
# PHONE
# ---------------------------
def extract_phone(text):
    matches = re.findall(r'(\+?\d[\d\s\-\.\(\)]{8,})', text)

    for m in matches:
        digits = re.sub(r'\D', '', m)

        if digits.startswith("84"):
            digits = "0" + digits[2:]

        if 9 <= len(digits) <= 11:
            return digits

    return ""

# ---------------------------
# AI NAME
# ---------------------------
async def extract_name_ai(text):
    prompt = f"Extract full name only:\n{text[:2000]}"

    try:
        res = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        return res.choices[0].message.content.strip()

    except:
        return ""

# ---------------------------
# PROCESS SINGLE
# ---------------------------
async def process_single(file):
    try:
        text = await asyncio.to_thread(extract_text_from_pdf, file)

        email = await extract_best_email(text)
        email = smart_fix_email(email)  # extra safety

        phone = extract_phone(text)
        name = await extract_name_ai(text)

        confidence = email_confidence(email)

        return {
            "File Name": file.name,
            "Name": name,
            "Email": email,
            "Confidence (%)": confidence,
            "Phone": phone,
            "Error": ""
        }

    except Exception as e:
        return {
            "File Name": file.name,
            "Name": "ERROR",
            "Email": "",
            "Confidence (%)": 0,
            "Phone": "",
            "Error": str(e)
        }

# ---------------------------
# BATCH PROCESS
# ---------------------------
async def process_all(files):
    semaphore = asyncio.Semaphore(5)

    async def task(f):
        async with semaphore:
            return await process_single(f)

    tasks = [task(f) for f in files]

    results = await asyncio.gather(*tasks)

    df = pd.DataFrame(results)
    return df.fillna("")

# ---------------------------
# EXPORT EXCEL
# ---------------------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="CV Parser ATS", layout="wide")

st.title("🚀 CV Parser – ATS Smart Version")

files = st.file_uploader(
    "Upload CVs (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if "df" not in st.session_state:
    st.session_state.df = None

if files:
    st.info(f"{len(files)} files uploaded")

    if st.button("🚀 Process CVs"):
        with st.spinner("Processing..."):
            df = asyncio.run(process_all(files))

        st.session_state.df = df
        st.success("Done!")

# ---------------------------
# RESULTS + EDIT
# ---------------------------
if st.session_state.df is not None:
    df = st.session_state.df

    st.subheader("📊 Results (Editable)")

    edited_df = st.data_editor(
        df,
        width='stretch',
        height=500,          # 👈 show nhiều rows hơn (~10)
        num_rows="fixed"     # 👈 disable add row
    )

    # highlight nghi ngờ
    def highlight_row(row):
        if row["Confidence (%)"] < 80:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        edited_df.style.apply(highlight_row, axis=1),
        width='stretch',
        height=500
    )

    st.session_state.df = edited_df

    st.download_button(
        "📥 Download Excel",
        data=to_excel(edited_df),
        file_name="cv_results.xlsx"
    )