import re
from datetime import datetime

import os

try:
    import pytesseract
    from PIL import Image
    # Auto-detect Tesseract on Windows if not in PATH
    if os.name == "nt":
        default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_path):
            pytesseract.pytesseract.tesseract_cmd = default_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


DATE_PATTERNS = [
    r'\d{2}[/\-\.]\d{2}[/\-\.]\d{4}',  # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    r'\d{4}[/\-\.]\d{2}[/\-\.]\d{2}',  # YYYY/MM/DD, YYYY-MM-DD
]

EXPIRY_KEYWORDS = [
    "valid", "expiry", "upto", "up to", "till", "valid till",
    "valid upto", "valid up to", "expiry date", "date of expiry",
    "expires on", "valid until", "validity",
]


def extract_dates_from_text(text):
    """Extract all date strings from OCR text."""
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    return dates


def parse_date(date_str):
    """Try to parse a date string into a date object."""
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y/%m/%d", "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def find_expiry_date_from_text(text):
    """Find the most likely expiry date from OCR text by looking near expiry keywords."""
    text_lower = text.lower()
    lines = text.split("\n")

    # First pass: look for dates on lines containing expiry keywords
    best_date = None
    for line in lines:
        line_lower = line.lower()
        has_keyword = any(kw in line_lower for kw in EXPIRY_KEYWORDS)
        if has_keyword:
            dates = extract_dates_from_text(line)
            for d in dates:
                parsed = parse_date(d)
                if parsed:
                    if best_date is None or parsed > best_date:
                        best_date = parsed

    # If found near keywords, return it
    if best_date:
        return best_date

    # Second pass: return the latest date found (likely the expiry)
    all_dates = extract_dates_from_text(text)
    parsed_dates = [parse_date(d) for d in all_dates]
    valid_dates = [d for d in parsed_dates if d is not None]

    if valid_dates:
        return max(valid_dates)

    return None


def extract_expiry_from_image(file_path):
    """Run OCR on an image and try to extract the expiry date."""
    if not OCR_AVAILABLE:
        return None, "OCR libraries not available"

    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        expiry = find_expiry_date_from_text(text)
        return expiry, text
    except Exception as e:
        return None, str(e)
