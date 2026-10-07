from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key")

DATABASE = "allotment.db"


# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# CREATE DATABASE
# -----------------------------
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS colleges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            college_name TEXT NOT NULL,
            course TEXT NOT NULL,
            category TEXT NOT NULL,
            min_rank INTEGER NOT NULL,
            max_rank INTEGER NOT NULL,
            seats INTEGER NOT NULL,
            fee INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            rank INTEGER NOT NULL,
            category TEXT NOT NULL,
            preference1 TEXT,
            preference2 TEXT,
            preference3 TEXT,
            allotted_college TEXT,
            allotted_course TEXT,
            status TEXT
        )
    """)

    # Add sample data only if table is empty
    count = conn.execute(
        "SELECT COUNT(*) FROM colleges"
    ).fetchone()[0]

    if count == 0:
        colleges = [
            ("Government Engineering College", "Computer Science", "General", 1, 5000, 10, 45000),
            ("Government Engineering College", "Information Technology", "General", 1, 8000, 10, 40000),
            ("City Engineering College", "Computer Science", "General", 1, 12000, 15, 60000),
            ("City Engineering College", "Electronics", "General", 1, 18000, 20, 55000),
            ("National Institute of Technology", "Computer Science", "General", 1, 3000, 5, 90000),

            ("Government Engineering College", "Computer Science", "OBC", 1, 9000, 10, 45000),
            ("Government Engineering College", "Information Technology", "OBC", 1, 13000, 10, 40000),
            ("City Engineering College", "Computer Science", "OBC", 1, 18000, 15, 60000),

            ("Government Engineering College", "Computer Science", "SC", 1, 20000, 10, 45000),
            ("City Engineering College", "Computer Science", "SC", 1, 30000, 15, 60000),

            ("Government Engineering College", "Computer Science", "ST", 1, 25000, 10, 45000),
            ("City Engineering College", "Computer Science", "ST", 1, 35000, 15, 60000)
        ]

        conn.executemany("""
            INSERT INTO colleges
            (college_name, course, category, min_rank, max_rank, seats, fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, colleges)

    conn.commit()
    conn.close()


# -----------------------------
# HOME PAGE
# -----------------------------
@app.route("/")
def index():
    conn = get_db()

    colleges = conn.execute("""
        SELECT * FROM colleges
        ORDER BY college_name, course
    """).fetchall()

    conn.close()

    return render_template("index.html", colleges=colleges)


# -----------------------------
# SEAT ALLOTMENT
# -----------------------------
@app.route("/allot", methods=["POST"])
def allot():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    rank_text = request.form.get("rank", "").strip()
    category = request.form.get("category", "").strip()

    preference1 = request.form.get("preference1", "").strip()
    preference2 = request.form.get("preference2", "").strip()
    preference3 = request.form.get("preference3", "").strip()

    # Basic validation
    if not name or not email or not rank_text or not category:
        flash("Please fill in all required fields.")
        return redirect(url_for("index"))

    try:
        rank = int(rank_text)
    except ValueError:
        flash("Rank must be a valid number.")
        return redirect(url_for("index"))

    if rank <= 0:
        flash("Rank must be greater than zero.")
        return redirect(url_for("index"))

    preferences = [
        preference1,
        preference2,
        preference3
    ]

    preferences = [p for p in preferences if p]

    if not preferences:
        flash("Please select at least one course preference.")
        return redirect(url_for("index"))

    conn = get_db()

    allotted_college = None
    allotted_course = None
    allotted_fee = None

    # Check preferences in order
    for preference in preferences:

        college = conn.execute("""
            SELECT *
            FROM colleges
            WHERE course = ?
            AND category = ?
            AND min_rank <= ?
            AND max_rank >= ?
            AND seats > 0
            ORDER BY min_rank ASC
        """, (
            preference,
            category,
            rank,
            rank
        )).fetchone()

        if college:
            allotted_college = college["college_name"]
            allotted_course = college["course"]
            allotted_fee = college["fee"]

            # Reduce available seat
            conn.execute("""
                UPDATE colleges
                SET seats = seats - 1
                WHERE id = ?
                AND seats > 0
            """, (college["id"],))

            break

    # Student was successfully allotted
    if allotted_college:

        conn.execute("""
            INSERT INTO students (
                name,
                email,
                rank,
                category,
                preference1,
                preference2,
                preference3,
                allotted_college,
                allotted_course,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            rank,
            category,
            preference1,
            preference2,
            preference3,
            allotted_college,
            allotted_course,
            "ALLOTTED"
        ))

        conn.commit()
        conn.close()

        result = {
            "name": name,
            "rank": rank,
            "category": category,
            "college": allotted_college,
            "course": allotted_course,
            "fee": allotted_fee
        }

        return render_template(
            "result.html",
            result=result
        )

    # No seat available
    conn.execute("""
        INSERT INTO students (
            name,
            email,
            rank,
            category,
            preference1,
            preference2,
            preference3,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        rank,
        category,
        preference1,
        preference2,
        preference3,
        "NOT ALLOTTED"
    ))

    conn.commit()
    conn.close()

    result = {
        "name": name,
        "rank": rank,
        "category": category
    }

    return render_template(
        "result.html",
        result=result,
        not_allotted=True
    )


# -----------------------------
# ADMIN PAGE
# -----------------------------
@app.route("/admin")
def admin():

    conn = get_db()

    colleges = conn.execute("""
        SELECT * FROM colleges
        ORDER BY college_name, course
    """).fetchall()

    students = conn.execute("""
        SELECT * FROM students
        ORDER BY rank ASC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        colleges=colleges,
        students=students
    )


# -----------------------------
# RESET SEATS
# -----------------------------
@app.route("/reset-seats", methods=["POST"])
def reset_seats():

    conn = get_db()

    # Restore sample seat count
    conn.execute("""
        UPDATE colleges
        SET seats =
            CASE
                WHEN college_name = 'Government Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'General' THEN 10

                WHEN college_name = 'Government Engineering College'
                     AND course = 'Information Technology'
                     AND category = 'General' THEN 10

                WHEN college_name = 'City Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'General' THEN 15

                WHEN college_name = 'City Engineering College'
                     AND course = 'Electronics'
                     AND category = 'General' THEN 20

                WHEN college_name = 'National Institute of Technology'
                     AND course = 'Computer Science'
                     AND category = 'General' THEN 5

                WHEN college_name = 'Government Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'OBC' THEN 10

                WHEN college_name = 'Government Engineering College'
                     AND course = 'Information Technology'
                     AND category = 'OBC' THEN 10

                WHEN college_name = 'City Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'OBC' THEN 15

                WHEN college_name = 'Government Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'SC' THEN 10

                WHEN college_name = 'City Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'SC' THEN 15

                WHEN college_name = 'Government Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'ST' THEN 10

                WHEN college_name = 'City Engineering College'
                     AND course = 'Computer Science'
                     AND category = 'ST' THEN 15

                ELSE seats
            END
    """)

    conn.commit()
    conn.close()

    flash("Seats have been reset successfully.")

    return redirect(url_for("admin"))


# -----------------------------
# RUN APPLICATION
# -----------------------------
if __name__ == "__main__":
    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
