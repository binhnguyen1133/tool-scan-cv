import asyncio
import re
from config import client, EMAIL_REGEX
from utils import smart_fix_email

# ---------------------------
# AI EMAIL
# ---------------------------
async def extract_email_ai(text):
    prompt = f"""Extract the candidate's personal contact email from this CV.

Rules:
- Return ONLY the email address, nothing else
- Fix common OCR mistakes: 1↔l, 0↔o, q↔g, rn↔m
- Prefer personal emails (gmail, yahoo, outlook) over company/university emails
- If no email found, return empty string

CV:
{text[:3000]}"""

    try:
        res = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        raw = res.choices[0].message.content.strip().rstrip('.,;:')
        return raw if '@' in raw else ""
    except:
        return ""

def _preprocess_text_for_email(text):
    # Join lines that split an email across two lines (e.g. "user\n@gmail.com")
    text = re.sub(r'(\S+)\s*\n\s*(@\S+)', r'\1\2', text)
    text = re.sub(r'(@\S+)\s*\n\s*(\S+)', r'\1\2', text)
    return text

async def extract_best_email(text):
    text = _preprocess_text_for_email(text)
    candidates = list(set(re.findall(EMAIL_REGEX, text)))
    # Filter out obviously invalid candidates (too short, no dot in domain)
    candidates = [e for e in candidates if '.' in e.split('@')[-1] and len(e) > 6]

    if len(candidates) == 1:
        # Still run through AI if it looks suspicious (OCR artifacts)
        if re.search(r'[1I0]', candidates[0]):
            ai_email = await extract_email_ai(text)
            if ai_email:
                return smart_fix_email(ai_email)
        return smart_fix_email(candidates[0])

    ai_email = await extract_email_ai(text)
    return smart_fix_email(ai_email)

# ---------------------------
# AI NAME (CLEAN)
# ---------------------------
async def extract_name_ai(text):
    prompt = f"""Extract the candidate's full name from this CV.

Rules:
- Return ONLY the full name, nothing else — no labels, no quotes
- Keep Vietnamese diacritics (e.g. Nguyễn Văn An, Trần Thị Bích)
- Do NOT include job titles, positions, or company names
- Do NOT include "Name:", "Full name:", "Họ tên:" prefixes
- The name is usually on the first 1-2 lines or near "Họ tên" / "Name" label
- If unclear, pick the most person-like name (2-4 words)

CV:
{text[:3000]}"""

    try:
        res = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        name = res.choices[0].message.content.strip()
        # Strip common prefixes AI sometimes includes
        name = re.sub(r'^(name|full name|họ tên|họ và tên)\s*[:\-]\s*', '', name, flags=re.IGNORECASE)
        return name.strip()

    except:
        return ""

# ---------------------------
# AI SCHOOL (UNIVERSITY)
# ---------------------------
async def extract_school_ai(text):
    prompt = f"""Extract the university/college name from this CV.

Rules:
- Return ONLY 1 school name, nothing else
- Include both Vietnamese and English university names
- Ignore: high school (THPT), certifications, short courses, training centers
- Prefer highest degree (Master/Bachelor over Associate)
- Fix OCR mistakes if needed
- If no university found, return empty string

CV:
{text[:3000]}"""

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

UNIVERSITY_KEYWORDS = [
    # English
    "university", "college", "institute", "academy",
    # Vietnamese
    "đại học", "học viện", "cao đẳng", "trường đh", "trường đại"
]

def extract_school_candidates(text):
    lines = text.split("\n")
    candidates = []

    for line in lines:
        lower = line.lower()
        if any(k in lower for k in UNIVERSITY_KEYWORDS):
            cleaned = line.strip()
            if cleaned:
                candidates.append(cleaned)

    return list(set(candidates))


async def extract_best_school(text):
    candidates = extract_school_candidates(text)

    # Nếu chỉ có 1 candidate → dùng luôn
    if len(candidates) == 1:
        return candidates[0]

    # Nếu nhiều hoặc không có → dùng AI
    ai_school = await extract_school_ai(text)
    return ai_school