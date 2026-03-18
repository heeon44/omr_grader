def grade_student(row, exam):

    answers = exam.get("answers", {})
    scores = exam.get("scores", {})
    sections = exam.get("sections", {})

    total_score = 0
    wrong_questions = []

    for q in range(1, exam["num_questions"] + 1):

        q_data = answers.get(str(q), {})
        q_type = q_data.get("type", "mcq")
        correct = q_data.get("answer")

        student_answer = row.get(f"{q}번_학생답", "")
        student_answer = student_answer.strip() if student_answer else ""

        # -------------------------------------------------
        # 객관식 채점
        # -------------------------------------------------
        if q_type == "mcq":

            student_set = set(student_answer.split(",")) if student_answer else set()

            # OR 정답 (예: 1 or 2)
            if isinstance(correct, str) and "or" in correct:

                correct_options = {
                    x.strip() for x in correct.split("or")
                }

                if student_set & correct_options:

                    row[f"{q}번"] = "O"
                    total_score += scores.get(str(q), 1)

                else:

                    row[f"{q}번"] = "X"
                    wrong_questions.append(str(q))

            # AND 정답 (예: 1,2)
            else:

                if isinstance(correct, str):
                    correct_set = {x.strip() for x in correct.split(",")}
                else:
                    correct_set = set(correct)

                if student_set == correct_set:

                    row[f"{q}번"] = "O"
                    total_score += scores.get(str(q), 1)

                else:

                    row[f"{q}번"] = "X"
                    wrong_questions.append(str(q))

        # -------------------------------------------------
        # 단답형 (자동 채점 안 함)
        # -------------------------------------------------
        elif q_type == "short":

            row[f"{q}번"] = student_answer

        else:

            row[f"{q}번"] = ""

        # 학생답 원본 제거
        if f"{q}번_학생답" in row:
            del row[f"{q}번_학생답"]

    # -------------------------------------------------
    # 영역 점수 계산 (객관식만)
    # -------------------------------------------------
    for sec_id, sec in sections.items():

        sec_name = sec.get("name", f"영역{sec_id}")
        sec_questions = sec.get("questions", [])

        sec_score = 0

        for q in sec_questions:

            if q > exam["num_questions"]:
                continue

            q_data = answers.get(str(q), {})
            q_type = q_data.get("type", "mcq")

            if q_type == "mcq":

                if row.get(f"{q}번") == "O":
                    sec_score += scores.get(str(q), 1)

        row[f"{sec_name}_총점"] = sec_score

    # -------------------------------------------------
    # 총점 + 틀린 문항
    # -------------------------------------------------

    row["총점"] = total_score
    row["틀린 문항"] = ",".join(wrong_questions)

    return row
