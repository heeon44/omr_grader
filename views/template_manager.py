import streamlit as st
import os
import cv2
import numpy as np
import shutil
import zipfile
import io
import json
import copy
from datetime import datetime
from core.database import load_exams, update_exam

TEMPLATE_DIR = "templates"
TRASH_DIR = "trash_templates"
BACKUP_DIR = "template_backups"
DB_PATH = "data/exams.json"

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
    backup_path = os.path.join(BACKUP_DIR, filename)
    shutil.copy(path, backup_path)


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
    q_x_range = layout.get("question_x_range")

    for col_id, x_list in columns_x.items():
        for q in range(1, exam["num_questions"] + 1):
            if str(q) not in y_ranges:
                continue
            y1, y2 = y_ranges[str(q)]
            for i in range(5):
                if i + 1 >= len(x_list):
                    continue
                cv2.rectangle(debug_img,
                              (x_list[i], y1),
                              (x_list[i+1], y2),
                              (0,255,0), 1)

    if q_x_range:
        qx1, qx2 = q_x_range
        for q in range(1, exam["num_questions"] + 1):
            if str(q) not in y_ranges:
                continue
            y1, y2 = y_ranges[str(q)]
            cv2.rectangle(debug_img,
                          (qx1, y1),
                          (qx2, y2),
                          (0,0,255), 2)

    return debug_img


def show_template_manager():

    st.header("🧾 템플릿 관리")

    exams = load_exams()
    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    exam_options = ["시험을 선택하세요"] + list(exams.keys())

    if "exam_selector" not in st.session_state:
        st.session_state.exam_selector = exam_options[0]

    exam_name = st.selectbox(
        "시험 선택",
        exam_options,
        key="exam_selector"
    )

    if exam_name == "시험을 선택하세요":
        st.info("시험을 선택하면 템플릿 설정 화면이 열립니다.")
        return

    exam = exams[exam_name]

    # -------------------------------------------------
    # ✏ 시험 이름 변경
    # -------------------------------------------------
    st.subheader("✏ 시험 이름 변경")

    new_name = st.text_input("새 시험 이름", value=exam_name)

    if st.button("시험 이름 변경"):
        if new_name in exams:
            st.error("이미 존재하는 시험 이름입니다.")
        else:
            exams[new_name] = exams.pop(exam_name)

            # 템플릿 파일 이름도 변경
            old_path = exam.get("template_path")
            if old_path and os.path.exists(old_path):
                new_path = os.path.join(TEMPLATE_DIR, f"{new_name}.png")
                os.rename(old_path, new_path)
                exams[new_name]["template_path"] = new_path

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(exams, f, ensure_ascii=False, indent=2)

            st.success("시험 이름 변경 완료")
            st.session_state.exam_selector = new_name
            st.rerun()

    # -------------------------------------------------
    # 📋 템플릿 복사 (덮어쓰기 방식)
    # -------------------------------------------------
    st.subheader("📋 템플릿 복사")

    other_exams = [e for e in exams.keys() if e != exam_name]

    if other_exams:
        source_exam = st.selectbox("복사할 시험 선택", other_exams)

        if st.button("이 시험 템플릿 복사"):

            source_data = copy.deepcopy(exams[source_exam])

            # 이미지 파일 복사
            src_path = source_data.get("template_path")
            if src_path and os.path.exists(src_path):
                new_path = os.path.join(TEMPLATE_DIR, f"{exam_name}.png")
                shutil.copy(src_path, new_path)
                source_data["template_path"] = new_path

            update_exam(exam_name, source_data)

            st.success("템플릿 + 좌표 복사 완료")
            st.rerun()

    # -------------------------------------------------
    # 삭제
    # -------------------------------------------------
    st.subheader("❌ 템플릿 삭제")

    if exam.get("template_path"):

        if st.button("이 시험 템플릿 삭제"):

            backup_template(exam["template_path"], exam_name)

            filename = os.path.basename(exam["template_path"])
            trash_path = os.path.join(TRASH_DIR, filename)

            try:
                shutil.move(exam["template_path"], trash_path)
            except:
                pass

            exam["template_path"] = ""
            update_exam(exam_name, exam)

            st.success("휴지통 이동 완료")
            st.rerun()

    # -------------------------------------------------
    # 업로드
    # -------------------------------------------------
    st.subheader("📤 템플릿 업로드")

    uploaded = st.file_uploader("빈 OMR 이미지",
                                type=["png","jpg","jpeg"])

    if uploaded and st.button("템플릿 저장"):

        if exam.get("template_path"):
            backup_template(exam["template_path"], exam_name)

        save_path = os.path.join(TEMPLATE_DIR, f"{exam_name}.png")

        with open(save_path,"wb") as f:
            f.write(uploaded.read())

        exam["template_path"] = save_path
        update_exam(exam_name, exam)

        st.success("저장 완료")
        st.rerun()

    # -------------------------------------------------
    # 이미지 표시
    # -------------------------------------------------
    template_path = exam.get("template_path")
    img = load_image_safe(template_path)

    if img is not None:
        st.image(img, channels="BGR")

    # -------------------------------------------------
    # 좌표 설정
    # -------------------------------------------------
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
        value=len(layout.get("columns_x", {})) or 1
    )

    columns_x = {}

    for c in range(1, int(num_columns)+1):

        default = layout.get("columns_x",{}).get(str(c),
                                                 [0,0,0,0,0,0])

        x_input = st.text_input(
            f"{c}열 X 좌표 6개",
            value=",".join(map(str, default))
        )

        try:
            columns_x[str(c)] = list(map(int,x_input.split(",")))
        except:
            columns_x[str(c)] = default

    y_ranges = {}

    for q in range(1, exam["num_questions"]+1):

        default_y = layout.get("y_ranges",{}).get(str(q),[0,0])

        y_input = st.text_input(
            f"{q}번 Y 범위",
            value=",".join(map(str, default_y))
        )

        try:
            y_ranges[str(q)] = list(map(int,y_input.split(",")))
        except:
            y_ranges[str(q)] = default_y

    default_qx = layout.get("question_x_range",[0,0])

    qx_input = st.text_input(
        "문항 공통 X 범위 (x1,x2)",
        value=",".join(map(str, default_qx))
    )

    try:
        question_x_range = list(map(int,qx_input.split(",")))
    except:
        question_x_range = default_qx

    if st.button("좌표 저장"):

        exam["layout"] = {
            "questions_per_column":questions_per_column,
            "columns_x":columns_x,
            "y_ranges":y_ranges,
            "question_x_range":question_x_range
        }

        update_exam(exam_name,exam)

        st.success("좌표 저장 완료")
        st.rerun()

    if img is not None:
        st.subheader("📊 좌표 시각화")
        debug_img = draw_layout(img,exam.get("layout",{}),exam)
        st.image(debug_img,channels="BGR")

    # -------------------------------------------------
    # 전체 백업 / 복원
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("📦 템플릿 전체 백업 / 복원")

    zip_buffer = io.BytesIO()
    exam_backup_file = create_exam_backup_file()

    with zipfile.ZipFile(zip_buffer, "w") as z:

        for root, dirs, files in os.walk(TEMPLATE_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                z.write(file_path,
                        arcname=os.path.join("templates", file))

        z.write(exam_backup_file,
                arcname="exams_backup.json")

    st.download_button(
        "📥 전체 백업 ZIP 다운로드",
        data=zip_buffer.getvalue(),
        file_name="omr_full_backup.zip",
        mime="application/zip"
    )
