import asyncio
import re
from config import client, EMAIL_REGEX
from utils import smart_fix_email

# ---------------------------
# AI EMAIL
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

async def extract_best_email(text):
    candidates = list(set(re.findall(EMAIL_REGEX, text)))

    if len(candidates) == 1:
        return smart_fix_email(candidates[0])

    ai_email = await extract_email_ai(text)
    return smart_fix_email(ai_email)

# ---------------------------
# AI NAME (CLEAN)
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
