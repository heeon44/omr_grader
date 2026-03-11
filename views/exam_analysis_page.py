import streamlit as st
import pandas as pd
import io

from core.database import load_exams


def normalize_answer(v):
    if pd.isna(v):
        return None

    v = str(v)

    if v.endswith(".0"):
        v = v[:-2]

    return v.strip()


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
        st.info("Excel 파일을 업로드하세요.")
        return

    # ---------------------------------
    # Excel 여러개 병합
    # ---------------------------------

    dfs = []

    for file in uploaded_files:
        df = pd.read_excel(file)
        dfs.append(df)

    data = pd.concat(dfs, ignore_index=True)

    total_students = len(data)

    question_cols = [c for c in data.columns if c.startswith("Q")]

    results = []

    # ---------------------------------
    # 문항 분석
    # ---------------------------------

    for q in question_cols:

        q_num = q.replace("Q", "")

        correct = exam["answers"][q_num]["answer"]

        if isinstance(correct, list):
            correct = correct[0]

        correct = normalize_answer(correct)

        values = data[q].apply(normalize_answer).dropna()

        counts = values.value_counts()

        row = {
            "문항": q,
            "정답": correct
        }

        correct_count = counts.get(correct, 0)

        correct_rate = (correct_count / total_students) * 100

        row["정답률"] = f"{correct_rate:.1f}% ({correct_count}명)"

        # -----------------------------
        # 매력적 오답
        # -----------------------------

        wrong_counts = counts.drop(correct, errors="ignore")

        if len(wrong_counts) > 0:

            distractor = wrong_counts.idxmax()
            distractor_count = wrong_counts.max()

            distractor_rate = (distractor_count / total_students) * 100

            row["매력적 오답"] = f"{distractor} ({distractor_rate:.1f}%/{distractor_count}명)"

        else:
            row["매력적 오답"] = ""

        # -----------------------------
        # 선지 분포
        # -----------------------------

        for choice in ["1", "2", "3", "4", "5"]:

            count = counts.get(choice, 0)

            rate = (count / total_students) * 100

            row[choice] = f"{rate:.1f}% ({count}명)"

        results.append(row)

    result_df = pd.DataFrame(results)

    st.subheader("문항 분석 결과")

    st.dataframe(result_df, use_container_width=True)

    # ---------------------------------
    # Excel 다운로드
    # ---------------------------------

    output = io.BytesIO()

    with pd.ExcelWriter(output) as writer:
        result_df.to_excel(writer, index=False)

    st.download_button(
        "📥 분석 결과 Excel 다운로드",
        output.getvalue(),
        f"{exam_name}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
