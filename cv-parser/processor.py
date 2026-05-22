import re
import asyncio
import pandas as pd
from pdf_engine import extract_text_only, render_first_page
from ai_engine import extract_name_ai, extract_all_ai
from utils import remove_accents, smart_fix_email, email_confidence, extract_phone
from config import EMAIL_REGEX


# ---------------------------
# PROCESS SINGLE
# ---------------------------
async def process_single(file):
    try:
        # Step 1: Fast text extraction — pdfplumber only, no image
        text, pages_need_ocr = await asyncio.to_thread(extract_text_only, file)

        # Step 2: Regex fast path for email + phone
        candidates = [smart_fix_email(e) for e in re.findall(EMAIL_REGEX, text)]
        regex_email = next((e for e in candidates if email_confidence(e) >= 60), None)
        regex_phone = extract_phone(text)

        if regex_email and regex_phone:
            # Fast path: text-based PDF — AI for name only, no image needed
            name = await extract_name_ai(text)
            email, phone = regex_email, regex_phone
        else:
            # Slow path: truncated/image PDF — render image then full AI
            image_b64, ocr_text = await asyncio.to_thread(render_first_page, file, pages_need_ocr)
            full_text = (text + "\n" + ocr_text).strip() if ocr_text else text
            fields = await extract_all_ai(full_text, image_b64)
            name, email, phone = fields["name"], fields["email"], fields["phone"]

        return {
            "File Name": file.name,
            "Name": remove_accents(name, 0),
            "Name (No Accent)": remove_accents(name, 1),
            "Email": email,
            "Phone": phone,
            "Error": ""
        }

    except Exception as e:
        return {
            "File Name": file.name,
            "Name": "ERROR",
            "Name (No Accent)": "",
            "Email": "",
            "Phone": "",
            "Error": str(e)
        }


# ---------------------------
# BATCH
# ---------------------------
async def process_all(files, on_done=None):
    semaphore = asyncio.Semaphore(5)

    async def task(f):
        async with semaphore:
            result = await process_single(f)
            if on_done:
                on_done()
            return result

    tasks = [task(f) for f in files]
    results = await asyncio.gather(*tasks)
    return pd.DataFrame(results).fillna("")
