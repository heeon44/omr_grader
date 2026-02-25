import streamlit as st
import cv2
import numpy as np
import fitz  # 🔥 PyMuPDF
from core.database import load_exams
from core.omr_engine import align_images_orb, detect_answer

# ===============================
# 자동 기울기 보정
# ===============================
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


# ===============================
# 모바일 대비 강화
# ===============================
def enhance_mobile_image(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(gray)
    blur = cv2.GaussianBlur(cl, (5, 5), 0)

    return cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)
    
def show_debug_page():

    st.header("🔍 답안 채점")

    exams = load_exams()
    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    exam_name = st.selectbox("시험 선택", list(exams.keys()))
    exam = exams[exam_name]

    if not exam.get("layout") or not exam.get("template_path"):
        st.warning("템플릿 설정 필요")
        return

    tab_pdf, tab_img = st.tabs(["📄 PDF", "🖼 JPG/PNG"])

    with tab_pdf:

        uploaded_pdf = st.file_uploader("PDF 업로드", type=["pdf"])

        if uploaded_pdf and st.button("채점 시작"):

        # -------------------------------------------------
        # 🔥 PDF → 이미지 변환 (PyMuPDF)
        # -------------------------------------------------
        pdf_bytes = uploaded_pdf.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        pages = []

        for page_index in range(len(doc)):
            page = doc[page_index]
            pix = page.get_pixmap(dpi=200)

            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, pix.n)

            # RGBA → RGB 변환
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

            pages.append(img)

        # -------------------------------------------------
        # 템플릿 로딩
        # -------------------------------------------------
        stream = np.fromfile(exam["template_path"], np.uint8)
        template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

        layout = exam["layout"]
        sections = exam.get("sections", {})
        scores = exam.get("scores", {})

        # -------------------------------------------------
        # 페이지별 디버그
        # -------------------------------------------------
        for idx, page_img in enumerate(pages):

            st.subheader(f"📄 페이지 {idx+1}")

            # RGB → BGR 변환
            student_img = cv2.cvtColor(page_img, cv2.COLOR_RGB2BGR)
            aligned = align_images_orb(template_img, student_img, layout)

            if aligned is None:
                st.error("ORB 정렬 실패")
                return

            aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
            debug_img = aligned.copy()

            total_score = 0
            section_scores = {sec_id: 0 for sec_id in sections}

            # ============================
            # 문항 루프
            # ============================
            for q in range(1, exam["num_questions"] + 1):

                if str(q) not in layout.get("y_ranges", {}):
                    continue

                col_index = ((q - 1) // layout["questions_per_column"]) + 1
                col_index = str(min(col_index, len(layout["columns_x"])) )

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

                is_correct = set(correct) == set(selected)

                # 🔴 오답 문항 반투명
                if not is_correct:
                    qx = layout.get("question_x_range")
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
                            overlay, 0.25,
                            debug_img, 0.75, 0
                        )

                # 점수 계산
                if is_correct:
                    total_score += scores.get(str(q), 1)
                    for sec_id, sec in sections.items():
                        if q in sec.get("questions", []):
                            section_scores[sec_id] += scores.get(str(q), 1)

                # 🔴 기본 좌표선
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

                # 🔵 정답 표시
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

                # 🟢 학생 선택 표시
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

                # 문항 번호 표시
                qx = layout.get("question_x_range")
                if qx:
                    cv2.putText(
                        debug_img,
                        f"Q{q}",
                        (qx[0], y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )

            # ============================
            # 영역 점수 표시
            # ============================
            cols = st.columns(len(section_scores) + 1)

            i = 0
            for sec_id, score_val in section_scores.items():
                sec_name = sections[sec_id]["name"]

                cols[i].markdown(
                    f"""
                    <div style="text-align:center; line-height:1.05;">
                        <div style="font-size:30px; margin-bottom:4px;">
                            {sec_name}
                        </div>
                        <div style="font-size:44px; font-weight:bold;">
                            {score_val}점
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                i += 1

            cols[i].markdown(
                f"""
                <div style="text-align:center; line-height:1.05;">
                    <div style="font-size:32px; margin-bottom:4px;">
                        총점
                    </div>
                    <div style="font-size:50px; font-weight:bold; color:#2E8B57;">
                        {total_score}점
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.image(debug_img, channels="BGR")

            # ==================================
            # 🖼 이미지 디버그 추가 부분
            # ==================================
            with tab_img:

                uploaded_img = st.file_uploader(
                    "JPG / PNG 업로드",
                    type=["jpg", "jpeg", "png"],
                    key="debug_img"
                )

                if uploaded_img and st.button("채점 시작 (이미지)"):

                    file_bytes = uploaded_img.read()
                    file_array = np.frombuffer(file_bytes, np.uint8)
                    student_img = cv2.imdecode(file_array, cv2.IMREAD_COLOR)

                    # 🔥 자동 보정
                    student_img = auto_deskew(student_img)
                    student_img = enhance_mobile_image(student_img)

                    stream = np.fromfile(exam["template_path"], np.uint8)
                    template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)

                    aligned = align_images_orb(template_img, student_img, layout)

                    if aligned is None:
                        st.error("ORB 정렬 실패")
                        return

                    st.success("정렬 성공")
                    st.image(aligned, channels="BGR")


