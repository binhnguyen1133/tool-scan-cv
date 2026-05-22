import asyncio
import json
from config import client
from utils import smart_fix_email, normalize_phone

EXTRACTION_PROMPT = """\
You are an expert CV parser specialized in Vietnamese CVs.
{image_note}
Extract the following fields from the CV. Return ONLY valid JSON, no explanation.

IMPORTANT: The raw CV text below may have truncated characters at the end of words (e.g.,
"Nguyê" instead of "Nguyên", "gmail.co" instead of "gmail.com", "097770907" instead of
"0977709073"). This is a known PDF encoding bug in CVs created with design tools like Figma
or Canva. Always prefer the image over the raw text when they differ.

Fields:
- name: Full name of the candidate.
  * If a first-page image is provided, READ THE NAME FROM THE IMAGE — it is always more
    complete and accurate than the raw text below.
  * Vietnamese names have 3 parts (e.g., "Nguyễn Văn An"). Look for it at the top or in a prominent position.
  * Do NOT return job titles ("Product Designer", "Developer", etc.), company names, or section headers.
  * Return null if genuinely not found.

- email: The candidate's personal email address.
  * If a first-page image is provided, READ THE EMAIL FROM THE IMAGE to get the complete address.
  * Look for a field explicitly labeled "Email:" or "E-mail:".
  * Ignore any address listed under "Telegram:", "Zalo:", "WhatsApp:", "Line:", or any other messaging app.
  * Fix OCR errors: 0→o in domain part, 1→l, gmai1→gmail.
  * Return null if not found.

- phone: Vietnamese phone number.
  * If a first-page image is provided, READ THE PHONE FROM THE IMAGE to get all digits.
  * Valid prefixes: 03x, 05x, 07x, 08x, 09x (10 digits), or +84 followed by 9 digits.
  * Return digits only, starting with 0 (convert +84xxx → 0xxx).
  * Return null if not found.

CV TEXT (may have truncated characters — use image as ground truth):
{text}

Return JSON only:
{{"name": "...", "email": "...", "phone": "..."}}"""


async def extract_all_fields(text: str, image_b64: str = None) -> dict:
    image_note = (
        "The image of the first CV page is attached — use it as the primary source for name, "
        "email, and phone, since the raw text below may have truncated characters due to PDF encoding bugs."
        if image_b64 else ""
    )
    prompt = EXTRACTION_PROMPT.format(text=text[:6000], image_note=image_note)

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
