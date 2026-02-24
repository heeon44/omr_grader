import streamlit as st
import cv2
import numpy as np
import pandas as pd
import io
import fitz  # 🔥 PyMuPDF (Poppler 필요 없음)
from openpyxl import Workbook
from openpyxl.styles import PatternFill

from core.database import load_exams
from core.omr_engine import align_images_orb, detect_answer
from core.scoring import grade_student


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

    uploaded_pdf = st.file_uploader("PDF 업로드", type=["pdf"])

    if uploaded_pdf and st.button("채점 시작"):

        with st.spinner("📄 채점 진행 중..."):

            # -------------------------------------------------
            # 🔥 PDF → 이미지 변환 (PyMuPDF 방식)
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
            results = []
            progress_bar = st.progress(0)

            # -------------------------------------------------
            # 페이지별 채점
            # -------------------------------------------------
            for idx, page_img in enumerate(pages):

                # PyMuPDF는 RGB → BGR 변환
                student_img = cv2.cvtColor(page_img, cv2.COLOR_RGB2BGR)

                aligned = align_images_orb(template_img, student_img)

                if aligned is None:
                    st.error("ORB 정렬 실패")
                    return

                aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)

                row = {
                    "페이지 번호": idx + 1
                }

                # -------------------------------------------------
                # 객관식 처리
                # -------------------------------------------------
                for q in range(1, exam["num_questions"] + 1):

                    q_data = exam["answers"].get(str(q), {})
                    q_type = q_data.get("type", "mcq")

                    if q_type != "mcq":
                        row[f"{q}번_학생답"] = ""
                        continue

                    if str(q) not in layout.get("y_ranges", {}):
                        row[f"{q}번_학생답"] = ""
                        continue

                    if not layout.get("columns_x"):
                        row[f"{q}번_학생답"] = ""
                        continue

                    col_index = ((q - 1) // layout.get("questions_per_column", 1)) + 1
                    col_index = str(min(col_index, len(layout["columns_x"])))

                    if col_index not in layout["columns_x"]:
                        row[f"{q}번_학생답"] = ""
                        continue

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

                # 채점
                row = grade_student(row, exam)
                results.append(row)

                progress_bar.progress((idx + 1) / len(pages))

        # -------------------------------------------------
        # 결과 정리
        # -------------------------------------------------
        df = pd.DataFrame(results)

        ordered_cols = ["페이지 번호"]

        for q in range(1, exam["num_questions"] + 1):
            ordered_cols.append(f"{q}번")

        for sec_id, sec in exam.get("sections", {}).items():
            sec_name = sec.get("name", f"영역{sec_id}")
            ordered_cols.append(f"{sec_name}_총점")

        ordered_cols += ["총점", "틀린 문항"]

        df = df[ordered_cols]

        st.success("채점 완료 ✅")
        st.dataframe(df, use_container_width=True)

        # -------------------------------------------------
        # 엑셀 다운로드
        # -------------------------------------------------
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active

        ws.append(list(df.columns))

        red_fill = PatternFill(
            start_color="FFCCCC",
            end_color="FFCCCC",
            fill_type="solid"
        )

        for row_idx, row in df.iterrows():
            ws.append(list(row))
            for col_idx, value in enumerate(row, start=1):
                if value == "X":
                    ws.cell(row=row_idx + 2, column=col_idx).fill = red_fill

        wb.save(output)
        output.seek(0)

        st.download_button(
            label="📥 엑셀 다운로드",
            data=output,
            file_name="채점결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
