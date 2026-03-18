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


def draw_layout(image, layout, exam):

    debug_img = image.copy()

    columns_x = layout.get("columns_x", {})
    y_ranges = layout.get("y_ranges", {})
    q_x_ranges = layout.get("question_x_ranges", {})

    for col_id, x_list in columns_x.items():

        for q in range(1, exam["num_questions"] + 1):

            if str(q) not in y_ranges:
                continue

            y1, y2 = y_ranges[str(q)]

            for i in range(5):

                if i + 1 >= len(x_list):
                    continue

                cv2.rectangle(
                    debug_img,
                    (x_list[i], y1),
                    (x_list[i+1], y2),
                    (0,255,0),
                    1
                )

    for col_id, q_range in q_x_ranges.items():

        if not q_range:
            continue

        qx1, qx2 = q_range

        for q in range(1, exam["num_questions"] + 1):

            col_index = ((q - 1) //
                         layout.get("questions_per_column", 1)) + 1

            if str(col_index) != col_id:
                continue

            if str(q) not in y_ranges:
                continue

            y1, y2 = y_ranges[str(q)]

            cv2.rectangle(
                debug_img,
                (qx1, y1),
                (qx2, y2),
                (0,0,255),
                2
            )

    m1 = layout.get("marker1")
    m2 = layout.get("marker2")

    if m1:

        cv2.rectangle(
            debug_img,
            (m1["x1"], m1["y1"]),
            (m1["x2"], m1["y2"]),
            (255,0,0),
            2
        )

    if m2:

        cv2.rectangle(
            debug_img,
            (m2["x1"], m2["y1"]),
            (m2["x2"], m2["y2"]),
            (0,255,255),
            2
        )

    return debug_img


def show_template_manager():

    st.header("🧾 템플릿 관리")

    exams = load_exams()

    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    tab1, tab2 = st.tabs(["📚 템플릿 목록", "✏ 템플릿 편집"])

    # ==================================================
    # 템플릿 목록
    # ==================================================

    with tab1:

        for name, exam in exams.items():

            with st.expander(f"📘 {name}"):

                st.write(f"문항 수: {exam.get('num_questions')}")

                if exam.get("template_path"):
                    st.success("템플릿 있음")
                else:
                    st.warning("템플릿 없음")

                col1, col2, col3 = st.columns(3)

                if col1.button("삭제", key=f"delete_{name}"):

                    if exam.get("template_path"):

                        backup_template(
                            exam["template_path"],
                            name
                        )

                        try:
                            shutil.move(
                                exam["template_path"],
                                os.path.join(
                                    TRASH_DIR,
                                    os.path.basename(
                                        exam["template_path"]
                                    )
                                )
                            )
                        except:
                            pass

                    exam["template_path"] = ""
                    exam["layout"] = {}

                    update_exam(name, exam)

                    st.rerun()

                if col2.button("복사", key=f"copy_{name}"):

                    st.session_state["copy_source"] = name

                    st.success("템플릿 편집에서 붙여넣기 가능")

                if col3.button("이름 변경", key=f"rename_{name}"):

                    new_name = st.text_input(
                        "새 이름",
                        value=name,
                        key=f"rename_input_{name}"
                    )

                    if st.button("적용", key=f"rename_apply_{name}"):

                        exams[new_name] = exams.pop(name)

                        save_exams(exams)

                        st.success("이름 변경 완료")

                        st.rerun()

        # 백업

        st.markdown("---")
        st.subheader("📦 템플릿 백업")

        # ----------------------------
        # 전체 백업 ZIP 다운로드
        # ----------------------------

        zip_buffer = io.BytesIO()
        exam_backup_file = create_exam_backup_file()

        with zipfile.ZipFile(zip_buffer, "w") as z:

            # 템플릿 이미지 전체
            for root, dirs, files in os.walk(TEMPLATE_DIR):

                for file in files:

                    file_path = os.path.join(root, file)

                    z.write(
                        file_path,
                        arcname=os.path.join(
                            "templates",
                            file
                        )
                    )

            # 시험 JSON
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

        # ----------------------------
        # 선택 템플릿 ZIP 다운로드
        # ----------------------------

        st.markdown("### 📂 선택 템플릿 백업")

        exam_names = list(exams.keys())

        selected_exam = st.selectbox(
            "백업할 시험 선택",
            exam_names
        )

        if selected_exam:

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w") as z:

                exam = exams[selected_exam]

                # 템플릿 이미지
                if exam.get("template_path") and os.path.exists(exam["template_path"]):

                    z.write(
                        exam["template_path"],
                        arcname=os.path.join(
                            "templates",
                            os.path.basename(exam["template_path"])
                        )
                    )

                # 시험 JSON (좌표 포함)
                temp_json = {selected_exam: exam}

                json_bytes = json.dumps(
                    temp_json,
                    ensure_ascii=False,
                    indent=2
                ).encode("utf-8")

                z.writestr("exam_template.json", json_bytes)

            st.download_button(
                "📥 선택 템플릿 ZIP 다운로드",
                data=zip_buffer.getvalue(),
                file_name=f"{selected_exam}_template_backup.zip",
                mime="application/zip"
            )

        # ----------------------------
        # ZIP 업로드 복원
        # ----------------------------

        st.markdown("### 📤 템플릿 ZIP 복원")

        uploaded_zip = st.file_uploader(
            "템플릿 백업 ZIP 업로드",
            type=["zip"]
        )

        if uploaded_zip is not None:

            try:

                with zipfile.ZipFile(uploaded_zip, "r") as z:
                    z.extractall(".")

                if os.path.exists("exam_template.json"):

                    with open(
                        "exam_template.json",
                        "r",
                        encoding="utf-8"
                    ) as f:

                        restored_exam = json.load(f)

                    exams.update(restored_exam)

                    save_exams(exams)

                    os.remove("exam_template.json")

                st.success("템플릿 + 좌표 복원 완료")

                st.rerun()

            except Exception as e:

                st.error(f"복원 실패: {e}")

    
    # ==================================================
    # 템플릿 편집
    # ==================================================

    with tab2:

        exam_names = list(exams.keys())

        edit_name = st.selectbox(
            "편집할 시험 선택",
            exam_names
        )

        exam = exams[edit_name]

        st.subheader(f"✏ 템플릿 편집: {edit_name}")

        # 템플릿 복사

        if "copy_source" in st.session_state:

            src_name = st.session_state["copy_source"]

            if st.button(f"{src_name} 템플릿 붙여넣기"):

                src = exams[src_name]

                exam["layout"] = src.get("layout", {})
                exam["template_path"] = src.get(
                    "template_path",
                    ""
                )

                update_exam(edit_name, exam)

                st.success("복사 완료")

                del st.session_state["copy_source"]

                st.rerun()

        # 템플릿 업로드

        st.subheader("📤 템플릿 업로드")

        uploaded = st.file_uploader(
            "빈 OMR 이미지",
            type=["png","jpg","jpeg"]
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

            with open(save_path,"wb") as f:

                f.write(uploaded.read())

            exam["template_path"] = save_path

            update_exam(edit_name, exam)

            st.success("저장 완료")

            st.rerun()

        img = load_image_safe(
            exam.get("template_path")
        )

        if img is not None:

            st.image(img, channels="BGR")

        # 좌표 설정

        st.subheader("📐 좌표 설정")

        layout = exam.get("layout", {})

        questions_per_column = st.number_input(
            "한 열당 문항 수",
            min_value=1,
            value=layout.get(
                "questions_per_column",
                10
            )
        )

        num_columns = st.number_input(
            "열 개수",
            min_value=1,
            value=layout.get(
                "num_columns",
                1
            )
        )

        num_columns = int(num_columns)

        columns_x = {}

        for c in range(1, num_columns+1):

            default = layout.get(
                "columns_x",
                {}
            ).get(
                str(c),
                [0,0,0,0,0,0]
            )

            x_input = st.text_input(
                f"{c}열 X 좌표 6개",
                value=",".join(
                    map(str, default)
                )
            )

            try:
                columns_x[str(c)] = list(
                    map(int,
                    x_input.split(","))
                )
            except:
                columns_x[str(c)] = default

        y_ranges = {}

        for q in range(
            1,
            exam["num_questions"]+1
        ):

            default_y = layout.get(
                "y_ranges",
                {}
            ).get(str(q),[0,0])

            y_input = st.text_input(
                f"{q}번 Y 범위",
                value=",".join(
                    map(str, default_y)
                )
            )

            try:
                y_ranges[str(q)] = list(
                    map(int,
                    y_input.split(","))
                )
            except:
                y_ranges[str(q)] = default_y

        question_x_ranges = {}

        for c in range(
            1,
            num_columns+1
        ):

            default_qx = layout.get(
                "question_x_ranges",
                {}
            ).get(str(c),[0,0])

            qx_input = st.text_input(
                f"{c}열 문항 번호 X 범위",
                value=",".join(
                    map(str, default_qx)
                )
            )

            try:
                question_x_ranges[str(c)] = list(
                    map(int,
                    qx_input.split(","))
                )
            except:
                question_x_ranges[str(c)] = default_qx

        st.markdown("### 🟦 기준 마커 1")

        m1 = layout.get("marker1",{})

        m1_x1 = st.number_input(
            "x1",
            value=m1.get("x1",0)
        )

        m1_y1 = st.number_input(
            "y1",
            value=m1.get("y1",0)
        )

        m1_x2 = st.number_input(
            "x2",
            value=m1.get("x2",50)
        )

        m1_y2 = st.number_input(
            "y2",
            value=m1.get("y2",50)
        )

        st.markdown("### 🟨 기준 마커 2")

        m2 = layout.get("marker2",{})

        m2_x1 = st.number_input(
            "x1 ",
            value=m2.get("x1",0)
        )

        m2_y1 = st.number_input(
            "y1 ",
            value=m2.get("y1",0)
        )

        m2_x2 = st.number_input(
            "x2 ",
            value=m2.get("x2",50)
        )

        m2_y2 = st.number_input(
            "y2 ",
            value=m2.get("y2",50)
        )

        if st.button("💾 저장"):

            exam["layout"] = {

                "questions_per_column":
                    questions_per_column,

                "columns_x":
                    columns_x,

                "y_ranges":
                    y_ranges,

                "num_columns":
                    num_columns,

                "question_x_ranges":
                    question_x_ranges,

                "marker1":{
                    "x1":m1_x1,
                    "y1":m1_y1,
                    "x2":m1_x2,
                    "y2":m1_y2
                },

                "marker2":{
                    "x1":m2_x1,
                    "y1":m2_y1,
                    "x2":m2_x2,
                    "y2":m2_y2
                }
            }

            update_exam(edit_name, exam)

            st.success("저장 완료")

            st.rerun()

        if img is not None:

            st.subheader("📊 좌표 시각화")

            debug_img = draw_layout(
                img,
                exam.get("layout",{}),
                exam
            )

            st.image(
                debug_img,
                channels="BGR"
            )
