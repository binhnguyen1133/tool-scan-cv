import asyncio
import pandas as pd
from pdf_engine import extract_text_and_image
from ai_engine import extract_all_fields
from utils import remove_accents

# ---------------------------
# PROCESS SINGLE
# ---------------------------
async def process_single(file):
    try:
        text, image_b64 = await asyncio.to_thread(extract_text_and_image, file)

        fields = await extract_all_fields(text, image_b64)

        name = fields["name"]
        email = fields["email"]
        phone = fields["phone"]

        normalize_name = remove_accents(name, 0)
        name_format = remove_accents(name, 1)

        return {
            "File Name": file.name,
            "Name": normalize_name,
            "Name (No Accent)": name_format,
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
async def process_all(files):
    semaphore = asyncio.Semaphore(5)

    async def task(f):
        async with semaphore:
            return await process_single(f)

    tasks = [task(f) for f in files]
    results = await asyncio.gather(*tasks)

    return pd.DataFrame(results).fillna("")
