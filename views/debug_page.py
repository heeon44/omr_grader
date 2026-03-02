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

    uploaded_pdf = st.file_uploader("PDF 업로드", type=["pdf"])

    if uploaded_pdf and st.button("채점 시작"):

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

        # 세션 초기화
        st.session_state.pages = pages
        st.session_state.answers = {}
        st.session_state.aligned_pages = {}
        st.session_state.exam_name = exam_name

        # 템플릿 로딩
        stream = np.fromfile(exam["template_path"], np.uint8)
        template_img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

        layout = exam["layout"]

        # 🔥 자동 채점 먼저 전체 실행
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

   		# ===============================
		# 페이지 이동 UI (← 3 / 18 →)
		# ===============================

		if "current_page" not in st.session_state:
			st.session_state.current_page = 0

		total_pages = len(st.session_state.aligned_pages)

		col1, col2, col3 = st.columns([1, 2, 1])

		with col1:
			if st.button("⬅"):
				if st.session_state.current_page > 0:
					st.session_state.current_page -= 1
					st.rerun()

		with col2:
			st.markdown(
				f"<h3 style='text-align:center'>"
				f"{st.session_state.current_page+1} / {total_pages}"
				f"</h3>",
				unsafe_allow_html=True
			)

		with col3:
			if st.button("➡"):
				if st.session_state.current_page < total_pages - 1:
					st.session_state.current_page += 1
					st.rerun()

		selected_page = st.session_state.current_page

    aligned = st.session_state.aligned_pages[selected_page]
    page_answers = st.session_state.answers[selected_page]

    layout = exam["layout"]
    sections = exam.get("sections", {})
    scores = exam.get("scores", {})

    debug_img = aligned.copy()
    total_score = 0
    section_scores = {sec_id: 0 for sec_id in sections}

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

        if is_correct:
            total_score += scores.get(str(q), 1)
            for sec_id, sec in sections.items():
                if q in sec.get("questions", []):
                    section_scores[sec_id] += scores.get(str(q), 1)

        for i in range(5):
            if i + 1 >= len(x_bounds):
                continue

            bubble_id = str(i + 1)

            if bubble_id in correct and bubble_id in selected:
                color = (0, 255, 0)
            elif bubble_id in correct:
                color = (255, 0, 0)
            elif bubble_id in selected:
                color = (0, 255, 255)
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

    st.image(debug_img, channels="BGR")

		# ===============================
		# 한눈에 보이는 가로형 답 수정 표
		# ===============================

		import pandas as pd

		st.markdown("### 📝 문항별 답 수정")

		page_answers = st.session_state.answers[selected_page]

		row_data = {}
		for q in range(1, exam["num_questions"] + 1):
			row_data[f"{q}번"] = ", ".join(page_answers.get(q, []))

		df = pd.DataFrame([row_data])

		edited_df = st.data_editor(
			df,
			key=f"editor_{selected_page}",
			use_container_width=True,
			num_rows="fixed"
		)

		if st.button("수정하기", key=f"save_{selected_page}"):

			new_answers = {}

			for col in edited_df.columns:
				q_num = int(col.replace("번", ""))
				value = str(edited_df.iloc[0][col]).strip()

				if value == "":
					new_answers[q_num] = []
				else:
					new_answers[q_num] = [v.strip() for v in value.split(",")]

			st.session_state.answers[selected_page] = new_answers
			st.rerun()
    # ===============================
    # 점수 표시
    # ===============================
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






