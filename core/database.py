import json
import os

DB_PATH = "data/exams.json"


def _ensure_file():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)


def load_exams():
    _ensure_file()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_exams(exams):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(exams, f, ensure_ascii=False, indent=2)


def add_exam(name, exam_data):
    exams = load_exams()
    exams[name] = exam_data
    save_exams(exams)


def update_exam(name, exam_data):
    exams = load_exams()
    exams[name] = exam_data
    save_exams(exams)


def delete_exam(name):
    exams = load_exams()
    if name in exams:
        del exams[name]
        save_exams(exams)