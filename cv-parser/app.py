import os
import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import cv2
import numpy as np
from openai import OpenAI
import asyncio
import re

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

COMMON_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com"
]

# ---------------------------
# IMAGE PREPROCESS
# ---------------------------
def preprocess_image(pil_image):
    img = np.array(pil_image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, thresh = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return thresh


# ---------------------------
# EXTRACT TEXT
# ---------------------------
def extract_text_from_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text


# ---------------------------
# EMAIL CANDIDATES
# ---------------------------
def extract_email_candidates(text):
    return list(set(re.findall(EMAIL_REGEX, text)))


# ---------------------------
# GENERATE VARIANTS (OCR FIX)
# ---------------------------
def generate_email_variants(email):
    variants = set([email])

    replacements = [
        ("g", "q"), ("q", "g"),
        ("1", "l"), ("l", "1"),
        ("0", "o"), ("o", "0"),
        ("i", "l"), ("l", "i")
    ]

    for a, b in replacements:
        if a in email:
            variants.add(email.replace(a, b))

    return list(variants)


# ---------------------------
# SCORE EMAIL
# ---------------------------
def score_email(email):
    score = 0

    # domain chuẩn
    if any(domain in email for domain in COMMON_DOMAINS):
        score += 5

    # length hợp lý
    if 10 <= len(email) <= 30:
        score += 2

    # ít ký tự lạ
    if re.match(r'^[a-zA-Z0-9._@+-]+$', email):
        score += 2

    # có số (thường user VN)
    if re.search(r'\d', email):
        score += 1

    return score


# ---------------------------
# SELECT BEST EMAIL
# ---------------------------
def extract_best_email(text):
    candidates = extract_email_candidates(text)

    all_variants = []

    for email in candidates:
        variants = generate_email_variants(email)
        all_variants.extend(variants)

    if not all_variants:
        return ""

    scored = [(email, score_email(email)) for email in all_variants]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[0][0]


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
    prompt = f"""
Extract ONLY full name from CV.
Return only name.
CV:
{text}
"""

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except:
        return ""


# ---------------------------
# PROCESS SINGLE
# ---------------------------
async def process_single(file):
    try:
        text = await asyncio.to_thread(extract_text_from_pdf, file)

        email = extract_best_email(text)
        phone = extract_phone(text)
        name = await extract_name_ai(text)

        return {
            "File Name": file.name,
            "Name": name,
            "Email": email,
            "Phone": phone,
            "Error": ""
        }

    except Exception as e:
        return {
            "File Name": file.name,
            "Name": "ERROR",
            "Email": "",
            "Phone": "",
            "Error": str(e)
        }


# ---------------------------
# BATCH
# ---------------------------
async def process_all(files):
    tasks = [process_single(f) for f in files]
    results = await asyncio.gather(*tasks)

    df = pd.DataFrame(results)
    df = df.fillna("").astype(str)
    return df


# ---------------------------
# EXPORT
# ---------------------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# ---------------------------
# UI
# ---------------------------
st.title("🚀 CV Parser – Smart Email Fix")

files = st.file_uploader("Upload CVs", type=["pdf"], accept_multiple_files=True)

if files:
    if st.button("Process"):
        df = asyncio.run(process_all(files))

        st.dataframe(df, width='stretch')

        st.download_button(
            "Download Excel",
            data=to_excel(df),
            file_name="cv.xlsx"
        )