import json
import os
import re
import sqlite3
from database import init_db
from datetime import datetime

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
DATABASE = 'questions.db'


def clean_html(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index_page():
    cursor = get_db().cursor()
    cursor.execute("SELECT * FROM themes ORDER BY order_index")
    themes = cursor.fetchall()

    questions_by_theme = {}
    for theme in themes:
        cursor.execute(
            "SELECT * FROM questions WHERE theme_id = ? ORDER BY order_index", (theme['id'],)
        )
        questions_by_theme[theme['id']] = cursor.fetchall()

    cursor.execute("SELECT * FROM questions WHERE theme_id IS NULL ORDER BY order_index")
    unthemed_questions = cursor.fetchall()

    return render_template(
        'index.html',
        themes=themes,
        questions_by_theme=questions_by_theme,
        unthemed_questions=unthemed_questions,
    )


@app.route('/add', methods=['GET', 'POST'])
def add_question():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        title = request.form['title'].strip()
        answer = request.form['answer'].strip()
        theme_id = request.form.get('theme_id')
        new_theme_name = request.form.get('new_theme_name')

        final_theme_id = None
        if theme_id == 'new' and new_theme_name:
            try:
                cursor.execute("SELECT MAX(order_index) FROM themes")
                max_order = cursor.fetchone()[0]
                new_theme_order_index = (max_order or 0) + 1
                cursor.execute(
                    "INSERT INTO themes (name, order_index) VALUES (?, ?)",
                    (new_theme_name.strip(), new_theme_order_index),
                )
                final_theme_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM themes WHERE name = ?", (new_theme_name.strip(),))
                final_theme_id = cursor.fetchone()['id']
        elif theme_id:
            final_theme_id = int(theme_id)

        cursor.execute(
            "SELECT MAX(order_index) FROM questions WHERE theme_id = ? OR (theme_id IS NULL AND ? IS NULL)",
            (final_theme_id, final_theme_id),
        )
        max_order = cursor.fetchone()[0]
        new_order_index = (max_order or 0) + 1

        cursor.execute(
            "INSERT INTO questions (title, answer, theme_id, order_index) VALUES (?, ?, ?, ?)",
            (title, answer, final_theme_id, new_order_index),
        )

        new_question_id = cursor.lastrowid
        db.commit()

        theme_id_for_url = final_theme_id if final_theme_id is not None else 'unthemed'
        redirect_url = (
            url_for('list_questions', expanded_theme=theme_id_for_url)
            + f'#question-{new_question_id}'
        )

        return redirect(redirect_url)

    cursor.execute("SELECT * FROM themes ORDER BY name")
    themes = cursor.fetchall()
    return render_template('add_question.html', themes=themes)


@app.route('/update_positions', methods=['POST'])
def update_positions():
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    try:
        for theme_data in data.get('themes', []):
            theme_id = theme_data['id']
            for index, question_id in enumerate(theme_data['order']):
                cursor.execute(
                    "UPDATE questions SET order_index = ?, theme_id = ? WHERE id = ?",
                    (index, theme_id, question_id),
                )

        for index, question_id in enumerate(data.get('unthemed', [])):
            cursor.execute(
                "UPDATE questions SET order_index = ?, theme_id = NULL WHERE id = ?",
                (index, question_id),
            )

        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/results', methods=['POST'])
def results():
    interviewee_name = request.form.get('interviewee_name', 'Unknown').strip()
    results_data = json.loads(request.form.get('results_data', '{}'))

    db = get_db()
    cursor = db.cursor()

    status_map = {'positive': '✅', 'neutral': '⚠️', 'negative': '❌', 'unanswered': '➖'}

    cursor.execute("SELECT * FROM themes ORDER BY order_index")
    themes = cursor.fetchall()

    positive_count = 0
    neutral_count = 0
    negative_count = 0
    unanswered_count = 0
    total_db_questions = 0

    processed_results = {}

    def process_question_list(questions):
        nonlocal total_db_questions, positive_count, neutral_count, negative_count, unanswered_count
        result_list = []
        for q in questions:
            total_db_questions += 1
            status = results_data.get(str(q['id']), 'unanswered')

            if status == 'positive':
                positive_count += 1
            elif status == 'neutral':
                neutral_count += 1
            elif status == 'negative':
                negative_count += 1
            else:  # unanswered
                unanswered_count += 1

            result_list.append(
                {'title': clean_html(q['title']), 'status_icon': status_map[status]}
            )
        return result_list

    for theme in themes:
        cursor.execute(
            "SELECT id, title FROM questions WHERE theme_id = ? ORDER BY order_index",
            (theme['id'],),
        )
        questions_in_theme = cursor.fetchall()
        if not questions_in_theme:
            continue
        processed_results[theme['name']] = process_question_list(questions_in_theme)

    cursor.execute("SELECT id, title FROM questions WHERE theme_id IS NULL ORDER BY order_index")
    unthemed_questions = cursor.fetchall()
    if unthemed_questions:
        processed_results['Без темы'] = process_question_list(unthemed_questions)

    answered_questions_count = positive_count + neutral_count + negative_count
    rating = (
        ((positive_count * 1 + neutral_count * 0.5) / answered_questions_count * 100)
        if answered_questions_count > 0
        else 0
    )

    if not os.path.exists('results'):
        os.makedirs('results')

    timestamp = datetime.now().strftime("%Y-%m-%d")
    safe_name = (
        re.sub(r'[^\w\s-]', '', interviewee_name).replace(' ', '_')
        if interviewee_name
        else 'Unknown'
    )
    filename = f"results/{safe_name}_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Результаты технического интервью: {interviewee_name}\n")
        f.write("===================================\n")
        f.write(f"Всего вопросов в скрининге: {total_db_questions}\n")
        f.write(f"Оценено вопросов: {answered_questions_count}\n")
        f.write(f"Пропущено вопросов: {unanswered_count}\n")
        f.write("-----------------------------------\n")
        f.write(f"Успешных ответов (✅): {positive_count}\n")
        f.write(f"Нейтральных ответов (⚠️): {neutral_count}\n")
        f.write(f"Неуспешных ответов (❌): {negative_count}\n")
        f.write(f"Рейтинг (от оцененных): {rating:.1f}%\n\n")
        f.write("Детализация по вопросам:\n")
        f.write("------------------------\n")
        for theme_name, theme_results in processed_results.items():
            f.write(f"\n--- {theme_name.upper()} ---\n")
            for res in theme_results:
                f.write(f"{res['status_icon']} {res['title'].strip()}\n")

    print(f"Результаты сохранены в файл: {filename}")

    return render_template(
        'results.html',
        results_by_theme=processed_results,
        total=total_db_questions,
        answered=answered_questions_count,
        positive=positive_count,
        neutral=neutral_count,
        negative=negative_count,
        unanswered=unanswered_count,
        rating=rating,
        interviewee_name=interviewee_name,
    )


@app.route('/questions')
def list_questions():
    expanded_theme = request.args.get('expanded_theme')

    cursor = get_db().cursor()

    cursor.execute("SELECT * FROM themes ORDER BY order_index")
    themes = cursor.fetchall()

    questions_by_theme = {}
    for theme in themes:
        cursor.execute(
            "SELECT * FROM questions WHERE theme_id = ? ORDER BY order_index", (theme['id'],)
        )
        questions_by_theme[theme['id']] = cursor.fetchall()

    cursor.execute("SELECT * FROM questions WHERE theme_id IS NULL ORDER BY order_index")
    unthemed_questions = cursor.fetchall()

    return render_template(
        'questions.html',
        themes=themes,
        questions_by_theme=questions_by_theme,
        unthemed_questions=unthemed_questions,
        expanded_theme=expanded_theme,
    )


@app.route('/update_question/<int:question_id>', methods=['POST'])
def update_question(question_id):
    """
    Обновляет текст заголовка и ответа для указанного вопроса.
    """
    data = request.get_json()
    new_title = data.get('title', '').strip()
    new_answer = data.get('answer', '').strip()

    if not new_title or not new_answer:
        return jsonify({'success': False, 'error': 'Заголовок и ответ не могут быть пустыми'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE questions SET title = ?, answer = ? WHERE id = ?",
            (new_title, new_answer, question_id),
        )
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/add_theme', methods=['POST'])
def add_theme():
    data = request.get_json()
    theme_name = data.get('name', '').strip()
    if not theme_name:
        return jsonify({'success': False, 'error': 'Имя темы не может быть пустым'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT MAX(order_index) FROM themes")
        max_order = cursor.fetchone()[0]
        new_order_index = (max_order or 0) + 1

        cursor.execute(
            "INSERT INTO themes (name, order_index) VALUES (?, ?)", (theme_name, new_order_index)
        )
        new_theme_id = cursor.lastrowid
        db.commit()
        return jsonify({'success': True, 'id': new_theme_id, 'name': theme_name})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Тема с таким именем уже существует'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/update_theme_order', methods=['POST'])
def update_theme_order():
    data = request.get_json()
    theme_ids = data.get('order', [])
    db = get_db()
    cursor = db.cursor()
    try:
        for index, theme_id in enumerate(theme_ids):
            cursor.execute("UPDATE themes SET order_index = ? WHERE id = ?", (index, theme_id))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/update_theme_name', methods=['POST'])
def update_theme_name():
    data = request.get_json()
    theme_id = data.get('id')
    new_name = data.get('name', '').strip()

    if not theme_id or not new_name:
        return jsonify({'success': False, 'error': 'Неверные данные'}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE themes SET name = ? WHERE id = ?", (new_name, theme_id))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_theme/<int:theme_id>', methods=['POST'])
def delete_theme(theme_id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
