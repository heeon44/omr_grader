import streamlit as st
import pandas as pd
import io

from core.database import load_exams


def show_exam_analysis_page():

    st.header("📊 시험 분석")

    exams = load_exams()

    if not exams:
        st.warning("등록된 시험이 없습니다.")
        return

    exam_name = st.selectbox("시험 선택", list(exams.keys()))
    exam = exams[exam_name]

    uploaded_files = st.file_uploader(
        "답안 Excel 업로드",
        type=["xlsx"],
        accept_multiple_files=True
    )

    if not uploaded_files:
        st.info("분석할 Excel 파일을 업로드하세요.")
        return

    dfs = []

    for file in uploaded_files:
        df = pd.read_excel(file)
        dfs.append(df)

    data = pd.concat(dfs, ignore_index=True)

    total_students = len(data)

    question_cols = [c for c in data.columns if c.startswith("Q")]

    results = []

    for q in question_cols:

        q_num = q.replace("Q", "")

        correct_answer = exam["answers"][q_num]["answer"]

        if isinstance(correct_answer, list):
            correct_answer = correct_answer[0]

        correct_answer = str(correct_answer)

        counts = data[q].astype(str).value_counts()

        row = {
            "문항": q,
            "정답": correct_answer
        }

        correct_count = counts.get(correct_answer, 0)

        correct_rate = (correct_count / total_students) * 100

        row["정답률"] = f"{correct_rate:.1f}% ({correct_count}명)"

        wrong_counts = counts.drop(correct_answer, errors="ignore")

        attractive = ""

        if len(wrong_counts) > 0:
            attractive_choice = wrong_counts.idxmax()
            attractive_count = wrong_counts.max()

            attractive_rate = (attractive_count / total_students) * 100

            attractive = f"{attractive_choice} ({attractive_rate:.1f}%/{attractive_count}명)"

        row["매력적 오답"] = attractive

        for choice in ["1", "2", "3", "4", "5"]:

            count = counts.get(choice, 0)

            rate = (count / total_students) * 100

            row[choice] = f"{rate:.1f}% ({count}명)"

        results.append(row)

    result_df = pd.DataFrame(results)

    st.subheader("문항 분석 결과")

    st.dataframe(result_df, use_container_width=True)

    output = io.BytesIO()

    with pd.ExcelWriter(output) as writer:
        result_df.to_excel(writer, index=False)

    excel_data = output.getvalue()

    st.download_button(
        "📥 분석 결과 Excel 다운로드",
        excel_data,
        f"{exam_name}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
