import streamlit as st
import cv2
import numpy as np
import pandas as pd
import io

from core.database import load_exams
from core.omr_engine import align_images_orb, detect_answer
from core.scoring import grade_student


# ==================================================
# 📱 자동 기울기 보정
# ==================================================
def auto_deskew(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(
        edged,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return image

    largest = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

    if len(approx) != 4:
        return image

    pts = approx.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    (tl, tr, br, bl) = rect

    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))

    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))


# ==================================================
# 📱 기본 대비 강화 (이름만 변경)
# ==================================================
def enhance_basic_image(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(gray)
    blur = cv2.GaussianBlur(cl, (5, 5), 0)

    return cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)


# ==================================================
# 📱 모바일 대비 강화 (인식용)
# ==================================================
def enhance_mobile_image(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(gray)

    blur = cv2.GaussianBlur(cl, (3, 3), 0)

    return cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)


# ==================================================
# 🖼 이미지 디버그 페이지
# ==================================================
def show_image_debug_page():

    st.header("🖼 답안 채점 (이미지 디버그)")

    exams = load_exams()
    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    exam_name = st.selectbox("시험 선택", list(exams.keys()))
    exam = exams[exam_name]

    if not exam.get("layout") or not exam.get("template_path"):
        st.warning("템플릿 설정 필요")
        return

    mobile_mode = st.checkbox("📱 모바일 정렬 강화 모드", value=True)
    contrast_mode = st.checkbox("🎛 명암 대비 강화 적용", value=False)

    uploaded_imgs = st.file_uploader(
        "JPG / PNG 여러 장 업로드",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded_imgs and st.button("채점 시작"):

        stream = np.fromfile(exam["template_path"], np.uint8)
        template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

        layout = exam["layout"]
        sections = exam.get("sections", {})
        scores = exam.get("scores", {})

        all_rows = []

        for idx, uploaded_img in enumerate(uploaded_imgs):

            st.markdown("---")
            st.subheader(f"📄 이미지 {idx + 1}")

            file_bytes = uploaded_img.read()
            file_array = np.frombuffer(file_bytes, np.uint8)
            student_img = cv2.imdecode(file_array, cv2.IMREAD_COLOR)

            # 🔥 정렬 먼저
            aligned = align_images_orb(template_img, student_img, layout)

            if aligned is None:
                st.error("ORB 정렬 실패")
                continue

            # 🔥 인식용 이미지 생성
            aligned_for_detect = aligned

            if contrast_mode:
                aligned_for_detect = enhance_mobile_image(aligned_for_detect)

            # 🔥 디버그용 이미지 생성 (여기!)
            if contrast_mode:
                debug_img = aligned_for_detect.copy()
            else:
                debug_img = aligned.copy()

            # 🔥 그레이 변환
            aligned_gray = cv2.cvtColor(aligned_for_detect, cv2.COLOR_BGR2GRAY)

            total_score = 0
            section_scores = {sec_id: 0 for sec_id in sections}
            row = {"이미지 번호": idx + 1}

            for q in range(1, exam["num_questions"] + 1):

                if str(q) not in layout.get("y_ranges", {}):
                    continue

                col_index = ((q - 1) // layout["questions_per_column"]) + 1
                col_index = str(min(col_index, len(layout["columns_x"])))

                if col_index not in layout["columns_x"]:
                    continue

                x_bounds = layout["columns_x"][col_index]
                y1, y2 = layout["y_ranges"][str(q)]

                correct = exam["answers"][str(q)]["answer"]
                expected = len(correct)

                selected, _ = detect_answer(
                    template_gray,
                    aligned_gray,
                    x_bounds,
                    y1,
                    y2,
                    expected
                )

                row[f"{q}번_학생답"] = ",".join(selected)
                is_correct = set(correct) == set(selected)

                if not is_correct:
                    qx_ranges = layout.get("question_x_ranges", {})
                    qx = qx_ranges.get(col_index)
                    if qx:
                        overlay = debug_img.copy()
                        cv2.rectangle(
                            overlay,
                            (qx[0], y1),
                            (qx[1], y2),
                            (0, 0, 255),
                            -1
                        )
                        debug_img = cv2.addWeighted(
                            overlay, 0.45,
                            debug_img, 0.55, 0
                        )

                if is_correct:
                    total_score += scores.get(str(q), 1)
                    for sec_id, sec in sections.items():
                        if q in sec.get("questions", []):
                            section_scores[sec_id] += scores.get(str(q), 1)

                for i in range(5):
                    if i + 1 >= len(x_bounds):
                        continue
                    cv2.rectangle(
                        debug_img,
                        (x_bounds[i], y1),
                        (x_bounds[i + 1], y2),
                        (0, 0, 255),
                        2
                    )

                for i in range(5):
                    if i + 1 >= len(x_bounds):
                        continue
                    bubble_id = str(i + 1)
                    if bubble_id in correct:
                        overlay = debug_img.copy()
                        cv2.rectangle(
                            overlay,
                            (x_bounds[i], y1),
                            (x_bounds[i + 1], y2),
                            (255, 0, 0),
                            -1
                        )
                        debug_img = cv2.addWeighted(
                            overlay, 0.25,
                            debug_img, 0.75, 0
                        )
                        cv2.rectangle(
                            debug_img,
                            (x_bounds[i], y1),
                            (x_bounds[i + 1], y2),
                            (255, 0, 0),
                            5
                        )

                for i in range(5):
                    if i + 1 >= len(x_bounds):
                        continue
                    bubble_id = str(i + 1)
                    if bubble_id in selected:
                        overlay = debug_img.copy()
                        cv2.rectangle(
                            overlay,
                            (x_bounds[i], y1),
                            (x_bounds[i + 1], y2),
                            (0, 255, 0),
                            -1
                        )
                        debug_img = cv2.addWeighted(
                            overlay, 0.35,
                            debug_img, 0.65, 0
                        )
                        cv2.rectangle(
                            debug_img,
                            (x_bounds[i], y1),
                            (x_bounds[i + 1], y2),
                            (0, 255, 0),
                            5
                        )

                qx_ranges = layout.get("question_x_ranges", {})
                qx = qx_ranges.get(col_index)
                if qx:
                    cv2.putText(
                        debug_img,
                        f"Q{q}",
                        (qx[0], y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )

            row["총점"] = total_score
            all_rows.append(row)

            cols = st.columns(len(section_scores) + 1)
            i = 0
            for sec_id, score_val in section_scores.items():
                cols[i].markdown(
                    f"### {sections[sec_id]['name']}<br><b>{score_val}점</b>",
                    unsafe_allow_html=True
                )
                i += 1

            cols[i].markdown(
                f"### 총점<br><b style='color:#2E8B57;'>{total_score}점</b>",
                unsafe_allow_html=True
            )

            st.image(debug_img, channels="BGR")

        df = pd.DataFrame(all_rows)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)

        st.download_button(
            "📥 전체 결과 엑셀 다운로드",
            data=excel_buffer.getvalue(),
            file_name="image_debug_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )







