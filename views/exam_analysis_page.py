import streamlit as st
import pandas as pd
import io

from core.database import load_exams


# ------------------------------
# 값 정규화
# ------------------------------
def normalize_answer(v):

    if pd.isna(v):
        return None

    v = str(v)

    if v.endswith(".0"):
        v = v[:-2]

    return v.strip()


# ------------------------------
# 난이도 계산
# ------------------------------
def get_difficulty(rate):

    if rate < 30:
        return "어려움"
    elif rate < 70:
        return "보통"
    else:
        return "쉬움"


# ------------------------------
# 페이지
# ------------------------------
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

    dfs = []

    for file in uploaded_files:
        df = pd.read_excel(file)
        dfs.append(df)

    data = pd.concat(dfs, ignore_index=True)

    total_students = len(data)

    st.success(f"총 응시 인원: {total_students}명")

    question_cols = [c for c in data.columns if c.startswith("Q")]

    results = []
    graphs = {}

    # ------------------------------
    # 문항 분석
    # ------------------------------

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
        wrong_rate = 100 - correct_rate

        row["정답률"] = f"{correct_rate:.1f}% ({correct_count}명)"
        row["오답률"] = f"{wrong_rate:.1f}%"

        row["난이도"] = get_difficulty(correct_rate)

        wrong_counts = counts.drop(correct, errors="ignore")

        if len(wrong_counts) > 0:

            distractor = wrong_counts.idxmax()
            distractor_count = wrong_counts.max()

            distractor_rate = (distractor_count / total_students) * 100

            row["매력적 오답"] = f"{distractor} ({distractor_rate:.1f}%/{distractor_count}명)"

        else:
            row["매력적 오답"] = ""

        choice_counts = {}

        for choice in ["1", "2", "3", "4", "5"]:

            count = counts.get(choice, 0)

            rate = (count / total_students) * 100

            row[choice] = f"{rate:.1f}% ({count}명)"

            choice_counts[choice] = count

        graphs[q] = choice_counts

        results.append(row)

    result_df = pd.DataFrame(results)

    # ------------------------------
    # 문항 번호 순 정렬
    # ------------------------------

    result_df["문항번호"] = result_df["문항"].str.replace("Q", "").astype(int)

    result_df = result_df.sort_values("문항번호")

    result_df = result_df.drop(columns=["문항번호"])

    st.subheader("📋 문항 분석 결과")

    st.dataframe(result_df, use_container_width=True)

    # ------------------------------
    # 시험 요약 계산
    # ------------------------------

    correct_rates = []

    for r in results:
        rate = float(r["정답률"].split("%")[0])
        correct_rates.append(rate)

    avg_rate = sum(correct_rates) / len(correct_rates)

    hardest_q = result_df.iloc[0]["문항"]
    easiest_q = result_df.iloc[-1]["문항"]

    summary_df = pd.DataFrame({
        "항목": ["응시 인원", "평균 정답률", "가장 어려운 문제", "가장 쉬운 문제"],
        "값": [
            total_students,
            f"{avg_rate:.1f}%",
            hardest_q,
            easiest_q
        ]
    })

    # ------------------------------
    # Excel 저장
    # ------------------------------

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        result_df.to_excel(writer, sheet_name="문항분석", index=False)
        summary_df.to_excel(writer, sheet_name="시험요약", index=False)

        workbook = writer.book
        chart_sheet = workbook.add_worksheet("선지그래프")

        for i, (q, counts) in enumerate(graphs.items()):

            col = i * 7

            chart_sheet.write(0, col, q)

            chart_sheet.write_column(1, col, ["1", "2", "3", "4", "5"])
            chart_sheet.write_column(1, col + 1, [
                counts.get("1", 0),
                counts.get("2", 0),
                counts.get("3", 0),
                counts.get("4", 0),
                counts.get("5", 0)
            ])

            chart = workbook.add_chart({"type": "column"})

            chart.add_series({
                "categories": ["선지그래프", 1, col, 5, col],
                "values": ["선지그래프", 1, col + 1, 5, col + 1],
                "name": q
            })

            chart.set_title({"name": q})

            chart_sheet.insert_chart(7, col, chart)

    st.download_button(
        "📥 분석 결과 Excel 다운로드",
        output.getvalue(),
        f"{exam_name}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
