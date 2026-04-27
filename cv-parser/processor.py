import asyncio
import pandas as pd
from pdf_engine import extract_text_from_pdf
from ai_engine import extract_best_email, extract_name_ai, extract_best_school
from utils import smart_fix_email, extract_phone, remove_accents, email_confidence

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
        education = await extract_best_school(text)

        normalize_name = remove_accents(name, 0)
        name_format = remove_accents(name, 1)

        confidence = email_confidence(email)

        return {
            "File Name": file.name,
            "Name": normalize_name,
            "Name (No Accent)": name_format,
            "Email": email,
            "Confidence (%)": confidence,
            "Phone": phone,
            "Education": education,
            "Error": ""
        }

    except Exception as e:
        return {
            "File Name": file.name,
            "Name": "ERROR",
            "Name (No Accent)": "",
            "Email": "",
            "Confidence (%)": 0,
            "Phone": "",
            "Education": "",
            "Error": str(e)
        }

# ---------------------------
# BATCH
# ---------------------------
async def process_all(files):
    semaphore = asyncio.Semaphore(5)

    async def task(f):
        async with semaphore:
            return await process_single(f)

    tasks = [task(f) for f in files]
    results = await asyncio.gather(*tasks)

    return pd.DataFrame(results).fillna("")
