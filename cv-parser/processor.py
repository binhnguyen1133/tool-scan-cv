import re
import gc
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from pdf_engine import extract_text_only, render_first_page
from ai_engine import extract_name_ai, extract_all_ai
from utils import remove_accents, smart_fix_email, email_confidence, extract_phone
from config import EMAIL_REGEX, CONCURRENCY


def process_single(file):
    try:
        file.seek(0)
        pdf_bytes = file.read()

        # Step 1: Fast text extraction — pdfplumber, first 2 pages, no image
        text, pages_need_ocr = extract_text_only(pdf_bytes)

        # Step 2: Regex fast path for email + phone
        candidates = [smart_fix_email(e) for e in re.findall(EMAIL_REGEX, text)]
        regex_email = next((e for e in candidates if email_confidence(e) >= 60), None)
        regex_phone = extract_phone(text)

        if regex_email and regex_phone:
            # Fast path: text-based PDF — AI for name only, no image needed
            name = extract_name_ai(text)
            email, phone = regex_email, regex_phone
        else:
            # Slow path: truncated/image PDF — render image then full AI
            image_b64, ocr_text = render_first_page(pdf_bytes, pages_need_ocr)
            full_text = (text + "\n" + ocr_text).strip() if ocr_text else text
            fields = extract_all_ai(full_text, image_b64)
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


def process_all(files, on_progress=None):
    """Process files with bounded concurrency, reporting progress per completed file.

    Runs inline in the caller's thread (Streamlit script thread) so that
    `on_progress(done, total)` can safely update `st.progress`. Concurrency is
    capped (CONCURRENCY) to bound peak memory from simultaneous PDF renders.
    """
    results = []
    total = len(files)
    done = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(process_single, f): f for f in files}
        for future in as_completed(futures):
            results.append(future.result())
            done += 1
            if on_progress:
                on_progress(done, total)
            if done % 25 == 0:  # release pdfplumber/pixmap garbage between batches
                gc.collect()

    gc.collect()

    # Restore original upload order
    order = {f.name: i for i, f in enumerate(files)}
    results.sort(key=lambda r: order.get(r["File Name"], 0))
    return pd.DataFrame(results).fillna("")
