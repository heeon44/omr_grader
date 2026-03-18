import streamlit as st
import json
import copy
import io
import zipfile
import os

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

    exams = load_exams()

    tab1, tab2 = st.tabs(["📚 시험 목록", "✏ 시험 등록 / 수정"])

    # ==================================================
    # 시험 목록
    # ==================================================

    with tab1:

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

                    # 삭제
                    if col1.button("삭제", key=f"del_{name}"):

                        delete_exam(name)

                        st.rerun()

                    # 복사
                    if col2.button("복사", key=f"copy_{name}"):

                        new_copy_name = generate_copy_name(name, exams)

                        copied_exam = copy.deepcopy(exam)

                        exams[new_copy_name] = copied_exam

                        save_exams(exams)

                        st.success(f"{new_copy_name} 생성 완료")

                        st.rerun()

                    # 이름 변경
                    if col3.button("이름 변경", key=f"rename_btn_{name}"):

                        if new_name in exams and new_name != name:

                            st.error("이미 존재하는 시험 이름입니다.")

                        else:

                            exams[new_name] = exams.pop(name)

                            save_exams(exams)

                            st.success("이름 변경 완료")

                            st.rerun()

        # ==================================================
        # 시험 백업
        # ==================================================

        st.markdown("---")
        st.subheader("📦 시험 백업")

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as z:

            exams_json = json.dumps(
                exams,
                ensure_ascii=False,
                indent=2
            ).encode("utf-8")

            z.writestr("exams_backup.json", exams_json)

        st.download_button(
            "📥 전체 시험 ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name="exam_full_backup.zip",
            mime="application/zip"
        )

        st.markdown("### 📂 선택 시험 백업")

        exam_names = list(exams.keys())

        if exam_names:

            selected_exam = st.selectbox(
                "백업할 시험 선택",
                exam_names
            )

            if selected_exam:

                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(zip_buffer, "w") as z:

                    single_exam = {
                        selected_exam: exams[selected_exam]
                    }

                    exam_json = json.dumps(
                        single_exam,
                        ensure_ascii=False,
                        indent=2
                    ).encode("utf-8")

                    z.writestr("exam_backup.json", exam_json)

                st.download_button(
                    "📥 선택 시험 ZIP 다운로드",
                    data=zip_buffer.getvalue(),
                    file_name=f"{selected_exam}_backup.zip",
                    mime="application/zip"
                )

        st.markdown("### 📤 시험 ZIP 복원")

        uploaded_zip = st.file_uploader(
            "시험 백업 ZIP 업로드",
            type=["zip"]
        )

        if uploaded_zip is not None:

            try:

                with zipfile.ZipFile(uploaded_zip, "r") as z:

                    z.extractall(".")

                if os.path.exists("exams_backup.json"):

                    with open(
                        "exams_backup.json",
                        "r",
                        encoding="utf-8"
                    ) as f:

                        restored_exams = json.load(f)

                    save_exams(restored_exams)

                    os.remove("exams_backup.json")

                if os.path.exists("exam_backup.json"):

                    with open(
                        "exam_backup.json",
                        "r",
                        encoding="utf-8"
                    ) as f:

                        restored_exam = json.load(f)

                    exams.update(restored_exam)

                    save_exams(exams)

                    os.remove("exam_backup.json")

                st.success("시험 복원 완료")

                st.rerun()

            except Exception as e:

                st.error(f"복원 실패: {e}")

    # ==================================================
    # 시험 등록 / 수정
    # ==================================================

    with tab2:

        exam_names = ["새 시험 등록"] + list(exams.keys())

        selected_exam = st.selectbox(
            "시험 선택",
            exam_names
        )

        if selected_exam == "새 시험 등록":

            exam_data = {}

            exam_name = st.text_input("시험 이름")

        else:

            exam_data = exams[selected_exam]

            exam_name = st.text_input(
                "시험 이름",
                value=selected_exam
            )

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
                default_data = {"type": "mcq", "answer": raw_data}

            elif isinstance(raw_data, dict):
                default_data = raw_data

            else:
                default_data = {"type": "mcq", "answer": []}

            col1, col2, col3 = st.columns([1,2,1])

            q_type = col1.selectbox(
                f"{q}번 유형",
                ["mcq", "short"],
                index=0 if default_data.get("type","mcq") == "mcq" else 1,
                key=f"type_{q}"
            )

            if q_type == "mcq":
                default_ans = ",".join(default_data.get("answer", []))
            else:
                default_ans = default_data.get("answer","")

            ans_input = col2.text_input(
                f"{q}번 정답",
                value=default_ans,
                key=f"ans_{q}"
            )

            score = col3.number_input(
                f"{q}번 배점",
                value=exam_data.get("scores",{}).get(str(q),1),
                key=f"score_{q}"
            )

            if q_type == "mcq":
                answer_value = [x.strip() for x in ans_input.split(",")] if ans_input else []
            else:
                answer_value = ans_input.strip()

            answers[str(q)] = {"type":q_type,"answer":answer_value}
            scores[str(q)] = score

        st.markdown("### 📂 영역 설정")

        existing_sections = exam_data.get("sections",{})

        default_section_count = len(existing_sections) if existing_sections else 1

        num_sections = st.number_input(
            "영역 개수",
            min_value=1,
            value=default_section_count
        )

        sections = {}

        for i in range(1,int(num_sections)+1):

            default_sec = existing_sections.get(str(i),{})

            sec_name = st.text_input(
                f"{i}번 영역 이름",
                value=default_sec.get("name",""),
                key=f"secname_{i}"
            )

            default_range=""

            if default_sec.get("questions"):
                default_range=",".join(map(str,default_sec["questions"]))

            sec_q = st.text_input(
                f"{i}번 영역 문항 범위 (예: 1-5,7,9)",
                value=default_range,
                key=f"secq_{i}"
            )

            sections[str(i)] = {
                "name":sec_name,
                "questions":parse_question_range(sec_q)
            }

        if st.button("💾 저장"):

            new_data = {
                "num_questions":num_questions,
                "answers":answers,
                "scores":scores,
                "sections":sections,
                "layout":exam_data.get("layout",{}),
                "template_path":exam_data.get("template_path","")
            }

            if selected_exam == "새 시험 등록":

                add_exam(exam_name,new_data)

            else:

                if exam_name != selected_exam:

                    exams[exam_name] = new_data

                    del exams[selected_exam]

                    save_exams(exams)

                else:

                    update_exam(exam_name,new_data)

            st.success("저장 완료")

            st.rerun()
