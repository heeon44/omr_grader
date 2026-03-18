import streamlit as st

from views.exam_manager import show_exam_manager
from views.template_manager import show_template_manager
from views.debug_page import show_debug_page
from views.exam_analysis_page import show_exam_analysis_page


# -----------------------------------
# 🔐 페이지 기본 설정 (최상단 1번만!)
# -----------------------------------
st.set_page_config(layout="wide")


# -----------------------------------
# 🔐 비밀번호 설정
# -----------------------------------
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
USER_PASSWORD = st.secrets["USER_PASSWORD"]


# -----------------------------------
# 🔐 로그인 함수
# -----------------------------------
def login():

    if "role" not in st.session_state:
        st.session_state.role = None

    if st.session_state.role:
        return True

    st.title("🔐 OMR 채점 프로그램 로그인")

    password = st.text_input("비밀번호 입력", type="password")

    if st.button("로그인"):

        if password == ADMIN_PASSWORD:
            st.session_state.role = "admin"
            st.rerun()

        elif password == USER_PASSWORD:
            st.session_state.role = "갈무리"
            st.rerun()

        else:
            st.error("비밀번호가 틀렸습니다.")

    return False


# 로그인 안 되어 있으면 중단
if not login():
    st.stop()


# -----------------------------------
# 메인 화면
# -----------------------------------
st.title("📚 OMR 자동 채점 프로그램")


# -----------------------------------
# 사이드바 정보
# -----------------------------------
st.sidebar.markdown(f"### 👤 현재 권한: {st.session_state.role}")

if st.sidebar.button("로그아웃"):
    st.session_state.role = None
    st.rerun()


# -----------------------------------
# 권한별 메뉴 구성
# -----------------------------------
if st.session_state.role == "admin":

    menu = st.sidebar.radio(
        "📂 메뉴",
        [
            "시험 관리",
            "템플릿 관리",
            "답안 채점(PDF)",
            "시험 분석"
        ]
    )

elif st.session_state.role == "갈무리":

    menu = st.sidebar.radio(
        "📂 메뉴",
        [
            "답안 채점(PDF)",
            "시험 분석"
        ]
    )


# -----------------------------------
# 메뉴 실행 + 관리자 보호
# -----------------------------------
if menu == "시험 관리":

    if st.session_state.role != "admin":
        st.error("❌ 관리자만 접근 가능합니다.")
        st.stop()

    show_exam_manager()


elif menu == "템플릿 관리":

    if st.session_state.role != "admin":
        st.error("❌ 관리자만 접근 가능합니다.")
        st.stop()

    show_template_manager()


elif menu == "답안 채점(PDF)":
    show_debug_page()


elif menu == "시험 분석":
    show_exam_analysis_page()
