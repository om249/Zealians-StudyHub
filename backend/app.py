from models import user
from flask import Flask, render_template, request, redirect, session, Response, send_file, jsonify
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import os
import io
import csv
import subprocess
import bcrypt
import random
import sib_api_v3_sdk
#import google.generativeai as genai
from google import genai
from sib_api_v3_sdk.rest import ApiException
from werkzeug.utils import secure_filename

FACULTY_DOMAIN = "zealeducation.com"


app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static"
)




UPLOAD_FOLDER = "../static/uploads/notes"
ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "xlsx", "txt"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = "supersecret123"

# Folders where files are actually stored (relative to backend/)
NOTES_DIR = "static/uploads/notes"
TEMP_DIR = os.path.abspath(os.path.join(app.root_path, "..", "static", "temp"))

os.makedirs(NOTES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


model="models/gemini-flash-latest"



gemini_client = genai.Client(
    api_key="AIzaSyDST201O4MQXg-xGzQEgg0HQTm4AEmaxs8"
)
# --------------------------#
# MONGO CONFIG              #
# --------------------------#
client = MongoClient("mongodb://localhost:27017/")
db = client["studyhub"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --------------------------#
# ROLE BASED PROTECTION     #
# --------------------------#
def admin_required(f):
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return "❌ Access Denied (Admins Only)"
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def student_required(f):
    def wrapper(*args, **kwargs):
        if session.get("role") != "student":
            return "❌ Access Denied (Students Only)"
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper



def send_otp_email(email, otp):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = "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"

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    subject = "Your StudyHub Account Verification OTP"
    html_content = f"""
    <h2>Welcome to Zealians StudyHub</h2>
    <p>Your OTP for account verification is:</p>
    <h1>{otp}</h1>
    <p>This OTP will expire in 10 minutes.</p>
    """

    send_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email}],
        sender={"email": "zealians.studyhub@gmail.com", "name": "Zealians StudyHub"},
        subject=subject,
        html_content=html_content
    )

    try:
        api_instance.send_transac_email(send_email)
        return True
    except ApiException as e:
        print("Email sending failed:", e)
        return False

def send_email(to_email, subject, html_content):
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = "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"  # same key you already use

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        subject=subject,
        html_content=html_content,
        sender={
            "name": "Zealians StudyHub",
            "email": "no-reply@zealians.com"
        }
    )

    try:
        api_instance.send_transac_email(email)
        print(f"📧 Email sent to {to_email}")
    except ApiException as e:
        print("❌ Email send failed:", e)


def get_students_for_notification(course, division=None):
    query = {
        "role": "student",
        "approval_status": "approved",
        "course": course
    }

    if division:
        query["division"] = division

    return list(db.users.find(query))


def send_content_notification(students, title, message):

    print("📨 Notification triggered")
    print("👥 Students found:", len(students))

    for s in students:
        email = s.get("email")
        name = s.get("name", "Student")

        print("➡️ Sending email to:", email)

        send_email(
            email,
            title,
            message.format(name=name)
        )






def send_approval_email(email):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = "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"

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    html_content = """
    <h2>Zealians StudyHub – Account Approved</h2>
    <p>Your student account has been approved by the administration.</p>
    <p>You can now log in and access all study resources.</p>
    <br>
    <b>Best of luck with your studies!</b>
    """

    email_data = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email}],
        sender={"email": "zealians.studyhub@gmail.com", "name": "Zealians StudyHub"},
        subject="Your StudyHub Account is Approved",
        html_content=html_content
    )

    api_instance.send_transac_email(email_data)


def send_rejection_email(email, reason):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = "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"

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    html_content = f"""
    <h2>Zealians StudyHub – Account Verification Failed</h2>
    <p>Your account could not be approved.</p>
    <p><b>Reason:</b> {reason}</p>
    <p>Please log in and re-upload your ID card with correct details.</p>
    """

    email_data = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email}],
        sender={"email": "zealians.studyhub@gmail.com", "name": "Zealians StudyHub"},
        subject="Your StudyHub Account Was Rejected",
        html_content=html_content
    )

    api_instance.send_transac_email(email_data)

def get_subjects_for_course(course):
    return list(db.subjects.find(
        {"course": course},
        {"name": 1}
    ).sort("name", 1))

def get_chapters_for_subject(subject_id):
    return list(db.chapters.find(
        {"subject_id": ObjectId(subject_id)}
    ).sort("order", 1))


# --------------------------#
# GENERAL PAGES             #
# --------------------------#
@app.route("/")
@login_required
def home():
    role = session.get("role")

    # STUDENT HOME
    if role == "student":
        user = db.users.find_one({"_id": ObjectId(session["user_id"])})
        if not user:
            return redirect("/login")

        course = user.get("course")
        subjects = get_subjects_for_course(course)

        return render_template(
            "index.html",
            subjects=subjects,
            student_course=course
        )

    # FACULTY / ADMIN HOME (NO SUBJECT DATA)
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html",datetime=datetime)

@app.route("/debug/routes")
def debug_routes():
    return "<br>".join([str(r) for r in app.url_map.iter_rules()])


# --------------------------#
# AUTH                      #
# --------------------------#
# ---------- LOGIN ----------
from flask import flash

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        user = db.users.find_one({"email": email})
        if not user:
            flash("Invalid email or password.", "error")
            return redirect("/login")

        # bcrypt check
        if not bcrypt.checkpw(password.encode(), user["password"].encode()):
            flash("Invalid email or password.", "error")
            return redirect("/login")

        if not user.get("is_verified", False):
            flash("Please verify your email before logging in.", "warning")
            return redirect("/login")

        if user["role"] == "student":
            if user.get("approval_status") == "pending":
                flash("Your account is under verification. Please wait for approval.", "warning")
                return redirect("/login")

            if user.get("approval_status") == "rejected":
                reason = user.get("rejection_reason", "Not specified")
                flash(f"Your account was rejected. Reason: {reason}", "error")
                return redirect("/login")

        # ✅ LOGIN SUCCESS
        session["user_id"] = str(user["_id"])
        session["role"] = user["role"]
        flash("Login successful.", "success")
        return redirect("/")

    return render_template("login.html")




@app.route("/check_login_credentials", methods=["POST"])
def check_login_credentials():
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    user = db.users.find_one({"email": email})
    if not user:
        return {"status": "email_not_found"}

    # FIXED bcrypt compare
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return {"status": "wrong_password"}

    if not user.get("is_verified", False):
        return {"status": "not_verified"}

    return {"status": "success"}


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        zprn = request.form.get("zprn", "").strip()
        course = request.form.get("course")
        division = request.form.get("division")
        roll_no = request.form.get("roll_no")
        id_card = request.files.get("id_card")

        role = "admin" if email.endswith("@zealeducation.com") else "student"
        existing = db.users.find_one({"email": email})

        # ---------- EXISTING USER HANDLING ----------
        if existing:
            status = existing.get("approval_status")

            if status == "approved":
                flash("Email already registered. Please login.", "error")
                return render_template("signup.html")

            if status == "pending":
                flash("Your account is already under verification. Please wait for approval.", "info")
                return render_template("signup.html")
            # rejected → allowed to continue

        # ---------- STUDENT VALIDATION ----------
        if role == "student":

            if not division:
                flash("Division is required.", "error")
                return render_template("signup.html")

            division = division.upper().strip()  # normalize (A/B/C/D)

            if not id_card or id_card.filename == "":
                flash("College ID card is required.", "error")
                return render_template("signup.html")

            ext = id_card.filename.rsplit(".", 1)[1].lower()
            if ext not in {"jpg", "jpeg", "png", "pdf"}:
                flash("Invalid ID card format.", "error")
                return render_template("signup.html")

            if not zprn:
                flash("ZPRN is required for students.", "error")
                return render_template("signup.html")

        # ---------- PASSWORD VALIDATION ----------
        if not (8 <= len(password) <= 20):
            flash("Password must be 8–20 characters.", "error")
            return render_template("signup.html")
        if not any(c.islower() for c in password):
            flash("Password must contain a lowercase letter.", "error")
            return render_template("signup.html")
        if not any(c.isupper() for c in password):
            flash("Password must contain an uppercase letter.", "error")
            return render_template("signup.html")
        if not any(c.isdigit() for c in password):
            flash("Password must contain a digit.", "error")
            return render_template("signup.html")
        if not any(c in "!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~" for c in password):
            flash("Password must contain a symbol.", "error")
            return render_template("signup.html")

        # ---------- SAVE ID CARD ----------
        id_card_path = None
        if role == "student":
            filename = secure_filename(f"{email}_id.{ext}")
            path = f"static/uploads/id_cards/{filename}"
            id_card.save(path)
            id_card_path = "/" + path

        # ---------- FINAL DATA ----------
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        otp = str(random.randint(100000, 999999))
        otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        data = {
            "name": name,
            "email": email,
            "password": hashed,
            "role": role,
            "zprn": zprn if role == "student" else None,
            "course": course,
            "division": division if role == "student" else None,
            "roll_no": roll_no if role == "student" else None,
            "id_card_url": id_card_path,
            "approval_status": "pending" if role == "student" else "approved",
            "rejection_reason": None,
            "is_verified": False,
            "otp": otp,
            "otp_expiry": otp_expiry,
            "created_at": datetime.utcnow()
        }

        # ---------- INSERT / UPDATE ----------
        if existing:
            db.users.update_one(
                {"email": email},
                {"$set": data}
            )
        else:
            db.users.insert_one(data)

        send_otp_email(email, otp)
        session["pending_email"] = email

        flash("OTP sent successfully. Please verify your email.", "success")
        return redirect("/verify")

    return render_template("signup.html")


@app.route("/admin/pending_students")
@login_required
def pending_students():

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        return redirect("/login")

    # admin == faculty
    if user.get("role") != "admin":
        return "❌ Access Denied"

    course = user.get("course")

    # 🔑 ONLY students of SAME course
    students = list(db.users.find({
        "role": "student",
        "approval_status": "pending",
        "course": course
    }))

    return render_template(
        "admin_dashboard.html",
        students=students
    )

@app.route("/admin/approve_student", methods=["POST"])
@login_required
def approve_student():

    approver = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not approver or approver.get("role") != "admin":
        return "❌ Access Denied"

    approver_course = approver.get("course")

    user_id = request.form.get("id")
    student = db.users.find_one({"_id": ObjectId(user_id)})

    if not student:
        return redirect("/admin/dashboard")

    # 🔐 COURSE CHECK (MOST IMPORTANT)
    if student.get("course") != approver_course:
        return "❌ You cannot approve students from another course"

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "approval_status": "approved",
            "rejection_reason": None
        }}
    )

    send_approval_email(student["email"])
    return redirect("/admin/dashboard")



@app.route("/admin/reject_student", methods=["POST"])
@admin_required
def reject_student():
    user_id = request.form.get("id")
    reason = request.form.get("reason")

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return redirect("/admin/dashboard")

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "approval_status": "rejected",
            "rejection_reason": reason
        }}
    )

    send_rejection_email(user["email"], reason)
    return redirect("/admin/dashboard")




# ---------- VERIFY ----------
@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("pending_email")
    if not email:
        return redirect("/signup")

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        user = db.users.find_one({"email": email})
        if not user:
            return "User not found", 404

        # expired?
        if "otp_expiry" not in user or datetime.utcnow() > user.get("otp_expiry"):
            return "OTP expired. Please resend.", 400

        if str(user.get("otp")) != entered_otp:
            return "Invalid OTP", 400

        # successful
        db.users.update_one({"email": email}, {"$set": {"is_verified": True}, "$unset": {"otp": "", "otp_expiry": ""}})
        session.pop("pending_email", None)
        return redirect("/login")

    # GET
    return render_template("verify.html")


@app.route("/_pending_email")
def _pending_email():
    email = session.get("pending_email")
    if not email:
        return jsonify({"email": None})
    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"email": None})
    # compute remaining seconds
    expires = user.get("otp_expiry")
    if not expires:
        return jsonify({"email": email})
    remaining = int((expires - datetime.utcnow()).total_seconds())
    return jsonify({"email": email, "expires_in": max(0, remaining)})

# ---------- RESEND OTP (AJAX friendly) ----------
@app.route("/resend_otp", methods=["POST"])
def resend_otp():
    email = session.get("pending_email")
    if not email:
        # if called outside flow return JSON for UI
        return jsonify({"success": False, "message": "No pending email in session"}), 400

    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    new_otp = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=10)
    db.users.update_one({"email": email}, {"$set": {"otp": new_otp, "otp_expiry": expiry}})

    try:
        send_otp_email(email, new_otp)
    except Exception as e:
        print("Resend error:", e)
        return jsonify({"success": False, "message": "Failed to send OTP"}), 500

    return jsonify({"success": True, "message": "OTP resent. Check your email.", "expires_in": 10*60})







@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# --------------------------#
# STUDENT DASHBOARD         #
# --------------------------#
@app.route("/student/dashboard")
@student_required
def student_dashboard():
    user_id = session.get("user_id")

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        user = {"name": "Unknown", "email": "unknown@local", "role": "student"}

    downloads = list(db.downloads.find({"user_id": user_id}).sort("downloaded_at", -1))
    results = list(db.mcq_results.find({"student_id": user_id}).sort("submitted_at", -1))

    tests_attempted = len(results)
    avg_score = 0
    if tests_attempted > 0:
        avg_score = sum([(r["marks"] / r["total"]) * 100 for r in results]) / tests_attempted

    stats = {
        "downloads": len(downloads),
        "tests_attempted": tests_attempted,
        "avg_score": round(avg_score, 1)
    }

    # subjects = list(db.subjects.find({
    # "course": user.get("course")
    # }))

    return render_template(
    "student_dashboard.html",
    user=user,
    stats=stats,
    results=results,
    downloads_history=downloads,
    # subjects=subjects
)


@app.route("/student/profile/edit", methods=["GET", "POST"])
# @login_required
def student_edit_profile():

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":

        update_data = {
            "name": request.form.get("name"),
            "division": request.form.get("division"),
            "roll_no": request.form.get("roll_no")
        }

        # Allow ID re-upload ONLY if rejected
        if user.get("approval_status") == "rejected":
            id_card = request.files.get("id_card")

            if not id_card:
                flash("ID card is required.", "error")
                return redirect("/student/profile/edit")

            ext = id_card.filename.rsplit(".", 1)[1].lower()
            if ext not in {"jpg","jpeg","png","pdf"}:
                flash("Invalid file format.", "error")
                return redirect("/student/profile/edit")

            filename = secure_filename(f"{user['email']}_id.{ext}")
            path = f"static/uploads/id_cards/{filename}"
            id_card.save(path)

            update_data.update({
                "id_card_url": "/" + path,
                "approval_status": "pending",
                "rejection_reason": None
            })

        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": update_data}
        )

        flash("Profile updated successfully.", "success")
        return redirect("/student/dashboard")

    return render_template("student_edit_profile.html", user=user)


# --------------------------#
# ADMIN PAGES               #
# --------------------------#

@app.route("/admin/view_id_card/<user_id>")
@admin_required
def view_id_card(user_id):
    user = db.users.find_one({"_id": ObjectId(user_id)})

    # if not user or not user.get("id_card_path"):
    if not user or not user.get("id_card_url"):

        return "ID Card not found", 404

    # id_card_path example: static/uploads/id_cards/abc.pdf
    # rel_path = user["id_card_path"].lstrip("/")
    rel_path = user["id_card_url"].lstrip("/")

    abs_path = os.path.abspath(os.path.join(app.root_path, "..", rel_path))

    if not os.path.exists(abs_path):
        return "File not found", 404

    return send_file(abs_path)


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    admin_id = session["user_id"]
    admin = db.users.find_one({"_id": ObjectId(admin_id)})

    stats = {
        "notes": db.notes.count_documents({}),
        "videos": db.videos.count_documents({}),
        "students": db.users.count_documents({"role": "student"}),
        "total_downloads": db.downloads.count_documents({})
    }

     # 🔥 IMPORTANT: Fetch pending students
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user or user.get("role") != "admin":
        return "❌ Access Denied"

    admin_course = user.get("course")

    # ✅ ONLY SAME-COURSE pending students
    pending_students = list(db.users.find({
        "role": "student",
        "approval_status": "pending",
        "course": admin_course
    }))


    recent_notes = db.notes.find().sort("uploaded_at", -1).limit(3)
    recent_videos = db.videos.find().sort("uploaded_at", -1).limit(3)

    recent = []
    for n in recent_notes:
        recent.append({
            "title": n["title"],
            "type": "Note",
            "date": n["uploaded_at"],
            "link": f"/notes/{n['_id']}"
        })
    for v in recent_videos:
        recent.append({
            "title": v["title"],
            "type": "Video",
            "date": v["uploaded_at"],
            "link": f"/videos/{v['_id']}"
        })

    return render_template("admin_dashboard.html",
                           admin=admin,
                           stats=stats,
                           recent=recent, 
                           pending_students=pending_students)


@app.route("/admin/profile/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_profile():
    admin = db.users.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        dept = request.form.get("department")
        subject = request.form.get("subject")

        update_data = {
            "name": name,
            "email": email,
            "department": dept,
            "subject": subject
        }

        if "photo" in request.files:
            photo = request.files["photo"]
            if photo.filename != "":
                filename = secure_filename(photo.filename)

                save_path = os.path.join(
                    app.root_path, "..", "static",
                    "uploads", "admin_photos", filename
                )
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                photo.save(save_path)

                update_data["photo_url"] = f"/static/uploads/admin_photos/{filename}"

        db.users.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": update_data}
        )

        return redirect("/admin/dashboard")

    return render_template("admin_edit_profile.html", admin=admin)


ADMIN_PHOTO_FOLDER = "../static/uploads/admin_photos"
os.makedirs(ADMIN_PHOTO_FOLDER, exist_ok=True)


@app.route("/admin/profile/update", methods=["POST"])
@admin_required
def admin_profile_update():

    admin_id = session.get("user_id")
    admin = db.users.find_one({"_id": ObjectId(admin_id)})

    if not admin:
        return "Admin not found"

    name = request.form.get("name")
    email = request.form.get("email")
    department = request.form.get("department")
    subject = request.form.get("subject")
    position = request.form.get("position")

    update_data = {
        "name": name,
        "email": email,
        "department": department,
        "subject": subject,
        "position": position
    }

    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename != "":
            filename = secure_filename(photo.filename)
            filepath = os.path.join(ADMIN_PHOTO_FOLDER, filename)
            photo.save(filepath)

            update_data["photo_url"] = f"/static/uploads/admin_photos/{filename}"

    db.users.update_one(
        {"_id": ObjectId(admin_id)},
        {"$set": update_data}
    )

    return redirect("/admin/dashboard")


# --------------------------#
# ADMIN – UPLOAD NOTES      #
# --------------------------#

@app.route("/admin/upload_notes", methods=["GET", "POST"])
@login_required
def upload_notes():

    chapter_id = request.args.get("chapter_id")
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    chapter = None
    subject = None

    # ---------- IF COMING FROM CHAPTER PAGE ----------
    if chapter_id:
        try:
            chapter_oid = ObjectId(chapter_id)
        except:
            return "Invalid chapter ID", 400

        chapter = db.chapters.find_one({"_id": chapter_oid})
        if not chapter:
            return "Chapter not found", 404

        subject = db.subjects.find_one({"_id": chapter["subject_id"]})
        if not subject:
            return "Subject not found", 404

    # ---------- POST ----------
    if request.method == "POST":

        title = request.form.get("title").strip()
        description = request.form.get("description")
        # course = request.form.get("category")
        course = user.get("course")
        subject_id = ObjectId(request.form.get("subject_id"))
        chapter_id = ObjectId(request.form.get("chapter_id"))
        semester = request.form.get("semester")
        divisions = request.form.getlist("divisions")  # checkbox values

        if not divisions:
            flash("Please select at least one division.", "error")
            return redirect(request.url)

        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No file selected.", "error")
            return redirect(request.url)

        filename = secure_filename(file.filename.replace(" ", "_"))
        upload_path = os.path.join(NOTES_DIR, filename)
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        file.save(upload_path)

        db.notes.insert_one({
            "title": title,
            "description": description,
            "course": course,
            "subject_id": subject_id,
            "chapter_id": chapter_id,
            "semester": semester,
            "divisions": divisions,
            "file_url": "/" + upload_path,
            "uploaded_at": datetime.utcnow(),
            "uploaded_by": session["user_id"]
        })


        # 📧 EMAIL NOTIFICATION – NOTES
        for div in divisions:
            students = get_students_for_notification(course=course, division=div)

            if students:
                send_content_notification(
            students,
            title="📘 New Notes Uploaded",
            message=(
                "<h3>Hello {name},</h3>"
                "<p>New notes have been uploaded.</p>"
                f"<p><b>Title:</b> {title}</p>"
                f"<p><b>Semester:</b> {semester}</p>"
                "<p>Please login to <b>Zealians StudyHub</b> to view them.</p>"
            )
        )

        flash("Notes uploaded successfully.", "success")
        return redirect(f"/notes/chapter/{chapter_id}")

    # ---------- GET ----------
    return render_template(
        "admin_upload_notes.html",
        subject=subject,
        chapter=chapter
    )



@app.route("/subjects/<subject_id>")
@login_required
def subject_chapters(subject_id):

    subject = db.subjects.find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return "Subject not found", 404

    chapters = list(db.chapters.find(
        {"subject_id": subject["_id"]}
    ).sort("chapter_no", 1))

    return render_template(
        "subject_chapters.html",
        subject=subject,
        chapters=chapters
    )

@app.route("/notes/chapter/<chapter_id>")
@login_required
def notes_by_chapter(chapter_id):

    # ---------- VALIDATE CHAPTER ID ----------
    try:
        chapter_oid = ObjectId(chapter_id)
    except:
        return "Invalid chapter ID", 400

    # ---------- FETCH CHAPTER ----------
    chapter = db.chapters.find_one({"_id": chapter_oid})
    if not chapter:
        return "Chapter not found", 404

    # ---------- FETCH SUBJECT ----------
    subject = db.subjects.find_one({"_id": chapter["subject_id"]})
    if not subject:
        return "Subject not found", 404

    # ---------- FETCH USER ----------
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        return redirect("/login")

    # ---------- BUILD QUERY ----------
    query = {
        "chapter_id": chapter_oid
    }

    # STUDENT → course + division filtering
    if user.get("role") == "student":
        query.update({
            "course": user.get("course"),
            "divisions": user.get("division")   # array match
        })

    # FACULTY / ADMIN → no division filter
    elif user.get("role") in ["faculty", "admin"]:
        # optional safety: restrict to course
        if user.get("course"):
            query["course"] = user.get("course")

    # ---------- FETCH NOTES ----------
    notes = list(
        db.notes.find(query).sort("uploaded_at", -1)
    )

    # ---------- RENDER ----------
    return render_template(
        "notes_by_chapter.html",
        subject=subject,
        chapter=chapter,
        notes=notes,
        current='Notes'
    )

@app.route("/videos/chapter/<chapter_id>")
@login_required
def videos_by_chapter(chapter_id):

    chapter_oid = ObjectId(chapter_id)
    chapter = db.chapters.find_one({"_id": chapter_oid})
    subject = db.subjects.find_one({"_id": chapter["subject_id"]})

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    role = user["role"]

    query = {
        "chapter_id": chapter_oid
    }

    # STUDENT: strict course + division
    if role == "student":
        query.update({
            "course": user["course"],
            "$or": [
                {"divisions": user["division"]},
                {"divisions": {"$size": 0}}  # all divisions
            ]
        })

    # FACULTY / ADMIN: see all for their course
    else:
        if subject.get("course"):
            query["course"] = subject["course"]

    videos = list(
        db.videos.find(query).sort("uploaded_at", -1)
    )

    return render_template(
        "videos_by_chapter.html",
        subject=subject,
        chapter=chapter,
        videos=videos,
        role=role
    )



@app.route("/mcq/chapter/<chapter_id>")
@login_required
def mcq_by_chapter(chapter_id):

    chapter = db.chapters.find_one({"_id": ObjectId(chapter_id)})
    if not chapter:
        return "Chapter not found", 404

    subject = db.subjects.find_one({"_id": chapter["subject_id"]})

    tests = list(db.mcq_tests.find({
        "chapter_id": chapter["_id"]
    }).sort("created_at", -1))

    # ✅ CHECK ATTEMPTED TESTS (STUDENT ONLY)
    attempted_test_ids = set()

    if session.get("role") == "student":
        student_id = session.get("user_id")

        results = db.mcq_results.find(
            {"student_id": student_id},
            {"test_id": 1}
        )

        attempted_test_ids = {r["test_id"] for r in results}

    return render_template(
        "mcq_by_chapter.html",
        subject=subject,
        chapter=chapter,
        tests=tests,
        attempted_test_ids=attempted_test_ids
    )


@app.route("/notes/<subject_id>", methods=["GET", "POST"])
@login_required
def notes_chapters(subject_id):

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        return redirect("/login")

    role = user.get("role")

    # ---------- SUBJECT ----------
    if role == "student":
        subject = db.subjects.find_one({
            "_id": ObjectId(subject_id),
            "course": user.get("course")
        })
    else:
        subject = db.subjects.find_one({
            "_id": ObjectId(subject_id)
        })

    if not subject:
        return "Subject not found", 404

    # ---------- ADD CHAPTER (ADMIN / FACULTY) ----------
    if request.method == "POST" and role in ["admin", "faculty"]:
        chapter_no = int(request.form.get("chapter_no"))
        title = request.form.get("title").strip()

        if not title:
            return redirect(request.url)

        db.chapters.insert_one({
            "subject_id": subject["_id"],
            "chapter_no": chapter_no,
            "title": title,
            "created_at": datetime.utcnow()
        })

        return redirect(request.url)

    # ---------- FETCH CHAPTERS ----------
    chapters = list(db.chapters.find(
        {"subject_id": subject["_id"]}
    ).sort("chapter_no", 1))

    return render_template(
        "notes_chapters.html",
        subject=subject,
        chapters=chapters
    )



@app.route("/admin/subjects")
@admin_required
def admin_subjects():
    subjects = list(db.subjects.find().sort("course", 1))
    return render_template("admin_subjects.html", subjects=subjects)


@app.route("/admin/subjects/create", methods=["GET", "POST"])
@admin_required
def admin_create_subject():
    if request.method == "POST":
        course = request.form.get("course")
        name = request.form.get("name").strip()

        if not course or not name:
            flash("Course and subject name required.", "error")
            return redirect(request.url)

        # prevent duplicate subject in same course
        exists = db.subjects.find_one({
            "course": course,
            "name": {"$regex": f"^{name}$", "$options": "i"}
        })
        if exists:
            flash("Subject already exists for this course.", "error")
            return redirect(request.url)

        db.subjects.insert_one({
            "course": course,
            "name": name,
            "created_by": session["user_id"],
            "created_at": datetime.utcnow()
        })

        flash("Subject added successfully.", "success")
        return redirect("/notes")

    return render_template("admin_subject_create.html")


@app.route("/admin/subjects/<subject_id>/chapters", methods=["GET", "POST"])
@admin_required
def admin_manage_chapters(subject_id):
    subject = db.subjects.find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return "Subject not found", 404

    if request.method == "POST":
        title = request.form.get("title").strip()
        chapter_no = int(request.form.get("chapter_no"))

        db.chapters.insert_one({
            "subject_id": ObjectId(subject_id),
            "chapter_no": chapter_no,
            "title": title,
            "created_at": datetime.utcnow()
        })

        flash("Chapter added.", "success")
        return redirect(request.url)

    chapters = list(db.chapters.find(
        {"subject_id": ObjectId(subject_id)}
    ).sort("chapter_no", 1))

    return render_template(
        "admin_chapters.html",
        subject=subject,
        chapters=chapters
    )

@app.route("/admin/upload_video", methods=["GET", "POST"])
@admin_required
def admin_upload_video():

    if request.method == "POST":

        # ---------- BASIC FIELDS ----------
        user = db.users.find_one({"_id": ObjectId(session["user_id"])})
        course = user.get("course")

        # course = request.form.get("course")
        subject_id = request.form.get("subject_id")
        chapter_id = request.form.get("chapter_id")
        title = request.form.get("title")
        url = request.form.get("url")
        semester = request.form.get("semester")

        divisions = request.form.getlist("divisions")  # ✅ MULTI DIVISION

        if not divisions:
            flash("Please select at least one division.", "error")
            return redirect(request.url)

        # ---------- VALIDATE IDS ----------
        try:
            subject_oid = ObjectId(subject_id)
            chapter_oid = ObjectId(chapter_id)
        except:
            flash("Invalid subject or chapter.", "error")
            return redirect(request.url)

        subject = db.subjects.find_one({"_id": subject_oid})
        chapter = db.chapters.find_one({"_id": chapter_oid})

        if not subject or not chapter:
            flash("Subject or Chapter not found.", "error")
            return redirect(request.url)

        # ---------- INSERT VIDEO FIRST ----------
        video_result = db.videos.insert_one({
            "course": course,
            "subject_id": subject_oid,
            "chapter_id": chapter_oid,
            "title": title,
            "url": url,
            "semester": semester,
            "divisions": divisions,   # ✅ ARRAY
            "uploaded_by": session["user_id"],
            "uploaded_at": datetime.utcnow()
        })

        # ✅ THIS FIXES NameError
        video_id = video_result.inserted_id

        # ---------- EMAIL NOTIFICATION – VIDEO ----------
        # 📧 EMAIL NOTIFICATION – VIDEO
        for div in divisions:
            students = get_students_for_notification(course=course, division=div)

            if students:
                send_content_notification(
            students,
            title="🎥 New Video Lecture Uploaded",
            message=(
                "<h3>Hello {name},</h3>"
                "<p>A new video lecture has been uploaded.</p>"
                f"<p><b>Title:</b> {title}</p>"
                f"<p><b>Semester:</b> {semester}</p>"
                "<p>Login to <b>Zealians StudyHub</b> to watch the video.</p>"
            )
        )

        flash("Video uploaded successfully.", "success")
        return redirect(f"/videos/chapter/{chapter_id}")

    # ---------- GET ----------
    return render_template("admin_upload_video.html")




@app.route("/api/subjects/<course>")
@login_required
def api_subjects(course):
    subjects = list(db.subjects.find(
        {"course": course},
        {"_id": 1, "name": 1}
    ))
    return jsonify([
        {"id": str(s["_id"]), "name": s["name"]}
        for s in subjects
    ])



@app.route("/api/chapters/<subject_id>")
@login_required
def api_chapters(subject_id):
    try:
        subject_oid = ObjectId(subject_id)
    except:
        return jsonify([])

    chapters = list(
        db.chapters.find({"subject_id": subject_oid})
        .sort("chapter_no", 1)
    )

    return jsonify([
        {
            "_id": str(c["_id"]),
            "chapter_no": c["chapter_no"],
            "title": c["title"]
        }
        for c in chapters
    ])


# --------------------------#
# MCQ TESTS                 #
# --------------------------#
@app.route("/admin/mcq_tests")
@admin_required
def admin_mcq_tests():
    tests = list(db.mcq_tests.find().sort("created_at", -1))
    return render_template("admin_mcq_tests.html", tests=tests)


@app.route("/admin/mcq/create", methods=["GET", "POST"])
@admin_required
def admin_create_mcq():

    if request.method == "POST":
        user = db.users.find_one({"_id": ObjectId(session["user_id"])})
        course = user.get("course")
        # course = request.form.get("course")
        subject_id = request.form.get("subject_id")
        chapter_id = request.form.get("chapter_id")
        title = request.form.get("title")
        duration = int(request.form.get("duration"))
        # start_at = request.form.get("start_at")
        # end_at = request.form.get("end_at")
        divisions = request.form.getlist("divisions")  # checkbox values

        if not divisions:
            flash("Please select at least one division.", "error")
            return redirect(request.url)

        questions = []
        index = 0

        while True:
            q = request.form.get(f"question_{index}")
            if not q:
                break

            questions.append({
                "qno": index + 1,
                "question": q,
                "A": request.form.get(f"A_{index}"),
                "B": request.form.get(f"B_{index}"),
                "C": request.form.get(f"C_{index}"),
                "D": request.form.get(f"D_{index}"),
                "correct": request.form.get(f"correct_{index}")
            })
            index += 1

    

        db.mcq_tests.insert_one({
            "course": course,
            "subject_id": ObjectId(subject_id),
            "chapter_id": ObjectId(chapter_id),
            "title": title,
            "divisions": divisions,
            "duration": duration,
            "questions": questions,
           
            "created_by": session["user_id"],
            "created_at": datetime.utcnow()
        })
        
        # 📧 EMAIL NOTIFICATION – MCQ
        for div in divisions:
            students = get_students_for_notification(course=course, division=div)

            if students:
                send_content_notification(
            students,
            title="📝 New MCQ Test Available",
            message=(
                "<h3>Hello {name},</h3>"
                "<p>A new MCQ test is now available.</p>"
                f"<p><b>Test:</b> {title}</p>"
                f"<p><b>Duration:</b> {duration} minutes</p>"
                "<p>Please login to <b>Zealians StudyHub</b> to attempt the test.</p>"
            )
        )


        flash("MCQ Test created successfully.", "success")
        return redirect("/admin/mcq_tests")

    return render_template("admin_upload_mcq.html")
@app.route("/mcq")
@login_required
def mcq_subjects():

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    role = user.get("role")
    course = user.get("course")

    # 🔑 BOTH student AND faculty/admin are course-restricted
    subjects = list(
        db.subjects.find({"course": course}).sort("name", 1)
    )

    return render_template("mcq_subjects.html", subjects=subjects)


@app.route("/mcq/<subject_id>")
@login_required
def mcq_chapters(subject_id):

    subject = db.subjects.find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return "Subject not found", 404

    chapters = list(db.chapters.find(
        {"subject_id": subject["_id"]}
    ).sort("chapter_no", 1))

    return render_template(
        "mcq_chapters.html",
        subject=subject,
        chapters=chapters
    )





@app.route("/mcq_test/<test_id>", methods=["GET", "POST"])
@student_required
def mcq_test(test_id):
    test = db.mcq_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        return "Test not found."

    student_id = session.get("user_id")

    existing = db.mcq_results.find_one({"test_id": test_id, "student_id": student_id})
    if existing:
        return render_template("mcq_already_attempted.html", test=test, result=existing)

    if request.method == "POST":
        questions = test["questions"]
        total = len(questions)
        score = 0
        answers = []

        for idx, q in enumerate(questions):
            key = f"q_{idx}"
            selected = request.form.get(key)
            correct = q["correct"]

            if selected == correct:
                score += 1

            answers.append({
                "qno": q["qno"],
                "selected": selected,
                "correct": correct
            })

        student = db.users.find_one({"_id": ObjectId(student_id)}) or {}
        student_name = student.get("name", "Unknown")
        student_email = student.get("email", "unknown@example.com")
        roll_no = student.get("roll_no", "-")

        result_doc = {
            "test_id": test_id,
            "student_id": student_id,
            "student_name": student_name,
            "student_email": student_email,
            "roll_no": roll_no,
            "marks": score,
            "total": total,
            "submitted_at": datetime.utcnow(),
            "answers": answers
        }

        db.mcq_results.insert_one(result_doc)

        return render_template("mcq_result.html",
                               test=test,
                               result=result_doc)

    return render_template("mcq_test.html", test=test)


@app.route("/mcq_results")
@student_required
def mcq_results():
    student_id = session.get("user_id")
    results = list(db.mcq_results.find({"student_id": student_id}).sort("submitted_at", -1))

    for r in results:
        t = db.mcq_tests.find_one({"_id": ObjectId(r["test_id"])})
        r["test_title"] = t["title"] if t else "Deleted Test"

    return render_template("student_mcq_results.html", results=results)


@app.route("/mcq_results/view/<test_id>")
@student_required
def mcq_view_result(test_id):
    student_id = session.get("user_id")

    result = db.mcq_results.find_one({
        "test_id": test_id,
        "student_id": student_id
    })

    if not result:
        return "Result not found."

    test = db.mcq_tests.find_one({"_id": ObjectId(test_id)})

    return render_template("student_result_view.html",
                           test=test,
                           result=result)


@app.route("/admin/mcq_tests/<test_id>/results")
@admin_required
def admin_view_results(test_id):
    test = db.mcq_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        return "Test not found."

    results = list(db.mcq_results.find({"test_id": test_id}).sort("submitted_at", -1))

    return render_template(
        "admin_mcq_results.html",
        test=test,
        results=results
    )


@app.route("/admin/mcq_tests/<test_id>/export")
@admin_required
def export_mcq_results(test_id):
    test = db.mcq_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        return "Test not found."

    results = list(db.mcq_results.find({"test_id": test_id}))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Name", "Roll No", "Email", "Marks", "Total", "Submitted At"])

    for r in results:
        writer.writerow([
            r.get("student_name", ""),
            r.get("roll_no", ""),
            r.get("student_email", ""),
            r.get("marks", 0),
            r.get("total", 0),
            r.get("submitted_at").strftime("%Y-%m-%d %H:%M") if r.get("submitted_at") else ""
        ])

    output.seek(0)
    filename = f"mcq_results_{test_id}.csv"

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


# --------------------------#
# NOTES LIST + VIEW         #
# --------------------------#

@app.route("/notes")
@login_required
def notes_subjects():

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        return redirect("/login")

    role = user.get("role")
    course = user.get("course")

    # 🔑 BOTH student AND faculty/admin are course-restricted
    subjects = list(
        db.subjects.find({"course": course}).sort("name", 1)
    )

    return render_template(
        "notes_subjects.html",
        subjects=subjects,
        role=role
    )


@app.route("/view_note/<note_id>")
def view_note(note_id):
    note = db.notes.find_one({"_id": ObjectId(note_id)})
    if not note:
        return "File not found", 404

    rel_path = note["file_url"].lstrip("/")  # static/uploads/notes/filename
    ext = os.path.splitext(rel_path)[1].lower()

    # Absolute real path (static is OUTSIDE backend)
    abs_path = os.path.abspath(os.path.join(app.root_path, "..", rel_path))

    # ---------- CASE 1: PDF ----------
    if ext == ".pdf":
        if os.path.exists(abs_path):
            return send_file(abs_path)
        else:
            return f"PDF not found at: {abs_path}", 500

    # ---------- CASE 2: Convert DOCX/PPTX ----------
    if ext in [".docx", ".pptx"]:
        abs_input = abs_path
        out_dir = TEMP_DIR

        LIBREOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"

        # Convert
        result = subprocess.run(
            [LIBREOFFICE_PATH, "--headless", "--convert-to", "pdf",
             "--outdir", out_dir, abs_input],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print("LibreOffice Output:", result.stdout)
        print("LibreOffice Error:", result.stderr)

        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        output_pdf = os.path.join(out_dir, base_name + ".pdf")

        if not os.path.exists(output_pdf):
            return f"Converted PDF not found at: {output_pdf}", 500

        return send_file(output_pdf)

    # ---------- OTHER FILE TYPES ----------
    return send_file(abs_path)

# --------------------------#
# VIDEOS PAGE               #
# --------------------------#

@app.route("/videos")
@login_required
def video_subjects():

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        return redirect("/login")

    course = user.get("course")

    # ✅ BOTH student AND faculty/admin → course restricted
    subjects = list(
        db.subjects.find({"course": course}).sort("name", 1)
    )

    return render_template(
        "video_subjects.html",
        subjects=subjects
    )




@app.route("/videos/<subject_id>")
@login_required
def video_chapters(subject_id):

    subject = db.subjects.find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return "Subject not found", 404

    chapters = list(db.chapters.find(
        {"subject_id": subject["_id"]}
    ).sort("chapter_no", 1))

    return render_template(
        "video_chapters.html",
        subject=subject,
        chapters=chapters
    )


@app.route("/videos/<id>")
@login_required
def video_detail(id):

    video = db.videos.find_one({"_id": ObjectId(id)})
    if not video:
        return "Video not found", 404

    # Related videos from same chapter
    related = list(db.videos.find({
        "chapter_id": video["chapter_id"],
        "_id": {"$ne": ObjectId(id)}
    }))

    return render_template(
        "video_detail.html",
        video=video,
        related=related
    )



@app.route("/videos/watch/<video_id>")
@login_required
def watch_video(video_id):

    video = db.videos.find_one({"_id": ObjectId(video_id)})
    if not video:
        return "Video not found", 404

    chapter = db.chapters.find_one({"_id": video["chapter_id"]})
    subject = db.subjects.find_one({"_id": video["subject_id"]})

    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    role = user["role"]

    # --- Related videos (same chapter, same visibility rules) ---
    query = {"chapter_id": video["chapter_id"]}

    if role == "student":
        query.update({
        "course": user["course"],
        "$or": [
            {"divisions": user["division"]},
            {"divisions": {"$exists": False}}
        ]
    })


    related_videos = list(
        db.videos.find(query).sort("uploaded_at", -1)
    )

    mcqs = list(db.video_mcqs.find({"video_id": video["_id"]}))



    return render_template(
    "video_watch.html",
    video=video,
    chapter=chapter,
    subject=subject,
    related_videos=related_videos,
    mcqs=mcqs,
    role=role
)



# --------------------------#
# SIMPLE CHATBOT PAGE       #
# --------------------------#

@app.route("/test_gemini")
def test_gemini():
    try:
        response = gemini_client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents="Say hello in one sentence"
        )
        return response.text
    except Exception as e:
        return f"ERROR: {str(e)}"
    
@app.route("/list_models")
def list_models():
    models = gemini_client.models.list()
    return jsonify([m.name for m in models])



@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")


@app.route("/chatbot_api", methods=["POST"])
def chatbot_api():
    data = request.get_json()
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Please enter a question."})

    prompt = (
        "You are an AI Study Assistant for Zealians StudyHub.\n"
        "Answer ONLY MCA, MBA, IMCA, programming, database, exam, and academic questions.\n"
        "If the question is unrelated, politely refuse.\n\n"
        f"User: {user_msg}"
    )

    try:
        response = gemini_client.models.generate_content(
            model="models/gemini-flash-latest",
            contents=prompt
        )

        return jsonify({
            "reply": response.text.strip()
        })

    except Exception as e:
        print("❌ GEMINI ERROR:", e)
        return jsonify({
            "reply": "AI is temporarily busy. Please try again after a minute."
        })

if __name__ == "__main__":
    app.run(debug=True)

