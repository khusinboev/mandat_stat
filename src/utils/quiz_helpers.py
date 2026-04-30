from config import conn, cursor


VALID_SUBJECTS = {"math", "literature", "history"}


def insert_result(user_id: int, subject: str, number: int) -> None:
    subject = subject.lower().strip()
    if subject not in VALID_SUBJECTS:
        raise ValueError("Noto'g'ri fan nomi")

    query = f"""
        INSERT INTO public.results (user_id, {subject}, number)
        VALUES (%s, TRUE, %s)
    """
    cursor.execute(query, (user_id, number))
    conn.commit()


def get_last_5_results(user_id: int, subject: str):
    subject = subject.lower().strip()
    if subject not in VALID_SUBJECTS:
        raise ValueError("Noto'g'ri fan nomi")

    query = f"""
        SELECT number, finished_at
        FROM public.results
        WHERE user_id = %s AND {subject} = TRUE
        ORDER BY finished_at DESC
        LIMIT 5
    """
    cursor.execute(query, (user_id,))
    return cursor.fetchall()


def format_results(user_id: int) -> str:
    subjects = {
        "math": "📘 Matematika",
        "literature": "📗 Ona tili",
        "history": "📙 O'zbekiston tarixi",
    }

    text = "<b>📊 So'nggi test natijalaringiz:</b>\n\n"

    for subject, title in subjects.items():
        rows = get_last_5_results(user_id, subject)
        if not rows:
            continue

        text += f"{title}:\n"
        for idx, (number, finished_at) in enumerate(rows, 1):
            score = round(number * 1.1, 1)
            time_str = finished_at.strftime("%Y-%m-%d %H:%M")
            text += f"{idx}. {number} ta to'g'ri javob | {score} ball | {time_str}\n"
        text += "\n"

    if text.strip() == "<b>📊 So'nggi test natijalaringiz:</b>":
        return "Siz hali hech qanday test ishlamagansiz."
    return text
