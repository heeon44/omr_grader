import streamlit as st
import pandas as pd


def show_edit_page():

    st.header("✏️ 답안 수정")

    # ===============================
    # 1️⃣ 채점 결과 존재 여부 확인
    # ===============================
    if "answers" not in st.session_state:
        st.warning("먼저 채점을 진행하세요.")
        return

    answers = st.session_state.answers
    num_questions = st.session_state.get("num_questions", len(answers))

    # ===============================
    # 2️⃣ DataFrame 변환
    # ===============================
    data = []

    for q in range(1, num_questions + 1):
        selected = answers.get(q, [])
        data.append({
            "문항": q,
            "선택한 답": ", ".join(selected) if selected else ""
        })

    df = pd.DataFrame(data)

    # ===============================
    # 3️⃣ 수정 가능한 표
    # ===============================
    st.markdown("### 📝 선택한 답 수정")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed"
    )

    # ===============================
    # 4️⃣ 수정 내용 반영 버튼
    # ===============================
    if st.button("수정 내용 저장"):

        new_answers = {}

        for _, row in edited_df.iterrows():
            q = int(row["문항"])
            value = str(row["선택한 답"]).strip()

            if value == "":
                new_answers[q] = []
            else:
                new_answers[q] = [
                    v.strip() for v in value.split(",")
                ]

        st.session_state.answers = new_answers

        st.success("수정 내용이 반영되었습니다.")

    # ===============================
    # 5️⃣ 현재 반영된 결과 미리보기
    # ===============================
    st.markdown("### 🔍 현재 반영된 답안")

    preview_data = []

    for q in range(1, num_questions + 1):
        preview_data.append({
            "문항": q,
            "최종 답": ", ".join(st.session_state.answers.get(q, []))
        })

    preview_df = pd.DataFrame(preview_data)
    st.dataframe(preview_df, use_container_width=True)
