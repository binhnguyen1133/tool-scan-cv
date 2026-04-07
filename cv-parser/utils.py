import re
import unicodedata
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

    parts = email.split("@")
    if len(parts) != 2:
        return email

    local, domain = parts

    domain = domain.lower()
    domain = domain.replace("0", "o")
    domain = domain.replace("gmai1.com", "gmail.com")
    domain = domain.replace("gma1l.com", "gmail.com")

    if domain.endswith("gmail.co"):
        domain += "m"

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
def extract_phone(text):
    matches = re.findall(r'(\+?\d[\d\s\-\.\(\)]{8,})', text)

    for m in matches:
        digits = re.sub(r'\D', '', m)

        if digits.startswith("84"):
            digits = "0" + digits[2:]

        if 9 <= len(digits) <= 11:
            return digits

    return ""

# ---------------------------
# EXPORT EXCEL
# ---------------------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ---------------------------
# BUILD ZIP (USE name_format)
# ---------------------------
def build_zip(files, df, start_number, prefix_text, postfix=""):
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:
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

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
