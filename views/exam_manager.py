import streamlit as st
import json
import copy

from core.database import load_exams, add_exam, update_exam, delete_exam, save_exams


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


def generate_copy_name(base_name, exams):

    new_name = f"{base_name}_복사"

    count = 2

    while new_name in exams:

        new_name = f"{base_name}_복사{count}"

        count += 1

    return new_name


def show_exam_manager():

    st.header("📋 시험 관리")

    tab1, tab2, tab3 = st.tabs([
        "📚 시험 목록",
        "➕ 시험 등록",
        "✏ 시험 수정"
    ])

    # ==================================================
    # 시험 목록
    # ==================================================

    with tab1:

        exams = load_exams()

        if not exams:
            st.info("등록된 시험이 없습니다.")

        else:

            for name, exam in exams.items():

                with st.expander(f"📘 {name}"):

                    st.write(f"문항 수: {exam.get('num_questions')}")
                    st.write(f"영역 수: {len(exam.get('sections', {}))}")

                    new_name = st.text_input(
                        "새 시험 이름",
                        value=name,
                        key=f"rename_input_{name}"
                    )

                    col1, col2, col3 = st.columns(3)

                    if col1.button("삭제", key=f"del_{name}"):

                        delete_exam(name)
                        st.rerun()

                    if col2.button("복사", key=f"copy_{name}"):

                        new_copy_name = generate_copy_name(name, exams)

                        exams[new_copy_name] = copy.deepcopy(exam)

                        save_exams(exams)

                        st.success("복사 완료")
                        st.rerun()

                    if col3.button("이름 변경", key=f"rename_btn_{name}"):

                        if new_name in exams and new_name != name:

                            st.error("이미 존재하는 시험 이름입니다.")

                        else:

                            exams[new_name] = exams.pop(name)
                            save_exams(exams)

                            st.success("이름 변경 완료")
                            st.rerun()

    # ==================================================
    # 시험 등록
    # ==================================================

    with tab2:

        st.subheader("➕ 새 시험 등록")

        exam_name = st.text_input("시험 이름")

        num_questions = st.number_input(
            "문항 수",
            min_value=1,
            value=20
        )

        answers = {}
        scores = {}

        st.markdown("### 📝 문항 설정")

        for q in range(1, num_questions + 1):

            col1, col2, col3 = st.columns([1,2,1])

            q_type_label = col1.selectbox(
                f"{q}번 유형",
                ["객관식", "단답식"],
                key=f"new_type_{q}"
            )

            q_type = "mcq" if q_type_label == "객관식" else "short"

            ans_input = col2.text_input(
                f"{q}번 정답",
                key=f"new_ans_{q}"
            )

            score = col3.number_input(
                f"{q}번 배점",
                value=1,
                key=f"new_score_{q}"
            )

            if q_type == "mcq":

                ans = ans_input.strip()

                if "or" in ans:
                    answer_value = [ans]

                elif "," in ans:
                    answer_value = [x.strip() for x in ans.split(",") if x.strip()]

                elif ans:
                    answer_value = [ans]

                else:
                    answer_value = []

            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {"type": q_type, "answer": answer_value}
            scores[str(q)] = score

        st.markdown("### 📂 영역 설정")

        num_sections = st.number_input(
            "영역 개수",
            min_value=1,
            value=1,
            step=1
        )

        sections = {}

        for i in range(1, int(num_sections) + 1):

            sec_name = st.text_input(
                f"{i}번 영역 이름",
                key=f"{exam_name}_secname_{i}"
            )

            sec_q = st.text_input(
                f"{i}번 영역 문항 범위 (예: 1-5,7,9)",
                key=f"{exam_name}_secq_{i}"
            )

            sections[str(i)] = {
                "name": sec_name,
                "questions": parse_question_range(sec_q)
            }

        if st.button("시험 등록"):

            new_data = {
                "num_questions": num_questions,
                "answers": answers,
                "scores": scores,
                "sections": sections,
                "layout": {},
                "template_path": ""
            }

            add_exam(exam_name, new_data)

            st.success("시험 등록 완료")
            st.rerun()

    # ==================================================
    # 시험 수정
    # ==================================================

    with tab3:

        st.subheader("✏ 시험 수정")

        exams = load_exams()

        if not exams:

            st.warning("등록된 시험이 없습니다.")
            st.stop()

        exam_names = list(exams.keys())

        selected_exam = st.selectbox(
            "시험 선택",
            exam_names,
            key="exam_edit_selectbox"
        )

        exam_data = exams[selected_exam]

        st.markdown("---")

        exam_name = st.text_input(
            "시험 이름",
            value=selected_exam
        )

        num_questions = st.number_input(
            "문항 수",
            min_value=1,
            value=exam_data.get("num_questions", 20)
        )

        answers = {}
        scores = {}

        st.markdown("### 📝 문항 설정")

        for q in range(1, num_questions + 1):

            raw_data = exam_data.get("answers", {}).get(str(q), {})

            if isinstance(raw_data, dict):

                default_type = raw_data.get("type", "mcq")
                default_ans = raw_data.get("answer", [])

            else:

                default_type = "mcq"
                default_ans = raw_data

            col1, col2, col3 = st.columns([1, 2, 1])

            q_type_label = col1.selectbox(
                f"{q}번 유형",
                ["객관식", "단답식"],
                index=0 if default_type == "mcq" else 1,
                key=f"{selected_exam}_type_{q}"
            )

            q_type = "mcq" if q_type_label == "객관식" else "short"

            if q_type == "mcq":

                if isinstance(default_ans, list):
                    default_ans = ",".join(default_ans)

            ans_input = col2.text_input(
                f"{q}번 정답",
                value=default_ans,
                key=f"{selected_exam}_ans_{q}"
            )

            score = col3.number_input(
                f"{q}번 배점",
                value=exam_data.get("scores", {}).get(str(q), 1),
                key=f"{selected_exam}_score_{q}"
            )

            if q_type == "mcq":

                ans = ans_input.strip()

                if "or" in ans:
                    answer_value = [ans]

                elif "," in ans:
                    answer_value = [x.strip() for x in ans.split(",") if x.strip()]

                elif ans:
                    answer_value = [ans]

                else:
                    answer_value = []

            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {"type": q_type, "answer": answer_value}
            scores[str(q)] = score

        st.markdown("---")
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
                key=f"{exam_name}_secname_{i}"
            )

            default_range = ""
            if default_sec.get("questions"):
                default_range = ",".join(map(str, default_sec["questions"]))

            sec_q = st.text_input(
                f"{i}번 영역 문항 범위 (예: 1-5,7,9)",
                value=default_range,
                key=f"{exam_name}_secq_{i}"
            )

            sections[str(i)] = {
                "name": sec_name,
                "questions": parse_question_range(sec_q)
            }

        if st.button("시험 수정 저장"):

            new_data = {
                "num_questions": num_questions,
                "answers": answers,
                "scores": scores,
                "sections": sections,
                "layout": exam_data.get("layout", {}),
                "template_path": exam_data.get("template_path", "")
            }

            if exam_name != selected_exam:

                exams[exam_name] = new_data
                del exams[selected_exam]
                save_exams(exams)

            else:

                update_exam(selected_exam, new_data)

            st.success("수정 완료")
            st.rerun()
