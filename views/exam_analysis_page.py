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
# 변별도 평가
# ------------------------------
def get_discrimination_level(d):

    if d >= 0.4:
        return "매우 좋음"
    elif d >= 0.3:
        return "좋음"
    elif d >= 0.2:
        return "보통"
    else:
        return "나쁨"


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

    # ------------------------------
    # 문항 -> 영역 매핑
    # ------------------------------

    sections = exam.get("sections", {})

    question_area_map = {}

    for sec in sections.values():

        area_name = sec.get("name", "기타")
        questions = sec.get("questions", [])

        for q in questions:
            try:
                q_num = int(str(q).strip())
                question_area_map[q_num] = area_name
            except:
                continue

    areas = sorted(set(question_area_map.values()))

    if not areas:
        areas = ["기타"]

    # ------------------------------
    # 학생 총점 계산
    # ------------------------------

    student_scores = []
    area_scores_list = []

	for idx, row in data.iterrows():

		score = 0
		area_scores = {area: 0 for area in areas}

		for q in question_cols:

			q_num = int(str(q).replace("Q", "").strip())
			correct = exam["answers"][str(q_num)]["answer"]

			if not isinstance(correct, list):
				correct = [correct]

			correct = [normalize_answer(c) for c in correct]

				ans = normalize_answer(row[q])

				if ans in correct:
					score += 1
					area_scores[area] += 1

		student_scores.append(score)
		area_scores_list.append(area_scores)

    data["총점"] = student_scores

    for area in areas:
        data[f"{area}_점수"] = [a[area] for a in area_scores_list]

    # ------------------------------
    # 상위 / 하위 그룹
    # ------------------------------

    sorted_data = data.sort_values("총점", ascending=False)

    group_size = max(int(len(sorted_data) * 0.27), 1)

    top_group = sorted_data.head(group_size)
    bottom_group = sorted_data.tail(group_size)

    # ------------------------------
    # 문항 분석
    # ------------------------------

    results = []
    graphs = {}
    rate_map = {}

    for q in question_cols:

			q_num = int(str(q).replace("Q", "").strip())
			correct = exam["answers"][str(q_num)]["answer"]

        if not isinstance(correct, list):
            correct = [correct]

        correct = [normalize_answer(c) for c in correct]

        values = data[q].apply(normalize_answer)

        counts = values.value_counts()

        row = {
            "문항": q,
            "정답": ", ".join(correct)
        }

        correct_count = 0

        for c in correct:
            correct_count += counts.get(c, 0)

        correct_rate = (correct_count / total_students) * 100
        wrong_rate = 100 - correct_rate

        rate_map[q] = correct_rate

        row["정답률"] = f"{correct_rate:.1f}%"
        row["오답률"] = f"{wrong_rate:.1f}%"

        row["난이도"] = get_difficulty(correct_rate)

        wrong_counts = counts.drop(correct, errors="ignore")

        if len(wrong_counts) > 0:
            distractor = wrong_counts.idxmax()
            row["매력적 오답"] = distractor
        else:
            row["매력적 오답"] = ""

        choice_counts = {}

        for choice in ["1", "2", "3", "4", "5"]:

            count = counts.get(choice, 0)

            rate = (count / total_students) * 100

            row[choice] = f"{rate:.1f}% ({count}명)"

            choice_counts[choice] = count

        graphs[q] = choice_counts

        top_correct = 0
        bottom_correct = 0

        for idx, student in top_group.iterrows():

            ans = normalize_answer(student[q])

            if ans in correct:
                top_correct += 1

        for idx, student in bottom_group.iterrows():

            ans = normalize_answer(student[q])

            if ans in correct:
                bottom_correct += 1

        top_rate = top_correct / len(top_group)
        bottom_rate = bottom_correct / len(bottom_group)

        discrimination = top_rate - bottom_rate

        row["변별도"] = f"{discrimination:.2f}"
        row["변별도 평가"] = get_discrimination_level(discrimination)

        results.append(row)

    result_df = pd.DataFrame(results)

    result_df["문항번호"] = result_df["문항"].str.replace("Q", "").astype(int)
    result_df = result_df.sort_values("문항번호")
    result_df = result_df.drop(columns=["문항번호"])

    st.subheader("📋 문항 분석 결과")

    st.dataframe(result_df, use_container_width=True)

    rate_series = pd.Series(rate_map)

    hardest = rate_series.sort_values().head(5)
    easiest = rate_series.sort_values(ascending=False).head(5)

    avg_rate = rate_series.mean()

    exam_average = data["총점"].mean()

    area_averages = {}

    for area in areas:
        area_averages[area] = data[f"{area}_점수"].mean()

    summary_rows = [
        ["응시 인원", total_students],
        ["시험 평균 점수", f"{exam_average:.2f}"],
        ["평균 정답률", f"{avg_rate:.1f}%"],
        ["", ""],
        ["영역별 평균 점수", ""],
    ]

    for area, avg in area_averages.items():
        summary_rows.append([area, f"{avg:.2f}"])

    summary_rows.append(["", ""])
    summary_rows.append(["어려운 문제 TOP5", ""])

    for q, r in hardest.items():
        summary_rows.append([q, f"{r:.1f}%"])

    summary_rows.append(["", ""])
    summary_rows.append(["쉬운 문제 TOP5", ""])

    for q, r in easiest.items():
        summary_rows.append([q, f"{r:.1f}%"])

    summary_df = pd.DataFrame(summary_rows, columns=["항목", "값"])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        result_df.to_excel(writer, sheet_name="문항분석", index=False)
        summary_df.to_excel(writer, sheet_name="시험요약", index=False)

        workbook = writer.book
        worksheet = writer.sheets["문항분석"]
        summary_sheet = writer.sheets["시험요약"]

        header_format = workbook.add_format({
            "bold": True,
            "align": "center"
        })

        heatmap_90 = workbook.add_format({"bg_color": "#DDEBF7"})
        heatmap_70 = workbook.add_format({"bg_color": "#C6E0B4"})
        heatmap_50 = workbook.add_format({"bg_color": "#FFE699"})
        heatmap_30 = workbook.add_format({"bg_color": "#F8CBAD"})
        heatmap_10 = workbook.add_format({"bg_color": "#F4B084"})

        distractor_format = workbook.add_format({
            "bg_color": "#9DC3E6"
        })

        for col_num, value in enumerate(result_df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        worksheet.set_column(0, 0, 6)
        worksheet.set_column(1, 1, 8)
        worksheet.set_column(2, 4, 10)
        worksheet.set_column(5, 10, 14)

        legend_row = len(result_df) + 3

        worksheet.write(legend_row, 0, "색상 의미 (정답 선지 히트맵)")
        worksheet.write(legend_row + 1, 0, "90% 이상 : 매우 쉬운 문제", heatmap_90)
        worksheet.write(legend_row + 2, 0, "70% 이상 : 쉬운 문제", heatmap_70)
        worksheet.write(legend_row + 3, 0, "50% 이상 : 적정 난이도", heatmap_50)
        worksheet.write(legend_row + 4, 0, "30% 이상 : 어려운 문제", heatmap_30)
        worksheet.write(legend_row + 5, 0, "30% 미만 : 매우 어려운 문제", heatmap_10)

        worksheet.write(legend_row + 7, 0, "매력적 오답", distractor_format)

        start_row = len(summary_df) + 2

        summary_sheet.write(
            start_row + 7,
            0,
            "※ TOP5 옆 % 는 정답률을 의미합니다."
        )

        for row_idx, row in result_df.iterrows():

            correct_choices = str(row["정답"]).split(",")
            distractor = str(row["매력적 오답"]).strip()

            for choice in ["1", "2", "3", "4", "5"]:

                col_idx = result_df.columns.get_loc(choice)

                if choice in correct_choices:

                    rate = rate_map[row["문항"]]

                    if rate >= 90:
                        fmt = heatmap_90
                    elif rate >= 70:
                        fmt = heatmap_70
                    elif rate >= 50:
                        fmt = heatmap_50
                    elif rate >= 30:
                        fmt = heatmap_30
                    else:
                        fmt = heatmap_10

                    worksheet.write(row_idx + 1, col_idx, row[choice], fmt)

                elif choice == distractor:

                    worksheet.write(row_idx + 1, col_idx, row[choice], distractor_format)

        chart_sheet = workbook.add_worksheet("선지그래프")

        for i, (q, counts) in enumerate(graphs.items()):

            col = i * 7

            chart_sheet.write(0, col, q)

            chart_sheet.write_column(1, col, ["1", "2", "3", "4", "5"])
            chart_sheet.write_column(
                1,
                col + 1,
                [
                    counts.get("1", 0),
                    counts.get("2", 0),
                    counts.get("3", 0),
                    counts.get("4", 0),
                    counts.get("5", 0),
                ],
            )

            chart = workbook.add_chart({"type": "column"})

            chart.add_series({
                "categories": ["선지그래프", 1, col, 5, col],
                "values": ["선지그래프", 1, col + 1, 5, col + 1],
                "name": q,
            })

            chart.set_title({"name": q})

            chart_sheet.insert_chart(7, col, chart)

    st.download_button(
        "📥 분석 결과 Excel 다운로드",
        output.getvalue(),
        f"{exam_name}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
