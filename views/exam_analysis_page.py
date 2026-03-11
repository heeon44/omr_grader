import streamlit as st
import pandas as pd


def show_exam_analysis_page():

    st.header("📊 시험 분석")

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

    question_cols = [c for c in data.columns if c.startswith("Q")]

    results = []

    total_students = len(data)

    for q in question_cols:

        counts = data[q].value_counts()

        correct = counts.idxmax()
        correct_count = counts.max()

        correct_rate = correct_count / total_students
        wrong_rate = 1 - correct_rate

        # 매력적인 오답
        wrong_choices = counts.drop(correct, errors="ignore")

        attractive = None
        if len(wrong_choices) > 0:
            attractive = wrong_choices.idxmax()

        results.append({
            "문항": q,
            "응시수": total_students,
            "정답": correct,
            "정답률": round(correct_rate * 100, 1),
            "오답률": round(wrong_rate * 100, 1),
            "매력적 오답": attractive
        })

    result_df = pd.DataFrame(results)

    st.subheader("문항 분석 결과")
    st.dataframe(result_df, use_container_width=True)

    excel = result_df.to_excel(index=False)

    st.download_button(
        "📥 분석 결과 Excel 다운로드",
        excel,
        "exam_analysis.xlsx"
    )
