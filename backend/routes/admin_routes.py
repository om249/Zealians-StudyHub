from flask import Blueprint, render_template, request, redirect, url_for, current_app, session, flash
from backend.helpers.file_helper import save_uploaded_file
import os

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
def admin_dashboard():
    # TODO: Check admin session
    return render_template("admin_dashboard.html")

@admin_bp.route("/upload", methods=["GET", "POST"])
def admin_upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == '':
            flash('No file selected', 'warning')
            return redirect(url_for("admin.admin_upload"))
        
        saved_filename = save_uploaded_file(file, current_app.config.get("UPLOAD_FOLDER", "static/uploads"))
        if not saved_filename:
            flash('Invalid file type or failed to save', 'danger')
        else:
            flash(f'File uploaded: {saved_filename}', 'success')
        return redirect(url_for("admin.admin_upload"))
    
    return render_template("upload.html")
