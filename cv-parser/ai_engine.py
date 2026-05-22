import asyncio
import json
from config import client
from utils import smart_fix_email, normalize_phone

EXTRACTION_PROMPT = """\
You are an expert CV parser specialized in Vietnamese CVs.
{image_note}
Extract the following fields from the CV. Return ONLY valid JSON, no explanation.

Fields:
- name: Full name of the candidate.
  * If a first-page image is provided, check the image first — the name is often rendered as large styled text that does NOT appear in the raw text below.
  * Vietnamese names have 3 parts (e.g., "Nguyễn Văn An"). Look for it at the top or in a prominent position.
  * Do NOT return job titles ("Product Designer", "Developer", etc.), company names, or section headers.
  * Return null if genuinely not found.

- email: The candidate's personal email address.
  * Look for a field explicitly labeled "Email:" or "E-mail:".
  * Ignore any address listed under "Telegram:", "Zalo:", "WhatsApp:", "Line:", or any other messaging app.
  * Fix OCR errors: 0→o in domain part, 1→l, gmai1→gmail.
  * Return null if not found.

- phone: Vietnamese phone number.
  * Valid prefixes: 03x, 05x, 07x, 08x, 09x (10 digits), or +84 followed by 9 digits.
  * Return digits only, starting with 0 (convert +84xxx → 0xxx).
  * Return null if not found.

CV TEXT (may be incomplete for design-heavy image-based CVs):
{text}

Return JSON only:
{{"name": "...", "email": "...", "phone": "..."}}"""


async def extract_all_fields(text: str, image_b64: str = None) -> dict:
    image_note = (
        "The image of the first CV page is attached — use it to find the candidate's "
        "name if it is rendered as styled/graphic text not present in the raw text."
        if image_b64 else ""
    )
    prompt = EXTRACTION_PROMPT.format(text=text[:4000], image_note=image_note)

    content = []
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_b64}",
                "detail": "high"
            }
        })
    content.append({"type": "text", "text": prompt})

    try:
        res = await asyncio.to_thread(
            client.chat.completions.create,
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
