import re
import unicodedata
import tempfile
import pandas as pd
import zipfile
from io import BytesIO
from config import COMMON_DOMAINS

# ---------------------------
# REMOVE VIETNAMESE ACCENT
# ---------------------------
def remove_accents(text, check):
    if not text:
        return ""

    # 1. Remove accents
    if check:
        text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

    # 2. Lowercase
    text = text.lower()

    # 3. Remove special characters (giữ lại space)
    if check:
        text = re.sub(r'[^a-z0-9\s]', '', text)

    # 4. Normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # 5. Title Case (viết hoa chữ cái đầu mỗi từ)
    text = text.title()

    return text

# ---------------------------
# EMAIL FIX
# ---------------------------
def smart_fix_email(email: str):
    if not email:
        return email

    email = email.strip().rstrip('.,;:()')

    parts = email.split("@")
    if len(parts) != 2:
        return email

    local, domain = parts

    # Fix domain OCR errors
    domain = domain.lower().strip()
    domain = re.sub(r'^0+', '', domain)          # leading zeros
    domain = domain.replace("gmai1.com", "gmail.com")
    domain = domain.replace("gma1l.com", "gmail.com")
    domain = domain.replace("gmaii.com", "gmail.com")
    domain = domain.replace("yah00.com", "yahoo.com")
    domain = re.sub(r'(?<=[a-z])0(?=[a-z])', 'o', domain)  # 0→o between letters

    if domain.endswith("gmail.co"):
        domain += "m"

    # Fix local part OCR: rn→m in common patterns
    local = re.sub(r'rn(?=[a-z])', 'm', local)

    return f"{local}@{domain}"

# ---------------------------
# EMAIL CONFIDENCE
# ---------------------------
def email_confidence(email):
    if not email:
        return 0

    score = 100

    if re.search(r'[1lIqg0o]', email):
        score -= 20

    if any(d in email for d in COMMON_DOMAINS):
        score += 5

    return max(0, min(score, 100))

# ---------------------------
# PHONE
# ---------------------------
_VN_PHONE_RE = re.compile(
    r'(?<!\d)'                      # không phải digit trước
    r'(\+?84|0)'                    # prefix: +84, 84, or 0
    r'([3-9]\d{8})'                 # 9 chữ số còn lại (03x-09x)
    r'(?!\d)'                       # không phải digit sau
)

def normalize_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r'\D', '', raw)
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits[0] == "0":
        return digits
    return raw  # trả về nguyên gốc nếu không match

def extract_phone(text: str) -> str:
    for m in _VN_PHONE_RE.finditer(text):
        prefix, body = m.group(1), m.group(2)
        return "0" + body
    return ""

# ---------------------------
# EXPORT EXCEL
# ---------------------------
_ILLEGAL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def _clean_cell(val):
    if isinstance(val, str):
        return _ILLEGAL_CHARS.sub('', val)
    return val

def to_excel(df):
    clean_df = df.map(_clean_cell)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        clean_df.to_excel(writer, index=False)
    return output.getvalue()

# ---------------------------
# BUILD ZIP (USE name_format)
# ---------------------------
def build_zip(files, df, start_number, prefix_text, postfix=""):
    """Build the renamed ZIP on disk (one PDF at a time) to avoid holding a full
    second copy of every PDF in RAM. Returns the temp file path; the caller is
    responsible for reading/streaming it to the download widget."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, file in enumerate(files):
            try:
                # Lấy tên và sanitize
                name = df.iloc[i].get("Name (No Accent)", "") or "Unknown"
                name = re.sub(r'[\\/*?:"<>|]', "", name)

                # Tăng số và format thành 3 chữ số (005, 048, 448...)
                number = f"{start_number + i:03}"

                # Build filename
                new_filename = f"{number} {prefix_text} {name} {postfix}".strip()
                new_filename = re.sub(r'\s+', ' ', new_filename)

                # Thêm đuôi .pdf
                new_filename += ".pdf"

                # Ghi vào zip
                zf.writestr(new_filename, file.getvalue())

            except Exception as e:
                print("ZIP error:", e)

    return tmp.name
