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
    q_x_range = layout.get("question_x_ranges", {})

    for col_id, x_list in columns_x.items():
        for q in range(1, exam["num_questions"] + 1):
            if str(q) not in y_ranges:
                continue
            y1, y2 = y_ranges[str(q)]
            for i in range(5):
                if i + 1 >= len(x_list):
                    continue
                cv2.rectangle(debug_img,(x_list[i], y1),(x_list[i+1], y2),(0,255,0),1)

   for col_id, q_range in q_x_ranges.items():

      if not q_range:
            continue

        qx1, qx2 = q_range

        for q in range(1, exam["num_questions"] + 1):

            # 이 문항이 몇 열인지 계산
            col_index = ((q - 1) // layout.get("questions_per_column", 1)) + 1

            if str(col_index) != col_id:
                continue

            if str(q) not in y_ranges:
                continue

            y1, y2 = y_ranges[str(q)]
            cv2.rectangle(debug_img,(qx1,y1),(qx2,y2),(0,0,255),2)

        m1 = layout.get("marker1")
        m2 = layout.get("marker2")

      if m1:
         cv2.rectangle(debug_img,(m1["x1"],m1["y1"]),(m1["x2"],m1["y2"]),(255,0,0),2)
      if m2:
         cv2.rectangle(debug_img,(m2["x1"],m2["y1"]),(m2["x2"],m2["y2"]),(0,255,255),2)

    return debug_img


def show_template_manager():

    st.header("🧾 템플릿 관리")

    exams = load_exams()
    if not exams:
        st.warning("시험 먼저 등록하세요.")
        return

    tab1, tab2 = st.tabs(["📚 템플릿 목록", "✏ 템플릿 편집"])

    # ==================================================
    # 📚 목록 탭
    # ==================================================
    with tab1:

        for name, exam in exams.items():

            with st.expander(f"📘 {name}"):

                st.write(f"문항 수: {exam.get('num_questions')}")

                col1, col2 = st.columns(2)

                if col1.button("편집", key=f"edit_{name}"):
                    st.session_state["edit_template"] = name
                    st.rerun()

                if col2.button("삭제", key=f"delete_{name}"):

                    if exam.get("template_path"):
                        backup_template(exam["template_path"], name)
                        try:
                            shutil.move(
                                exam["template_path"],
                                os.path.join(TRASH_DIR,
                                os.path.basename(exam["template_path"]))
                            )
                        except:
                            pass

                    exam["template_path"] = ""
                    exam["layout"] = {}
                    update_exam(name, exam)
                    st.rerun()

    # ==================================================
    # ✏ 편집 탭
    # ==================================================
    with tab2:

        edit_name = st.session_state.get("edit_template")

        if not edit_name:
            st.info("목록에서 편집할 시험을 선택하세요.")
            return

        exam = exams[edit_name]
        st.subheader(f"✏ 템플릿 편집: {edit_name}")

        # ----------------------------
        # 템플릿 복사
        # ----------------------------
        st.subheader("📋 템플릿 복사")

        other_exams = [e for e in exams.keys() if e != edit_name]

        if other_exams:
            target_exam = st.selectbox("복사 대상 시험", other_exams)

            if st.button("이 시험 템플릿 복사"):
                target_data = exams[target_exam]
                target_data["layout"] = exam.get("layout", {})
                target_data["template_path"] = exam.get("template_path", "")
                update_exam(target_exam, target_data)
                st.success("복사 완료")

        # ----------------------------
        # 삭제 / 복구
        # ----------------------------
        st.subheader("❌ 템플릿 삭제")

        if exam.get("template_path"):
            if st.button("이 시험 템플릿 삭제"):
                backup_template(exam["template_path"], edit_name)
                try:
                    shutil.move(
                        exam["template_path"],
                        os.path.join(TRASH_DIR,
                        os.path.basename(exam["template_path"]))
                    )
                except:
                    pass
                exam["template_path"] = ""
                update_exam(edit_name, exam)
                st.success("휴지통 이동 완료")
                st.rerun()

        st.subheader("♻ 템플릿 복구")

        trash_files = os.listdir(TRASH_DIR)
        if trash_files:
            restore_file = st.selectbox("복구할 파일", trash_files)
            if st.button("선택 파일 복구"):
                restore_path = os.path.join(TRASH_DIR, restore_file)
                new_path = os.path.join(TEMPLATE_DIR, restore_file)
                shutil.move(restore_path, new_path)
                exam["template_path"] = new_path
                update_exam(edit_name, exam)
                st.success("복구 완료")
                st.rerun()

        # ----------------------------
        # 업로드
        # ----------------------------
        st.subheader("📤 템플릿 업로드")

        uploaded = st.file_uploader("빈 OMR 이미지", type=["png","jpg","jpeg"])

        if uploaded and st.button("템플릿 저장"):
            if exam.get("template_path"):
                backup_template(exam["template_path"], edit_name)

            save_path = os.path.join(TEMPLATE_DIR, f"{edit_name}.png")
            with open(save_path,"wb") as f:
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
            value=len(layout.get("columns_x", {})) or 1
        )

        columns_x = {}
        for c in range(1, int(num_columns)+1):
            default = layout.get("columns_x",{}).get(str(c), [0,0,0,0,0,0])
            x_input = st.text_input(
                f"{c}열 X 좌표 6개",
                value=",".join(map(str, default)),
                key=f"{edit_name}_x_{c}"
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
                value=",".join(map(str, default_y)),
                key=f"{edit_name}_y_{q}"
            )
            try:
                y_ranges[str(q)] = list(map(int,y_input.split(",")))
            except:
                y_ranges[str(q)] = default_y

        question_x_ranges = {}

        for c in range(1, int(num_columns) + 1):

            default_qx = layout.get("question_x_ranges", {}).get(str(c), [0,0])

            qx_input = st.text_input(
                f"{c}열 문항 번호 X 범위 (x1,x2)",
                value=",".join(map(str, default_qx)),
                key=f"{edit_name}_qx_{c}"
            )

            try:
                question_x_ranges[str(c)] = list(map(int, qx_input.split(",")))
            except:
                question_x_ranges[str(c)] = default_qx

        st.markdown("### 🟦 기준 마커 1 (x1,y1,x2,y2)")
        m1 = layout.get("marker1", {})
        m1_x1 = st.number_input("마커1 x1",
                                value=m1.get("x1",0),
                                key=f"{edit_name}_m1_x1")

        m1_y1 = st.number_input("마커1 y1",
                                value=m1.get("y1",0),
                                key=f"{edit_name}_m1_y1")

        m1_x2 = st.number_input("마커1 x2",
                                value=m1.get("x2",50),
                                key=f"{edit_name}_m1_x2")

        m1_y2 = st.number_input("마커1 y2",
                                value=m1.get("y2",50),
                                key=f"{edit_name}_m1_y2")

        st.markdown("### 🟨 기준 마커 2 (x1,y1,x2,y2)")
        m2 = layout.get("marker2", {})
        m2_x1 = st.number_input("마커2 x1",
                                value=m2.get("x1",0),
                                key=f"{edit_name}_m2_x1")

        m2_y1 = st.number_input("마커2 y1",
                                value=m2.get("y1",0),
                                key=f"{edit_name}_m2_y1")

        m2_x2 = st.number_input("마커2 x2",
                                value=m2.get("x2",50),
                                key=f"{edit_name}_m2_x2")

        m2_y2 = st.number_input("마커2 y2",
                                value=m2.get("y2",50),
                                key=f"{edit_name}_m2_y2")

        if st.button("💾 저장하기"):

            exam["layout"] = {
                "questions_per_column":questions_per_column,
                "columns_x":columns_x,
                "y_ranges":y_ranges,
                "question_x_ranges":question_x_ranges,
                "marker1":{"x1":m1_x1,"y1":m1_y1,"x2":m1_x2,"y2":m1_y2},
                "marker2":{"x1":m2_x1,"y1":m2_y1,"x2":m2_x2,"y2":m2_y2}
            }

            update_exam(edit_name, exam)

            # 🔥 해당 시험 위젯 state 전부 정리
            for key in list(st.session_state.keys()):
                if key.startswith(f"{edit_name}_"):
                    del st.session_state[key]

            st.success("저장 완료")
            st.rerun()

        # ----------------------------
        # 좌표 시각화
        # ----------------------------
        if img is not None:
            st.subheader("📊 좌표 시각화")
            debug_img = draw_layout(img, exam.get("layout", {}), exam)
            st.image(debug_img, channels="BGR")

        # ==================================================
        # 전체 백업 / 복원
        # ==================================================
        st.markdown("---")
        st.subheader("📦 템플릿 전체 백업 / 복원")

        zip_buffer = io.BytesIO()
        exam_backup_file = create_exam_backup_file()

        with zipfile.ZipFile(zip_buffer, "w") as z:

            # 템플릿 이미지 전체 백업
            for root, dirs, files in os.walk(TEMPLATE_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    z.write(file_path,
                            arcname=os.path.join("templates", file))

            # 시험 JSON 백업
            z.write(exam_backup_file,
                    arcname="exams_backup.json")

        st.download_button(
            "📥 전체 백업 ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name="omr_full_backup.zip",
            mime="application/zip"
        )

        # ----------------------------
        # ZIP 업로드 복원
        # ----------------------------
        uploaded_zip = st.file_uploader(
            "📤 ZIP 업로드로 전체 복원",
            type=["zip"]
        )

        if uploaded_zip is not None:
            try:
                with zipfile.ZipFile(uploaded_zip, "r") as z:
                    z.extractall(".")

                backup_json_path = "exams_backup.json"

                if os.path.exists(backup_json_path):

                    with open(backup_json_path,
                              "r",
                              encoding="utf-8") as f:
                        restored_exams = json.load(f)

                    save_exams(restored_exams)

                    # 🔥 복원 후 현재 편집 시험 즉시 반영
                    exams = load_exams()
                    if edit_name in exams:
                        exam = exams[edit_name]

                    os.remove(backup_json_path)

                st.success("🔥 템플릿 + 좌표 + 시험정보 전체 복원 완료")
                st.rerun()

            except Exception as e:
                st.error(f"복원 실패: {e}")


