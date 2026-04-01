import streamlit as st
import pandas as pd
import json

from grader import process_pdf  # 기존 채점 로직 그대로 사용


# -----------------------------------
# 📄 템플릿 로드
# -----------------------------------
def load_template():
    with open("template.json", "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------------
# 🧪 모의 판독 페이지
# -----------------------------------
def show_mock_scan_page():

    st.title("🧪 모의 판독")

    uploaded_file = st.file_uploader("PDF 파일 업로드", type=["pdf"])

    if uploaded_file:

        with st.spinner("OMR 판독 중입니다..."):

            try:
                template = load_template()

                # ✅ 핵심: 정답 없어도 안 터지게 안전 처리
                if "correct_answers" not in template:
                    template["correct_answers"] = []

                # 👉 기존 채점 함수 그대로 사용
                results = process_pdf(uploaded_file, template)

                if not results:
                    st.warning("결과가 없습니다.")
                    return

                clean_results = []

                for r in results:
                    row = {}

                    # -------------------------
                    # 이름 / 코드
                    # -------------------------
                    row["이름"] = r.get("name", "")
                    row["개별코드"] = r.get("code", "")

                    # -------------------------
                    # 답안 펼치기
                    # -------------------------
                    answers = r.get("answers", [])

                    for i, a in enumerate(answers):
                        row[f"Q{i+1}"] = a

                    clean_results.append(row)

                df = pd.DataFrame(clean_results)

                # -------------------------
                # 결과 출력
                # -------------------------
                st.success("✅ 판독 완료!")
                st.dataframe(df, use_container_width=True)

                # -------------------------
                # 다운로드
                # -------------------------
                csv = df.to_csv(index=False).encode("utf-8-sig")

                st.download_button(
                    "📥 엑셀 다운로드",
                    csv,
                    "mock_result.csv",
                    "text/csv"
                )

            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
