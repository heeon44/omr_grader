import streamlit as st
import cv2
import numpy as np
import fitz  # 🔥 PyMuPDF
import pandas as pd
import io

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

# ===============================
# Excel 저장 함수
# ===============================
def generate_answer_excel():

    if "answers" not in st.session_state:
        return None

    exam_name = st.session_state.get("exam_name", "exam")

    rows = []

    for page, answers in st.session_state.answers.items():

        row = {"page": page + 1}

        for q, ans in answers.items():

            if isinstance(ans, list):
                row[f"Q{q}"] = ",".join(ans)
            else:
                row[f"Q{q}"] = ans

        rows.append(row)

    df = pd.DataFrame(rows)

    output = io.BytesIO()

    with pd.ExcelWriter(output) as writer:
        df.to_excel(writer, index=False)

    return output.getvalue(), exam_name

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

    uploaded_pdf = st.file_uploader("PDF 업로드", type=["pdf"])

    # =====================================================
    # 🔥 채점 시작 (최초 1회만 실행)
    # =====================================================
    start_grading = st.button("채점 시작")

    if uploaded_pdf and start_grading:

        # 🔥 이미 채점된 상태라면 초기화
        if "aligned_pages" in st.session_state:
            del st.session_state["aligned_pages"]
            del st.session_state["answers"]
            del st.session_state["current_page"]

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

        # 세션 초기화 (최초 채점용)
        st.session_state.answers = {}
        st.session_state.aligned_pages = {}
        st.session_state.current_page = 0
        st.session_state.exam_name = exam_name

        # 템플릿 로딩
        stream = np.fromfile(exam["template_path"], np.uint8)
        template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

        layout = exam["layout"]

        # =====================================================
        # 🔥 전체 자동채점 실행
        # =====================================================
        for idx, page_img in enumerate(pages):

            student_img = cv2.cvtColor(page_img, cv2.COLOR_RGB2BGR)
            aligned = align_images_orb(template_img, student_img, layout)

            if aligned is None:
                continue

            aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
            page_answers = {}

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

                page_answers[q] = selected

            st.session_state.answers[idx] = page_answers
            st.session_state.aligned_pages[idx] = aligned

        st.success("채점 완료!")
        st.rerun()

    # =====================================================
    # 🔥 채점된 데이터 없으면 종료
    # =====================================================
    if "aligned_pages" not in st.session_state:
        return
    # =====================================================
    # 🔥 현재 페이지 선택
    # =====================================================
    total_pages = len(st.session_state.aligned_pages)

    if st.session_state.current_page >= total_pages:
        st.session_state.current_page = 0

    selected_page = st.session_state.current_page

    aligned = st.session_state.aligned_pages[selected_page]

    # 🔥 항상 최신 수정값 사용
    page_answers = st.session_state.answers.get(selected_page, {})

    layout = exam["layout"]
    sections = exam.get("sections", {})
    scores = exam.get("scores", {})

    debug_img = aligned.copy()
    total_score = 0
    section_scores = {sec_id: 0 for sec_id in sections}

    # =====================================================
    # 🔥 수정값 기준으로 이미지 & 점수 계산
    # =====================================================
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
        selected = page_answers.get(q, [])

        is_correct = set(correct) == set(selected)

        # ===============================
        # 🔥 오답 문항 빨간 배경 표시
        # ===============================
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
                    overlay, 0.25,
                    debug_img, 0.75, 0
                )

        # ===============================
        # 🔥 점수 계산
        # ===============================
        if is_correct:
            total_score += scores.get(str(q), 1)
            for sec_id, sec in sections.items():
                if q in sec.get("questions", []):
                    section_scores[sec_id] += scores.get(str(q), 1)

        # ===============================
        # 🔥 버블 색상 표시
        # ===============================
        for i in range(5):
            if i + 1 >= len(x_bounds):
                continue

            bubble_id = str(i + 1)

            if bubble_id in correct and bubble_id in selected:
                color = (0, 255, 0)      # 🟢 정답 일치
            elif bubble_id in correct:
                color = (255, 0, 0)      # 🔵 정답
            elif bubble_id in selected:
                color = (0, 255, 255)    # 🟡 학생 선택
            else:
                continue

            overlay = debug_img.copy()
            cv2.rectangle(
                overlay,
                (x_bounds[i], y1),
                (x_bounds[i + 1], y2),
                color,
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
                color,
                4
            )

        # ===============================
        # 🔥 문항 번호 표시 (Q1, Q2 ...)
        # ===============================
        qx_ranges = layout.get("question_x_ranges", {})
        qx = qx_ranges.get(col_index)

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
    # =====================================================
    # 🔥 이미지 + 가로 5열 수정표
    # =====================================================

    col_img, col_edit = st.columns([3.5, 1.5], gap="small")

    with col_img:
        st.image(debug_img, channels="BGR", width=850)

    with col_edit:
        st.markdown("<div style='height:600px'></div>", unsafe_allow_html=True)

        st.markdown("### 📝 답 수정")

        updated_answers = {}
        total_q = exam["num_questions"]

        # 🔥 5개씩 가로 배열
        for row_start in range(1, total_q + 1, 5):

            cols = st.columns(5)

            for i in range(5):

                q = row_start + i
                if q > total_q:
                    continue

                current_value = ", ".join(page_answers.get(q, []))

                new_value = cols[i].text_input(
                    f"{q}",
                    value=current_value,
                    key=f"q_{selected_page}_{q}"
                )

                if new_value.strip() == "":
                    updated_answers[q] = []
                else:
                    updated_answers[q] = [
                        v.strip() for v in new_value.split(",")
                    ]

        if st.button("수정 반영", key=f"apply_{selected_page}"):

            st.session_state.answers[selected_page] = updated_answers
            st.rerun()

    # =====================================================
    # 🔥 페이지 이동 버튼 (완전 양끝 정렬)
    # =====================================================

nav_left, nav_center = st.columns([1,7])

with nav_left:
    if st.button("⬅", key=f"prev_btn_{selected_page}"):
        if st.session_state.current_page > 0:
            st.session_state.current_page -= 1
            st.rerun()

with nav_center:

    col_page, col_total, col_next = st.columns([0.4,2,0.6])

    page_input = col_page.text_input(
        "",
        value=str(st.session_state.current_page + 1),
        key=f"page_input_{selected_page}",
        label_visibility="collapsed"
    )

    col_total.markdown(
        f"<h4 style='margin-top:5px;'>/ {total_pages}</h4>",
        unsafe_allow_html=True
    )

    if col_next.button("➡", key=f"next_btn_{selected_page}"):
        if st.session_state.current_page < total_pages - 1:
            st.session_state.current_page += 1
            st.rerun()
    with nav_right:
        if st.button("➡", key=f"next_btn_{selected_page}"):
            if st.session_state.current_page < total_pages - 1:
                st.session_state.current_page += 1
                st.rerun()

    # =====================================================
    # 🔥 Excel 저장 버튼
    # =====================================================

    st.markdown("---")

    excel_data = generate_answer_excel()

    if excel_data:

        excel_bytes, exam_name = excel_data

        st.download_button(
            "📥 답안 Excel 저장",
            excel_bytes,
            file_name=f"{exam_name}_answers.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # =====================================================
    # 🔥 점수 표시 (수정값 기준)
    # =====================================================
    cols = st.columns(len(section_scores) + 1)

    i = 0
    for sec_id, score_val in section_scores.items():
        sec_name = sections[sec_id]["name"]

        cols[i].markdown(
            f"<h3 style='text-align:center'>{sec_name}</h3>"
            f"<h1 style='text-align:center'>{score_val}점</h1>",
            unsafe_allow_html=True
        )
        i += 1

    cols[i].markdown(
        f"<h3 style='text-align:center'>총점</h3>"
        f"<h1 style='text-align:center; color:#2E8B57'>{total_score}점</h1>",
        unsafe_allow_html=True
    )





















