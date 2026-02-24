import cv2
import numpy as np

def imread_unicode(path):
    stream = np.fromfile(path, np.uint8)
    img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
    return img


def detect_bubbles(template_path, debug=False):

    image = imread_unicode(template_path)

    if image is None:
        raise ValueError(f"이미지 로드 실패: {template_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5,5), 0)

    thresh = cv2.adaptiveThreshold(
        blur,255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15,3
    )

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE
    )

    bubbles = []

    for cnt in contours:

        area = cv2.contourArea(cnt)

        if area < 150:   # 🔥 낮춤
            continue

        (x,y,w,h) = cv2.boundingRect(cnt)

        ratio = w / float(h)

        # 🔥 조건 완화
        if 0.6 < ratio < 1.4 and 10 < w < 80:
            bubbles.append((int(x), int(y), int(w), int(h)))

    # 위에서 아래, 왼쪽 정렬
    bubbles = sorted(bubbles, key=lambda b: (b[1], b[0]))

    return bubbles