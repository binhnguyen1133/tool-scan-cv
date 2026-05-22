import json
from config import client
from utils import smart_fix_email, normalize_phone

NAME_ONLY_PROMPT = """\
Extract the full name of the CV candidate.
{image_note}
- Vietnamese names have 2-4 parts (e.g., "Nguyễn Văn An")
- If image provided, prefer the image — name is often rendered as large styled text
- Do NOT return job titles ("Designer", "Developer", etc.), companies, or section headers
- Return null if genuinely not found

CV TEXT:
{text}

Return JSON only: {{"name": "..."}}"""

EXTRACTION_PROMPT = """\
You are an expert CV parser specialized in Vietnamese CVs.
{image_note}
Extract the following fields from the CV. Return ONLY valid JSON, no explanation.

IMPORTANT: The raw CV text may have truncated characters (e.g., "Nguyê" instead of "Nguyên",
"gmail.co" instead of "gmail.com"). This is a PDF encoding bug from Figma/Canva.
Always prefer the image over the raw text when they differ.

Fields:
- name: Full name of the candidate.
  * READ FROM IMAGE if provided — more complete than raw text.
  * Vietnamese names have 2-4 parts. Look at the top of the CV.
  * Do NOT return job titles, company names, or section headers.
  * Return null if not found.

- email: The candidate's personal email address.
  * READ FROM IMAGE if provided.
  * Ignore Telegram/Zalo/WhatsApp/Line addresses.
  * Fix OCR errors: 0→o in domain, 1→l, gmai1→gmail.
  * Return null if not found.

- phone: Vietnamese phone number.
  * READ FROM IMAGE if provided.
  * Valid: 03x/05x/07x/08x/09x (10 digits) or +84 followed by 9 digits.
  * Return digits only, starting with 0.
  * Return null if not found.

CV TEXT (may have truncated characters — use image as ground truth):
{text}

Return JSON only: {{"name": "...", "email": "...", "phone": "..."}}"""


def extract_name_ai(text: str, image_b64: str = None) -> str:
    image_note = (
        "The image of the first CV page is attached — use it as the primary source for the name."
        if image_b64 else ""
    )
    prompt = NAME_ONLY_PROMPT.format(text=text[:2000], image_note=image_note)

    content = []
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}
        })
    content.append({"type": "text", "text": prompt})

    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": content}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        return (data.get("name") or "").strip()
    except Exception as e:
        print("AI name error:", e)
        return ""


def extract_all_ai(text: str, image_b64: str = None) -> dict:
    image_note = (
        "The image of the first CV page is attached — use it as the primary source for name, "
        "email, and phone. The raw text may have truncated characters due to PDF encoding bugs."
        if image_b64 else ""
    )
    prompt = EXTRACTION_PROMPT.format(text=text[:6000], image_note=image_note)

    content = []
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}
        })
    content.append({"type": "text", "text": prompt})

    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": content}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        return {
            "name":  (data.get("name")  or "").strip(),
            "email": smart_fix_email((data.get("email") or "").strip()),
            "phone": normalize_phone((data.get("phone") or "").strip()),
        }
    except Exception as e:
        print("AI extract error:", e)
        return {"name": "", "email": "", "phone": ""}
