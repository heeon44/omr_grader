import streamlit as st
import cv2
import numpy as np
import pandas as pd
import io
import fitz  # PyMuPDF
from openpyxl import Workbook
from openpyxl.styles import PatternFill

from core.database import load_exams
from core.omr_engine import align_images_orb, detect_answer
from core.scoring import grade_student


# ==================================================
# 📱 자동 외곽선 기반 기울기 보정
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
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    return warped


# ==================================================
# 📱 모바일 대비 강화
# ==================================================
def enhance_mobile_image(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(gray)

    blur = cv2.GaussianBlur(cl, (5, 5), 0)

    enhanced = cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)

    return enhanced


# ==================================================
# 📝 채점 페이지
# ==================================================
def show_grading_page():

    st.header("📝 답안 채점")

    exams = load_exams()

    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    exam_name = st.selectbox("시험 선택", list(exams.keys()))
    exam = exams[exam_name]

    if not exam.get("layout") or not exam.get("template_path"):
        st.warning("템플릿 설정 필요")
        return

    tab_pdf, tab_img = st.tabs(["📄 PDF 채점", "🖼 JPG/PNG 채점"])

    # ==================================================
    # 📄 PDF 채점
    # ==================================================
    with tab_pdf:

        uploaded_pdf = st.file_uploader(
            "PDF 업로드",
            type=["pdf"],
            key="pdf_uploader"
        )

        if uploaded_pdf and st.button("채점 시작 (PDF)", key="pdf_btn"):

            with st.spinner("📄 채점 진행 중..."):

                pdf_bytes = uploaded_pdf.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                pages = []

                for page_index in range(len(doc)):
                    page = doc[page_index]
                    pix = page.get_pixmap(dpi=200)

                    img = np.frombuffer(pix.samples, dtype=np.uint8)
                    img = img.reshape(pix.height, pix.width, pix.n)

                    if pix.n == 4:
                        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

                    pages.append(img)

                stream = np.fromfile(exam["template_path"], np.uint8)
                template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
                template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

                layout = exam["layout"]
                results = []
                progress_bar = st.progress(0)

                for idx, page_img in enumerate(pages):

                    student_img = cv2.cvtColor(page_img, cv2.COLOR_RGB2BGR)

                    aligned = align_images_orb(template_img, student_img, layout)

                    if aligned is None:
                        st.error("ORB 정렬 실패")
                        return

                    aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)

                    row = {"페이지 번호": idx + 1}

                    for q in range(1, exam["num_questions"] + 1):

                        q_data = exam["answers"].get(str(q), {})
                        if q_data.get("type") != "mcq":
                            continue

                        if str(q) not in layout.get("y_ranges", {}):
                            continue

                        col_index = ((q - 1) // layout.get("questions_per_column", 1)) + 1
                        col_index = str(min(col_index, len(layout["columns_x"])))

                        x_bounds = layout["columns_x"][col_index]
                        y1, y2 = layout["y_ranges"][str(q)]

                        correct_answers = q_data.get("answer", [])
                        expected_count = len(correct_answers)

                        selected, _ = detect_answer(
                            template_gray,
                            aligned_gray,
                            x_bounds,
                            y1,
                            y2,
                            expected_count
                        )

                        row[f"{q}번_학생답"] = ",".join(selected)

                    row = grade_student(row, exam)
                    results.append(row)

                    progress_bar.progress((idx + 1) / len(pages))

            df = pd.DataFrame(results)

            st.success("PDF 채점 완료 ✅")
            st.dataframe(df, use_container_width=True)

    # ==================================================
    # 🖼 이미지 채점
    # ==================================================
    with tab_img:

        uploaded_img = st.file_uploader(
            "JPG / PNG 이미지 업로드",
            type=["jpg", "jpeg", "png"],
            key="img_uploader"
        )

        if uploaded_img and st.button("채점 시작 (이미지)", key="img_btn"):

            file_bytes = uploaded_img.read()
            file_array = np.frombuffer(file_bytes, np.uint8)
            student_img = cv2.imdecode(file_array, cv2.IMREAD_COLOR)

            # 1️⃣ 자동 기울기 보정
            student_img = auto_deskew(student_img)

            # 2️⃣ 대비 강화
            student_img = enhance_mobile_image(student_img)

            stream = np.fromfile(exam["template_path"], np.uint8)
            template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
            template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

            layout = exam["layout"]

            aligned = align_images_orb(template_img, student_img, layout)

            if aligned is None:
                st.error("ORB 정렬 실패")
                return

            aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)

            row = {"페이지 번호": 1}

            for q in range(1, exam["num_questions"] + 1):

                q_data = exam["answers"].get(str(q), {})
                if q_data.get("type") != "mcq":
                    continue

                if str(q) not in layout.get("y_ranges", {}):
                    continue

                col_index = ((q - 1) // layout.get("questions_per_column", 1)) + 1
                col_index = str(min(col_index, len(layout["columns_x"])))

                x_bounds = layout["columns_x"][col_index]
                y1, y2 = layout["y_ranges"][str(q)]

                correct_answers = q_data.get("answer", [])
                expected_count = len(correct_answers)

                selected, _ = detect_answer(
                    template_gray,
                    aligned_gray,
                    x_bounds,
                    y1,
                    y2,
                    expected_count
                )

                row[f"{q}번_학생답"] = ",".join(selected)

            row = grade_student(row, exam)

            df = pd.DataFrame([row])

            st.success("이미지 채점 완료 ✅")
            st.dataframe(df, use_container_width=True)
