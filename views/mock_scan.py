import streamlit as st
import pandas as pd
import json

from grader import process_pdf


def load_template():
    with open("template.json", "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    st.title("🧪 모의 판독")

    uploaded_file = st.file_uploader("PDF 업로드", type=["pdf"])

    if uploaded_file:
        with st.spinner("OMR 판독 중..."):

            template = load_template()
            results = process_pdf(uploaded_file, template)

            clean_results = []

            for r in results:
                row = {}

                # ✅ 이름 / 코드
                row["이름"] = r.get("name", "")
                row["개별코드"] = r.get("code", "")

                # ✅ 답안만 추출
                answers = r.get("answers", [])

                for i, a in enumerate(answers):
                    row[f"Q{i+1}"] = a

                clean_results.append(row)

            df = pd.DataFrame(clean_results)

            st.success("완료!")

            st.dataframe(df)

            st.download_button(
                "엑셀 다운로드",
                df.to_csv(index=False).encode("utf-8-sig"),
                "mock_result.csv"
            )
