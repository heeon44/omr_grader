import streamlit as st
import json
from core.database import load_exams, add_exam, update_exam, delete_exam


def parse_question_range(text):
    result = []
    if not text:
        return result

    parts = text.split(",")
    for p in parts:
        p = p.strip()
        if "-" in p:
            start, end = map(int, p.split("-"))
            result.extend(range(start, end + 1))
        else:
            result.append(int(p))

    return sorted(list(set(result)))


def show_exam_manager():

    st.header("📋 시험 관리")

    exams = load_exams()

    tab1, tab2 = st.tabs(["📚 시험 목록", "✏ 시험 등록 / 수정"])

    # ==================================================
    # 📚 시험 목록
    # ==================================================
    with tab1:

        if not exams:
            st.info("등록된 시험이 없습니다.")
        else:
            for name, exam in exams.items():

                with st.expander(f"📘 {name}"):

                    st.write(f"문항 수: {exam.get('num_questions')}")
                    st.write(f"영역 수: {len(exam.get('sections', {}))}")

                    col1, col2 = st.columns(2)

                    if col1.button("수정", key=f"edit_{name}"):
                        st.session_state["edit_exam"] = name
                        st.rerun()

                    if col2.button("삭제", key=f"del_{name}"):
                        delete_exam(name)
                        st.rerun()

    # ==================================================
    # ✏ 시험 등록 / 수정
    # ==================================================
    with tab2:

        edit_name = st.session_state.get("edit_exam")
        exam_data = exams.get(edit_name, {}) if edit_name else {}

        if edit_name:
            st.subheader(f"✏ 시험 수정: {edit_name}")
            exam_name = edit_name
        else:
            exam_name = st.text_input("시험 이름")

        num_questions = st.number_input(
            "문항 수",
            min_value=1,
            value=exam_data.get("num_questions", 20)
        )

        st.markdown("### 📝 문항 설정")

        answers = {}
        scores = {}

        for q in range(1, num_questions + 1):

            raw_data = exam_data.get("answers", {}).get(str(q), {})

            if isinstance(raw_data, list):
                default_data = {
                    "type": "mcq",
                    "answer": raw_data
                }
            elif isinstance(raw_data, dict):
                default_data = raw_data
            else:
                default_data = {
                    "type": "mcq",
                    "answer": []
                }

            col1, col2, col3 = st.columns([1, 2, 1])

            q_type = col1.selectbox(
                f"{q}번 유형",
                ["mcq", "short"],
                index=0 if default_data.get("type", "mcq") == "mcq" else 1,
                key=f"type_{q}"
            )

            if q_type == "mcq":
                default_ans = ",".join(default_data.get("answer", []))
            else:
                default_ans = default_data.get("answer", "")

            ans_input = col2.text_input(
                f"{q}번 정답",
                value=default_ans,
                key=f"ans_{q}"
            )

            score = col3.number_input(
                f"{q}번 배점",
                value=exam_data.get("scores", {}).get(str(q), 1),
                key=f"score_{q}"
            )

            if q_type == "mcq":
                answer_value = [x.strip() for x in ans_input.split(",")] if ans_input else []
            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {
                "type": q_type,
                "answer": answer_value
            }

            scores[str(q)] = score

        # ==================================================
        # 📂 영역 설정
        # ==================================================
        st.markdown("### 📂 영역 설정")

        existing_sections = exam_data.get("sections", {})
        default_section_count = len(existing_sections) if existing_sections else 1

        num_sections = st.number_input(
            "영역 개수",
            min_value=1,
            value=default_section_count,
            step=1
        )

        sections = {}

        for i in range(1, int(num_sections) + 1):

            default_sec = existing_sections.get(str(i), {})

            sec_name = st.text_input(
                f"{i}번 영역 이름",
                value=default_sec.get("name", ""),
                key=f"secname_{i}"
            )

            default_range = ""
            if default_sec.get("questions"):
                default_range = ",".join(map(str, default_sec["questions"]))

            sec_q = st.text_input(
                f"{i}번 영역 문항 범위 (예: 1-5,7,9)",
                value=default_range,
                key=f"secq_{i}"
            )

            sections[str(i)] = {
                "name": sec_name,
                "questions": parse_question_range(sec_q)
            }

        # ==================================================
        # 💾 저장
        # ==================================================
        if st.button("💾 시험 저장 / 수정 완료"):

            new_data = {
                "num_questions": num_questions,
                "answers": answers,
                "scores": scores,
                "sections": sections,
                "layout": exam_data.get("layout", {}),
                "template_path": exam_data.get("template_path", "")
            }

            if edit_name:
                update_exam(edit_name, new_data)
                del st.session_state["edit_exam"]
            else:
                add_exam(exam_name, new_data)

            st.success("저장 완료")
            st.rerun()

    # ==================================================
    # 🔥 백업 / 복원 기능 (추가 기능)
    # ==================================================

    st.markdown("---")
    st.subheader("📦 시험자료 백업 / 복원")

    exams = load_exams()

    # 📥 백업 다운로드
    backup_json = json.dumps(exams, ensure_ascii=False, indent=2)

    st.download_button(
        label="📥 시험자료 JSON 다운로드",
        data=backup_json,
        file_name="exam_backup.json",
        mime="application/json"
    )

    # 📤 복원 업로드
    uploaded_backup = st.file_uploader(
        "📤 시험자료 JSON 업로드로 복원",
        type=["json"]
    )

    if uploaded_backup is not None:
        try:
            data = json.load(uploaded_backup)
            from core.database import save_exams
            save_exams(data)
            st.success("시험자료 복원 완료")
            st.rerun()
        except Exception as e:
            st.error(f"복원 실패: {e}")