import cv2
import pytesseract
import numpy as np
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_area(image, area):

    if not area or len(area) != 4:
        return ""

    x1, y1, x2, y2 = area
    crop = image[y1:y2, x1:x2]

    if crop.size == 0:
        return ""

    # 🔥 2배 확대 (핵심)
    crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # 대비 강화
    gray = cv2.equalizeHist(gray)

    # 노이즈 제거
    gray = cv2.GaussianBlur(gray, (3,3), 0)

    # 이진화
    _, thresh = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    custom_config = r'--oem 3 --psm 7'

    text = pytesseract.image_to_string(
        thresh,
        lang='kor+eng',
        config=custom_config
    )

    # 🔥 한글/영문/숫자만 남기기
    text = re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

    return text.strip()