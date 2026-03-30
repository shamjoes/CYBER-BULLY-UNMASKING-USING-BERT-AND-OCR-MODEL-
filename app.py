from flask import Flask, render_template, request, redirect, session
import sqlite3
import pandas as pd
from bert_predict import predict   # 🔥 BERT IMPORT
import cv2
import pytesseract
from PIL import Image
import os
import pytesseract
from PIL import Image
from werkzeug.utils import secure_filename
from langdetect import detect
from deep_translator import GoogleTranslator
from paddleocr import PaddleOCR
from deep_translator import GoogleTranslator



app = Flask(__name__)
app.secret_key = "cyber_secret_key"


UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
def translate_text(text, target_lang):
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return translated
    except:
        return text
def convert_to_english(text):
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated
    except:
        return text

def normalize_text(text):
    text = text.lower()

    replacements = {
        "pundaa": "punda",
        "pundaaa": "punda",
        "pun da": "punda",
        "loose": "loosu",
        "idiotaa": "idiot"
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    return text
# ---------------- OCR FUNCTION ----------------

ocr = PaddleOCR(use_angle_cls=True, lang='ta')   # 'ml' = multi-language   # 'en' enables multi‑language model

def extract_text_from_image(image_path):
    try:
        result = ocr.ocr(image_path, cls=True)
        texts = [line[1][0] for line in result[0]]
        return " ".join(texts)
    except Exception as e:
        print("PaddleOCR error:", e)
        return ""


# ---------------- DATABASE SETUP ----------------

def init_db():
    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    mother_tongue TEXT,
    bullying_count INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0
)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    content TEXT,
                    image TEXT,
                    is_bullying INTEGER DEFAULT 0
                )''')


    c.execute('''CREATE TABLE IF NOT EXISTS replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id INTEGER,
                    username TEXT,
                    content TEXT,
                    is_bullying INTEGER DEFAULT 0
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id INTEGER,
                    username TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receiver TEXT,
    sender TEXT,
    comment TEXT,
    reply_id INTEGER,
    is_read INTEGER DEFAULT 0
)''')


    conn.commit()
    conn.close()

init_db()

# ---------------- SIGNUP ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        mother_tongue = request.form["mother_tongue"]
        mother_tongue = request.form.get("mother_tongue", "en")   # <-- new

        conn = sqlite3.connect("cyberbully.db")
        c = conn.cursor()
        try:
            c.execute(
"INSERT INTO users (username, password, mother_tongue) VALUES (?, ?, ?)",
(username, password, mother_tongue)
)
            conn.commit()
            conn.close()
            return redirect("/")
        except:
            conn.close()
            return "Username already exists!"
    return render_template("signup.html")

# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():
    message = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin@123":
            session["admin"] = True
            return redirect("/admin")

        conn = sqlite3.connect("cyberbully.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()

        if not user:
            message = "No account exists. Please signup."
        else:
            if user[2] != password:
                message = "Incorrect password."
            elif user[5] == 1:
                message = "This account is blocked by admin."
            else:
                session["user"] = username
                conn.close()
                return redirect("/dashboard")

        conn.close()

    return render_template("login.html", message=message)

# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    # Get only non-bullying tweets
    c.execute("SELECT * FROM tweets WHERE is_bullying=0 ORDER BY id DESC")
    tweets = c.fetchall()

    # Get replies
    c.execute("SELECT * FROM replies WHERE is_bullying=0")
    replies = c.fetchall()
    # Get unread notifications
    c.execute("SELECT COUNT(*) FROM messages WHERE receiver=? AND is_read=0",
              (session["user"],))
    notification_count = c.fetchone()[0]

    # 🔥 ALWAYS DEFINE STRIKE
    c.execute("SELECT bullying_count FROM users WHERE username=?",
              (session["user"],))
    result = c.fetchone()

    if result:
        strike = result[0]
    else:
        strike = 0

    conn.close()

    return render_template("dashboard.html",
                           tweets=tweets,
                           replies=replies,
                           notification_count=notification_count,
                           current_user=session["user"],
                           strike=strike)
@app.route("/ignore_message", methods=["POST"])
def ignore_message():
    if "user" not in session:
        return redirect("/")

    message_id = request.form["message_id"]

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    c.execute("DELETE FROM messages WHERE id=?", (message_id,))

    conn.commit()
    conn.close()

    return redirect("/messages")
@app.route("/delete_comment", methods=["POST"])
def delete_comment():
    if "user" not in session:
        return redirect("/")

    message_id = request.form["message_id"]
    reply_id = request.form["reply_id"]

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    if reply_id:
        c.execute("DELETE FROM replies WHERE id=?", (reply_id,))

    c.execute("DELETE FROM messages WHERE id=?", (message_id,))

    conn.commit()
    conn.close()

    return redirect("/messages")



# ---------------- POST TWEET ----------------

from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route("/post", methods=["POST"])
def post():
    if "user" not in session:
        return redirect("/")

    username = session["user"]
    content = request.form["tweet"]

    image = request.files.get("image")
    filename = None
    image_text = ""

    # Save image if exists
    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(image_path)
        image_text = extract_text_from_image(image_path)

    # Combine tweet text and OCR text (if any)
    full_content = content
    if image_text:
        full_content += " " + image_text

    # Translate the combined text to English (if needed)
    english_text = convert_to_english(full_content)

    prediction = predict(english_text)
    is_bully = True if prediction == 1 else False

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    # Save tweet always (for admin evidence)
    c.execute(
        "INSERT INTO tweets (username, content, image, is_bullying) VALUES (?, ?, ?, ?)",
        (username, content, filename, 1 if is_bully else 0)
    )

    tweet_id = c.lastrowid

    if is_bully:

        # 🔥 Increase strike
        c.execute("UPDATE users SET bullying_count = bullying_count + 1 WHERE username=?",
                  (username,))

        c.execute("SELECT bullying_count FROM users WHERE username=?", (username,))
        strike = c.fetchone()[0]

        # 🔥 Prepare preview of bully content
        preview = content.strip()
        if len(preview) > 60:
            preview = preview[:60] + "..."

        # 🔥 Permanent warning message with actual content
        warning_text = f"⚠ Warning {strike}/3: You posted bullying content -> \"{preview}\". Continued violation will block your account."

        c.execute("""
        INSERT INTO messages (receiver, sender, comment, reply_id, is_read)
        VALUES (?, ?, ?, ?, 0)
        """, (username, "ADMIN", warning_text, tweet_id))

        # 🔥 Auto block at 3
        if strike >= 3:
            c.execute("UPDATE users SET blocked=1 WHERE username=?", (username,))
            conn.commit()
            conn.close()
            session.clear()

            return f"""
            <script>
                alert("3/3 Warnings!\\nYou posted -> '{preview}'\\nYour account has been blocked.");
                window.location = "/";
            </script>
            """

        conn.commit()
        conn.close()

        return f"""
        <script>
            alert("Warning {strike}/3:\\nYou posted -> '{preview}'\\nIf repeated 3 times your account will be blocked.");
            window.location = "/dashboard";
        </script>
        """

    conn.commit()
    conn.close()

    return redirect("/dashboard")
@app.route("/reply/<int:tweet_id>", methods=["POST"])
def reply(tweet_id):
    if "user" not in session:
        return redirect("/")

    username = session["user"]
    content = request.form["reply"]

    english_text = convert_to_english(content)

    prediction = predict(english_text)
    is_bully = True if prediction == 1 else False

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    # 🔥 Save reply (for admin evidence)
    c.execute(
        "INSERT INTO replies (tweet_id, username, content, is_bullying) VALUES (?, ?, ?, ?)",
        (tweet_id, username, content, 1 if is_bully else 0)
    )

    reply_id = c.lastrowid

    if is_bully:

        # 🔥 Increase strike
        c.execute("UPDATE users SET bullying_count = bullying_count + 1 WHERE username=?",
                  (username,))

        c.execute("SELECT bullying_count FROM users WHERE username=?", (username,))
        strike = c.fetchone()[0]

        # 🔥 Prepare preview text
        preview = content.strip()
        if len(preview) > 60:
            preview = preview[:60] + "..."

        # 🔥 Permanent warning with actual reply text
        warning_text = f"⚠ Warning {strike}/3: You posted bullying reply -> \"{preview}\". Continued violation will block your account."

        c.execute("""
        INSERT INTO messages (receiver, sender, comment, reply_id, is_read)
        VALUES (?, ?, ?, ?, 0)
        """, (username, "ADMIN", warning_text, reply_id))

        # 🔥 Auto block at 3
        if strike >= 3:
            c.execute("UPDATE users SET blocked=1 WHERE username=?", (username,))
            conn.commit()
            conn.close()
            session.clear()

            return f"""
            <script>
                alert("3/3 Warnings!\\nYou posted -> '{preview}'\\nYour account has been blocked.");
                window.location = "/";
            </script>
            """

        conn.commit()
        conn.close()

        return f"""
        <script>
            alert("Warning {strike}/3:\\nYou posted -> '{preview}'");
            window.location = "/dashboard";
        </script>
        """

    else:
        # ✅ Notify tweet owner only if not bullying
        c.execute("SELECT username FROM tweets WHERE id=?", (tweet_id,))
        owner = c.fetchone()[0]

        if owner != username:
            c.execute("""
            INSERT INTO messages (receiver, sender, comment, reply_id, is_read)
            VALUES (?, ?, ?, ?, 0)
            """, (owner, username, content, reply_id))

        conn.commit()
        conn.close()

        return redirect("/dashboard")
# ---------------- VIEW MESSAGES ----------------

@app.route("/messages")
def messages():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    c.execute("""
    SELECT m.id, m.sender, m.comment, r.id
    FROM messages m
    LEFT JOIN replies r
    ON m.comment = r.content AND m.sender = r.username
    WHERE m.receiver=?
""", (session["user"],))

    msgs = c.fetchall()

    c.execute("UPDATE messages SET is_read=1 WHERE receiver=?",
              (session["user"],))

    conn.commit()
    conn.close()

    return render_template("messages.html", messages=msgs)
@app.route("/translate")
def translate():

    text = request.args.get("text")

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    c.execute("SELECT mother_tongue FROM users WHERE username=?", (session["user"],))
    lang = c.fetchone()[0]

    conn.close()

    translated = translate_text(text, lang)

    return translated

# ---------------- ADMIN ----------------

@app.route("/admin")
@app.route("/admin/view/<username>")
def admin(username=None):
    if "admin" not in session:
        return redirect("/")

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()

    # Get all users
    c.execute("SELECT username, bullying_count, blocked FROM users")
    users = c.fetchall()

    selected_comments = None
    selected_user = None

    if username:

        # 🔥 Get bullying replies
        c.execute("""
        SELECT content, NULL as image
        FROM replies
        WHERE username=? AND is_bullying=1
        """, (username,))
        replies = c.fetchall()

        # 🔥 Get bullying tweets directly using is_bullying column
        c.execute("""
        SELECT content, image
        FROM tweets
        WHERE username=? AND is_bullying=1
        """, (username,))
        bullying_tweets = c.fetchall()

        selected_comments = replies + bullying_tweets
        selected_user = username

    conn.close()

    return render_template("admin.html",
                           users=users,
                           selected_user=selected_user,
                           selected_comments=selected_comments)# ---------------- BLOCK ----------------

@app.route("/block/<username>")
def block(username):
    if "admin" not in session:
        return redirect("/")

    conn = sqlite3.connect("cyberbully.db")
    c = conn.cursor()
    c.execute("UPDATE users SET blocked=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
