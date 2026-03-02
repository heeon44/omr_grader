import cv2
import numpy as np


def enhance_marker_region(img, layout):
    marker_x = layout.get("marker_x")
    marker_y = layout.get("marker_y")
    marker_size = layout.get("marker_size", 40)

    if marker_x is None:
        return img

    img_copy = img.copy()

    roi = img_copy[
        marker_y:marker_y+marker_size,
        marker_x:marker_x+marker_size
    ]

    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    roi_eq = cv2.equalizeHist(roi_gray)
    roi_eq = cv2.cvtColor(roi_eq, cv2.COLOR_GRAY2BGR)

    img_copy[
        marker_y:marker_y+marker_size,
        marker_x:marker_x+marker_size
    ] = roi_eq

    return img_copy


def align_images_orb(template_img, student_img, layout):

    template_img = enhance_marker_region(template_img, layout)
    student_img = enhance_marker_region(student_img, layout)

    template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
    student_gray = cv2.cvtColor(student_img, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(5000)

    kp1, des1 = orb.detectAndCompute(template_gray, None)
    kp2, des2 = orb.detectAndCompute(student_gray, None)

    if des1 is None or des2 is None:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 15:
        return None

    matches = sorted(matches, key=lambda x: x.distance)

    pts_template = np.float32(
        [kp1[m.queryIdx].pt for m in matches]
    ).reshape(-1, 1, 2)

    pts_student = np.float32(
        [kp2[m.trainIdx].pt for m in matches]
    ).reshape(-1, 1, 2)

    H, _ = cv2.findHomography(
        pts_student, pts_template,
        cv2.RANSAC, 5.0
    )

    if H is None:
        return None

    aligned = cv2.warpPerspective(
        student_img,
        H,
        (template_img.shape[1], template_img.shape[0])
    )

    return aligned


def detect_answer(template_gray, aligned_gray, x_bounds, y1, y2, expected_count):

    MIN_PIXEL = 50
    MIN_GAP = 25
    MEAN_RATIO = 1.15

    bubble_scores = []
    fill_ratios = []

    for i in range(5):

        x1 = x_bounds[i]
        x2 = x_bounds[i+1]

        margin_x = int((x2 - x1) * 0.10)
        margin_y = int((y2 - y1) * 0.10)

        template_bubble = template_gray[
            y1 + margin_y : y2 - margin_y,
            x1 + margin_x : x2 - margin_x
        ]

        student_bubble = aligned_gray[
            y1 + margin_y : y2 - margin_y,
            x1 + margin_x : x2 - margin_x
        ]

        # 🔧 5번 편향 완화용 추가 경계 축소
        pad = 2
        template_bubble = template_bubble[pad:-pad, pad:-pad]
        student_bubble  = student_bubble[pad:-pad, pad:-pad]

        _, template_bin = cv2.threshold(
            template_bubble, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        _, student_bin = cv2.threshold(
            student_bubble, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # ===== 디버그용 (임시) =====
        if i == 0:
            import streamlit as st
            st.image(student_bin, caption="DEBUG student_bin", width=150)
        # ============================

        # XOR 점수 (기존 유지)
        diff = cv2.bitwise_xor(template_bin, student_bin)
        xor_score = cv2.countNonZero(diff)
        bubble_scores.append(xor_score)

        # fill_ratio 계산 (보조 판단용)
        area = student_bin.shape[0] * student_bin.shape[1]
        fill = cv2.countNonZero(student_bin) / float(area)
        fill_ratios.append(fill)
        
            # ===== 디버그 출력 =====
            if i == 4:  # 마지막 버블에서 한 번만 출력
                import streamlit as st
                st.write("XOR 점수:", bubble_scores)
                st.write("Fill 비율:", fill_ratios)
            # ======================
    

    sorted_indices = np.argsort(bubble_scores)[::-1]
    fill_sorted = np.argsort(fill_ratios)[::-1]

    selected = []
    mean_score = np.mean(bubble_scores)

    for idx in sorted_indices[:expected_count]:

        top = bubble_scores[idx]
        second = bubble_scores[sorted_indices[expected_count]] if expected_count < len(sorted_indices) else 0
        gap = top - second

        # ✅ 1차: 기존 강한 마킹 (완전 채움 보호)
        if (
            top > MIN_PIXEL and
            gap > MIN_GAP and
            top > mean_score * MEAN_RATIO
        ):
            selected.append(str(idx + 1))
            continue

        # ✅ 2차: 약한 마킹 보조 판단 (체크/동그라미용)
        weak_candidate = (
            top > MIN_PIXEL * 0.6 and
            gap > MIN_GAP * 0.4
        )

        if weak_candidate:

            f_top_i = fill_sorted[0]
            f_second_i = fill_sorted[1]

            f_top = fill_ratios[f_top_i]
            f_second = fill_ratios[f_second_i]
            f_gap = f_top - f_second

            # 🔧 fill_ratio 차이 기준 (튜닝 가능)
            if f_gap > 0.02:
                selected.append(str(f_top_i + 1))

    return selected, bubble_scores




