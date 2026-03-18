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

        st.markdown("---")
        st.subheader("📦 시험자료 백업 / 복원")

        backup_json = json.dumps(
            exams,
            ensure_ascii=False,
            indent=2
        )

        st.download_button(
            label="📥 전체 시험자료 JSON 다운로드",
            data=backup_json,
            file_name="exam_backup.json",
            mime="application/json"
        )

        st.markdown("### 📂 선택 시험 다운로드")

        exam_names = list(exams.keys())

        if exam_names:

            selected_exam = st.selectbox(
                "다운로드할 시험 선택",
                exam_names,
                key="exam_backup_select"
            )

            single_exam = {selected_exam: exams[selected_exam]}

            exam_json = json.dumps(
                single_exam,
                ensure_ascii=False,
                indent=2
            )

            st.download_button(
                label="📥 선택 시험 다운로드",
                data=exam_json,
                file_name=f"{selected_exam}.json",
                mime="application/json"
            )

        st.markdown("### 📤 시험자료 JSON 업로드 복원")

        uploaded_backup = st.file_uploader(
            "시험자료 JSON 업로드",
            type=["json"]
        )

        if uploaded_backup is not None:

            try:

                data = json.load(uploaded_backup)

                exams.update(data)

                save_exams(exams)

                st.success("시험자료 복원 완료")
                st.rerun()

            except Exception as e:

                st.error(f"복원 실패: {e}")

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
                answer_value = ans_input.strip()
            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {"type": q_type, "answer": answer_value}
            scores[str(q)] = score

        if st.button("시험 등록"):

            new_data = {
                "num_questions": num_questions,
                "answers": answers,
                "scores": scores,
                "sections": {},
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

        # ⭐ 시험 목록 다시 불러오기
        exams = load_exams()

        if not exams:

            st.warning("등록된 시험이 없습니다.")
            st.stop()

        exam_names = list(exams.keys())

        # ⭐ 시험 선택
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
                answer_value = ans_input.strip()
            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {"type": q_type, "answer": answer_value}
            scores[str(q)] = score

        st.markdown("---")

        if st.button("시험 수정 저장"):

            new_data = {
                "num_questions": num_questions,
                "answers": answers,
                "scores": scores,
                "sections": exam_data.get("sections", {}),
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
