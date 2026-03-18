import streamlit as st
import os
import cv2
import numpy as np
import shutil
import zipfile
import io
import json
from datetime import datetime
from core.database import load_exams, update_exam, save_exams

TEMPLATE_DIR = "templates"
TRASH_DIR = "trash_templates"
BACKUP_DIR = "template_backups"

os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(TRASH_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def load_image_safe(path):
    if not path or not os.path.exists(path):
        return None
    stream = np.fromfile(path, np.uint8)
    return cv2.imdecode(stream, cv2.IMREAD_COLOR)


def backup_template(path, exam_name):
    if not path or not os.path.exists(path):
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{exam_name}_{timestamp}.png"
    shutil.copy(path, os.path.join(BACKUP_DIR, filename))


def create_exam_backup_file():
    exams = load_exams()
    backup_path = os.path.join(BACKUP_DIR, "exams_backup.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(exams, f, indent=4, ensure_ascii=False)
    return backup_path


def show_template_manager():

    st.header("🧾 템플릿 관리")

    exams = load_exams()

    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    tab1, tab2 = st.tabs(["📚 템플릿 목록", "✏ 템플릿 편집"])

    # ==================================================
    # 📚 템플릿 목록
    # ==================================================

    with tab1:

        for name, exam in exams.items():

            with st.expander(f"📘 {name}"):

                st.write(f"문항 수: {exam.get('num_questions')}")

                if exam.get("template_path"):
                    st.success("템플릿 있음")
                else:
                    st.warning("템플릿 없음")

                col1, col2, col3, col4 = st.columns(4)

                if col1.button("수정", key=f"edit_{name}"):

                    st.session_state["edit_template"] = name
                    st.session_state["template_tab"] = "edit"
                    st.rerun()

                if col2.button("삭제", key=f"delete_{name}"):

                    if exam.get("template_path"):
                        backup_template(exam["template_path"], name)

                        try:
                            shutil.move(
                                exam["template_path"],
                                os.path.join(
                                    TRASH_DIR,
                                    os.path.basename(exam["template_path"])
                                )
                            )
                        except:
                            pass

                    exam["template_path"] = ""
                    exam["layout"] = {}

                    update_exam(name, exam)

                    st.rerun()

                if col3.button("복사", key=f"copy_{name}"):

                    st.session_state["edit_template"] = name
                    st.session_state["template_tab"] = "edit"
                    st.session_state["copy_mode"] = True

                    st.rerun()

                if col4.button("이름 변경", key=f"rename_{name}"):

                    new_name = st.text_input(
                        "새 이름",
                        value=name,
                        key=f"rename_input_{name}"
                    )

                    if st.button("이름 적용", key=f"rename_apply_{name}"):

                        exams[new_name] = exams.pop(name)
                        save_exams(exams)

                        st.success("이름 변경 완료")

                        st.rerun()

        # ----------------------------
        # 템플릿 백업
        # ----------------------------

        st.markdown("---")
        st.subheader("📦 템플릿 백업")

        # 전체 ZIP 백업
        zip_buffer = io.BytesIO()
        exam_backup_file = create_exam_backup_file()

        with zipfile.ZipFile(zip_buffer, "w") as z:

            for root, dirs, files in os.walk(TEMPLATE_DIR):
                for file in files:

                    file_path = os.path.join(root, file)

                    z.write(
                        file_path,
                        arcname=os.path.join("templates", file)
                    )

            z.write(
                exam_backup_file,
                arcname="exams_backup.json"
            )

        st.download_button(
            "📥 전체 백업 ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name="omr_template_backup.zip",
            mime="application/zip"
        )

        # 선택 다운로드
        template_files = os.listdir(TEMPLATE_DIR)

        if template_files:

            selected_template = st.selectbox(
                "다운로드할 템플릿 선택",
                template_files
            )

            template_path = os.path.join(
                TEMPLATE_DIR,
                selected_template
            )

            with open(template_path, "rb") as f:

                template_bytes = f.read()

            st.download_button(
                "📥 선택 템플릿 다운로드",
                data=template_bytes,
                file_name=selected_template,
                mime="image/png"
            )

    # ==================================================
    # ✏ 템플릿 편집
    # ==================================================

    with tab2:

        edit_name = st.session_state.get("edit_template")

        if not edit_name:
            st.info("목록에서 수정 버튼을 누르세요.")
            return

        exam = exams[edit_name]

        st.subheader(f"✏ 템플릿 편집: {edit_name}")

        # ----------------------------
        # 템플릿 복사
        # ----------------------------

        st.subheader("📋 템플릿 복사")

        other_exams = [e for e in exams.keys() if e != edit_name]

        if other_exams:

            source_exam = st.selectbox(
                "가져올 템플릿",
                other_exams
            )

            if st.button("이 템플릿 적용"):

                src = exams[source_exam]

                exam["layout"] = src.get("layout", {})
                exam["template_path"] = src.get("template_path", "")

                update_exam(edit_name, exam)

                st.success("템플릿 적용 완료")

                st.rerun()

        # ----------------------------
        # 템플릿 업로드
        # ----------------------------

        st.subheader("📤 템플릿 업로드")

        uploaded = st.file_uploader(
            "빈 OMR 이미지",
            type=["png", "jpg", "jpeg"]
        )

        if uploaded and st.button("템플릿 저장"):

            if exam.get("template_path"):

                backup_template(
                    exam["template_path"],
                    edit_name
                )

            save_path = os.path.join(
                TEMPLATE_DIR,
                f"{edit_name}.png"
            )

            with open(save_path, "wb") as f:

                f.write(uploaded.read())

            exam["template_path"] = save_path

            update_exam(edit_name, exam)

            st.success("저장 완료")

            st.rerun()

        img = load_image_safe(exam.get("template_path"))

        if img is not None:

            st.image(img, channels="BGR")

        # ----------------------------
        # 좌표 설정
        # ----------------------------

        st.subheader("📐 좌표 설정")

        layout = exam.get("layout", {})

        questions_per_column = st.number_input(
            "한 열당 문항 수",
            min_value=1,
            value=layout.get("questions_per_column", 10)
        )

        num_columns = st.number_input(
            "열 개수",
            min_value=1,
            value=layout.get("num_columns", 1)
        )

        num_columns = int(num_columns)

        columns_x = {}

        for c in range(1, num_columns + 1):

            default = layout.get(
                "columns_x",
                {}
            ).get(str(c), [0,0,0,0,0,0])

            x_input = st.text_input(
                f"{c}열 X 좌표 6개",
                value=",".join(map(str, default))
            )

            try:
                columns_x[str(c)] = list(
                    map(int, x_input.split(","))
                )
            except:
                columns_x[str(c)] = default

        y_ranges = {}

        for q in range(1, exam["num_questions"] + 1):

            default_y = layout.get(
                "y_ranges",
                {}
            ).get(str(q), [0,0])

            y_input = st.text_input(
                f"{q}번 Y 범위",
                value=",".join(map(str, default_y))
            )

            try:
                y_ranges[str(q)] = list(
                    map(int, y_input.split(","))
                )
            except:
                y_ranges[str(q)] = default_y

        if st.button("💾 저장하기"):

            exam["layout"] = {
                "questions_per_column": questions_per_column,
                "columns_x": columns_x,
                "y_ranges": y_ranges,
                "num_columns": num_columns
            }

            update_exam(edit_name, exam)

            st.success("저장 완료")

            st.rerun()
