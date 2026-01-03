from flask import Blueprint, render_template, current_app, send_from_directory, request, redirect, session, url_for
import os

user_bp = Blueprint("user", __name__)

@user_bp.route("/notes")
def notes_page():
    # TODO: Fetch notes from database
    notes = []
    return render_template("notes.html", notes=notes)

@user_bp.route("/videos")
def videos_page():
    # TODO: Fetch videos from database
    videos = []
    return render_template("videos.html", videos=videos)

@user_bp.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@user_bp.route("/dashboard")
def dashboard():
    # TODO: Fetch user stats
    return render_template("dashboard.html")

@user_bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # TODO: Authenticate user
        pass
    return render_template('login.html')

@user_bp.route("/signup", methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        # TODO: Create new user
        pass
    return render_template('signup.html')

@user_bp.route("/logout")
def logout():
    # TODO: Clear session
    return redirect(url_for('home'))
