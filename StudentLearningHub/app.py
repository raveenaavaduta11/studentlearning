from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_from_directory, abort,
)
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Category, Resource, CATEGORY_ICONS, CATEGORY_COLORS
from forms import (
    RegisterForm, LoginForm, ResourceForm, ChangePasswordForm,
    ForgotPasswordForm, ResetPasswordForm, EditProfileForm, CategoryEditForm,
)
import os
import uuid
import mimetypes
import zipfile
import re
import hashlib
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader
import cloudinary.utils

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

RESOURCES_PER_PAGE = 12


def create_app(config_overrides=None):
    app = Flask(__name__, template_folder="template", static_folder="static")
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    if os.getenv("VERCEL") and not app.config.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required on Vercel")
    db.init_app(app)
    csrf.init_app(app)

    # Disabled under pytest/TESTING so repeated test requests never get
    # throttled; real usage still gets brute-force protection on /auth.
    app.config.setdefault("RATELIMIT_ENABLED", not app.config.get("TESTING", False))
    limiter.init_app(app)

    if not os.getenv("VERCEL"):
        os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    with app.app_context():
        db.create_all()

    # ── Helpers ──────────────────────────────────────────────────────

    def allowed_file(filename):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in app.config["ALLOWED_UPLOAD_EXTENSIONS"]

    def cloudinary_enabled():
        return all(app.config.get(name) for name in (
            "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
        ))

    def cloudinary_resource_type(filename):
        return "image" if filename.rsplit(".", 1)[-1].lower() in {"png", "jpg", "jpeg", "gif"} else "raw"

    def cloudinary_download_url(resource_item):
        resource_type = cloudinary_resource_type(resource_item.file_name)
        extension = resource_item.file_name.rsplit(".", 1)[-1].lower() if "." in resource_item.file_name else None
        options = {
            "resource_type": resource_type,
            "type": "upload",
            "secure": True,
            "flags": f"attachment:{secure_filename(resource_item.file_name)}",
        }
        if extension:
            options["format"] = extension
        return cloudinary.utils.cloudinary_url(resource_item.stored_file_name, **options)[0]

    def local_file_directory(resource_item):
        if resource_item.file_path and os.path.isabs(resource_item.file_path):
            return os.path.dirname(resource_item.file_path)
        if resource_item.file_path and resource_item.file_path.replace("\\", "/").startswith("static/uploads/"):
            return os.path.join(app.root_path, "static", "uploads")
        return os.path.join(app.root_path, "instance", "uploads")

    def remove_stored_file(stored_file_name, file_name, file_path):
        if cloudinary_enabled() and file_path and file_path.startswith("http"):
            try:
                cloudinary.uploader.destroy(
                    stored_file_name,
                    resource_type=cloudinary_resource_type(file_name),
                    invalidate=True,
                )
            except Exception:
                app.logger.exception("Unable to remove Cloudinary file %s", stored_file_name)
            return

        local_path = stored_file_name if os.path.isabs(stored_file_name) else os.path.join(
            app.root_path, "instance", "uploads", stored_file_name,
        )
        if not os.path.exists(local_path):
            local_path = os.path.join(app.root_path, "static", "uploads", stored_file_name)
        if os.path.exists(local_path):
            os.remove(local_path)

    if cloudinary_enabled():
        cloudinary.config(
            cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
            api_key=app.config["CLOUDINARY_API_KEY"],
            api_secret=app.config["CLOUDINARY_API_SECRET"],
            secure=True,
        )

    def valid_file_signature(file, extension):
        """Reject files whose content clearly does not match their extension."""
        position = file.tell()
        header = file.read(16)
        file.seek(position)

        if extension == "pdf":
            return header.startswith(b"%PDF-")
        if extension in {"png", "jpg", "jpeg", "gif"}:
            image_signatures = {
                "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
                "jpg": header.startswith(b"\xff\xd8\xff"),
                "jpeg": header.startswith(b"\xff\xd8\xff"),
                "gif": header.startswith((b"GIF87a", b"GIF89a")),
            }
            return image_signatures[extension]
        if extension in {"doc", "ppt", "xls"}:
            return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        if extension == "rar":
            return header.startswith((b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00"))
        if extension in {"zip", "docx", "pptx", "xlsx"}:
            if not header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
                return False
            if extension == "zip":
                return True
            try:
                with zipfile.ZipFile(file) as archive:
                    names = set(archive.namelist())
                required = {
                    "docx": "word/",
                    "pptx": "ppt/",
                    "xlsx": "xl/",
                }[extension]
                return "[Content_Types].xml" in names and any(
                    name.startswith(required) for name in names
                )
            except (OSError, zipfile.BadZipFile):
                return False
            finally:
                file.seek(position)
        if extension == "txt":
            try:
                file.seek(position)
                file.read(4096).decode("utf-8")
                file.seek(position)
                return True
            except UnicodeDecodeError:
                file.seek(position)
                return False
        return True

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        user = db.session.get(User, user_id)
        if user is None:
            # Session refers to a user that no longer exists (e.g. DB reset).
            session.clear()
        return user

    def send_password_reset_email(user, reset_url):
        required_settings = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")
        if not all(app.config.get(name) for name in required_settings):
            app.logger.error("Password reset email is not configured")
            return False

        message = EmailMessage()
        message["Subject"] = "Reset your Student Learning Hub password"
        message["From"] = app.config["SMTP_FROM_EMAIL"]
        message["To"] = user.email
        message.set_content(
            f"Hello {user.name},\n\n"
            "Use the link below to reset your Student Learning Hub password. "
            "It expires in 1 hour.\n\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )

        try:
            smtp_host = app.config["SMTP_HOST"]
            smtp_port = app.config["SMTP_PORT"]
            smtp_context = ssl.create_default_context()
            if app.config["SMTP_USE_SSL"]:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=smtp_context) as server:
                    server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
                    server.send_message(message)
            else:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.ehlo()
                    if app.config["SMTP_USE_TLS"]:
                        server.starttls(context=smtp_context)
                        server.ehlo()
                    server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
                    server.send_message(message)
            return True
        except (OSError, smtplib.SMTPException):
            app.logger.exception("Unable to send password reset email to %s", user.email)
            return False

    @app.before_request
    def protect_legacy_uploads():
        if request.path.startswith("/static/uploads/") and current_user() is None:
            return redirect(url_for("auth"))

    def category_icon(category):
        if category.key in CATEGORY_ICONS:
            return CATEGORY_ICONS[category.key]
        words = re.findall(r"[A-Za-z0-9]+", category.name)
        initials = "".join(word[0] for word in words).upper()
        return (initials or category.name[:3]).upper()[:3]

    def category_color(category):
        if category.key in CATEGORY_COLORS:
            return CATEGORY_COLORS[category.key]
        colors = ("cat-cyan", "cat-blue", "cat-purple", "cat-green", "cat-orange", "cat-pink", "cat-yellow", "cat-teal")
        color_index = int(hashlib.sha256(category.key.encode("utf-8")).hexdigest(), 16) % len(colors)
        return colors[color_index]

    # Inject helpers into every template automatically.
    @app.context_processor
    def inject_globals():
        return {
            "user": current_user(),
            "category_icons": CATEGORY_ICONS,
            "category_colors": CATEGORY_COLORS,
            "category_icon": category_icon,
            "category_color": category_color,
            "footer_categories": Category.query.order_by(Category.name.asc()).limit(3).all(),
        }

    # ── Public routes ────────────────────────────────────────────────

    @app.route("/")
    @app.route("/index")
    def index():
        latest_resources = Resource.query.order_by(Resource.created_at.desc()).limit(5).all()
        categories_list = Category.query.order_by(Category.name.asc()).all()
        return render_template("index.html", latest_resources=latest_resources, categories_list=categories_list)

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/categories")
    def categories():
        categories_list = Category.query.order_by(Category.name.asc()).all()
        return render_template("categories.html", categories_list=categories_list)

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            subject = request.form.get("subject", "").strip()
            message = request.form.get("message", "").strip()

            if name and email and subject and message:
                flash("Thank you for your message! We'll get back to you soon.", "success")
                return redirect(url_for("contact"))
            else:
                flash("Please fill in all required fields.", "danger")

        return render_template("contact.html")

    # ── Authentication ───────────────────────────────────────────────

    @app.route("/auth", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"])
    def auth():
        login_form = LoginForm()
        register_form = RegisterForm()

        if request.method == "POST":
            if "register_submit" in request.form:
                if register_form.validate_on_submit():
                    email = register_form.email.data.strip().lower()
                    if User.query.filter_by(email=email).first():
                        flash("Email already exists.", "danger")
                    else:
                        user = User(
                            name=register_form.name.data.strip(),
                            email=email,
                            password=generate_password_hash(register_form.password.data),
                        )
                        db.session.add(user)
                        db.session.commit()
                        flash("Registration successful! Please log in.", "success")
                        return redirect(url_for("auth"))
            elif "login_submit" in request.form:
                if login_form.validate_on_submit():
                    email = login_form.email.data.strip().lower()
                    user = User.query.filter_by(email=email).first()
                    if user and check_password_hash(user.password, login_form.password.data):
                        session["user_id"] = user.id
                        session["user_name"] = user.name
                        session["user_role"] = user.role
                        flash("Login successful!", "success")
                        return redirect(url_for("dashboard"))
                    flash("Invalid email or password.", "danger")

        return render_template("auth.html", login_form=login_form, register_form=register_form)

    # ── Forgot / Reset Password ─────────────────────────────────────

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        form = ForgotPasswordForm()

        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            user = User.query.filter_by(email=email).first()
            if user:
                token = uuid.uuid4().hex
                user.reset_token = token
                user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
                db.session.commit()
                reset_url = url_for("reset_password", token=token, _external=True)
                if not send_password_reset_email(user, reset_url):
                    user.reset_token = None
                    user.reset_token_expires = None
                    db.session.commit()
            # Do not reveal whether the email exists or whether delivery succeeded.
            flash("If that email is registered, a reset link has been sent.", "info")

        return render_template("forgot_password.html", form=form)

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        user = User.query.filter_by(reset_token=token).first()
        if not user or (user.reset_token_expires and user.reset_token_expires < datetime.utcnow()):
            flash("Invalid or expired reset link.", "danger")
            return redirect(url_for("forgot_password"))

        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.password = generate_password_hash(form.new_password.data)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            flash("Password reset successful! Please log in with your new password.", "success")
            return redirect(url_for("auth"))

        return render_template("reset_password.html", form=form, token=token)

    # ── Resources ────────────────────────────────────────────────────

    @app.route("/resources")
    def resources():
        search_query = request.args.get("search", "").strip()
        category_key = request.args.get("category", "").strip()
        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1

        query = Resource.query
        if search_query:
            like_pattern = f"%{search_query}%"
            query = query.filter(
                db.or_(Resource.title.ilike(like_pattern), Resource.description.ilike(like_pattern))
            )
        if category_key:
            query = query.join(Category).filter(Category.key == category_key)
        query = query.order_by(Resource.created_at.desc())

        total_count = query.count()
        total_pages = max(1, (total_count + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE)
        page = min(page, total_pages)
        resources_list = query.offset((page - 1) * RESOURCES_PER_PAGE).limit(RESOURCES_PER_PAGE).all()

        return render_template(
            "resources.html",
            resources_list=resources_list,
            search_query=search_query,
            selected_category=category_key,
            categories_list=Category.query.order_by(Category.name.asc()).all(),
            page=page,
            total_pages=total_pages,
        )

    @app.route("/resource/<int:resource_id>")
    def resource(resource_id):
        user = current_user()
        if user is None:
            flash("Please login to view resource details.", "warning")
            return redirect(url_for("auth"))
        resource_item = db.session.get(Resource, resource_id)
        if resource_item is None:
            abort(404)
        return render_template("resource.html", resource=resource_item)

    @app.route("/resource/<int:resource_id>/download")
    def download_resource(resource_id):
        if current_user() is None:
            flash("Please login to download resources.", "warning")
            return redirect(url_for("auth"))
        resource_item = db.session.get(Resource, resource_id)
        if resource_item is None:
            abort(404)
        if resource_item.file_path and resource_item.file_path.startswith("http"):
            return redirect(cloudinary_download_url(resource_item))
        return send_from_directory(
            local_file_directory(resource_item),
            os.path.basename(resource_item.stored_file_name),
            as_attachment=True,
            download_name=resource_item.file_name,
        )

    @app.route("/resource/<int:resource_id>/preview")
    def preview_resource(resource_id):
        if current_user() is None:
            flash("Please login to preview resources.", "warning")
            return redirect(url_for("auth"))
        resource_item = db.session.get(Resource, resource_id)
        if resource_item is None:
            abort(404)
        if resource_item.file_path and resource_item.file_path.startswith("http"):
            return redirect(resource_item.file_path)
        mime_type = mimetypes.guess_type(resource_item.file_name)[0] or "application/octet-stream"
        return send_from_directory(
            local_file_directory(resource_item),
            os.path.basename(resource_item.stored_file_name),
            mimetype=mime_type,
            as_attachment=False,
        )

    @app.route("/resource/<int:resource_id>/delete", methods=["POST"])
    def delete_resource(resource_id):
        user = current_user()
        if user is None:
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth"))

        resource_item = db.session.get(Resource, resource_id)
        if resource_item is None:
            abort(404)

        if resource_item.uploaded_by != user.id and user.role != "admin":
            abort(403)

        remove_stored_file(resource_item.stored_file_name, resource_item.file_name, resource_item.file_path)

        db.session.delete(resource_item)
        db.session.commit()
        flash("Resource deleted.", "success")

        return redirect(url_for("admin") if user.role == "admin" else url_for("dashboard"))

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        user = current_user()
        if user is None:
            flash("Please login to upload a resource.", "warning")
            return redirect(url_for("auth"))

        form = ResourceForm()
        form.category.choices = [
            (category.key, category.name)
            for category in Category.query.order_by(Category.name.asc()).all()
        ]
        new_category_name = request.form.get("new_category_name", "").strip()
        new_category = None
        category_creation_error = False
        if new_category_name:
            new_category_key = re.sub(r"[^a-z0-9]+", "-", new_category_name.lower()).strip("-")[:50]
            if len(new_category_name) < 2 or not new_category_key:
                flash("New category names must contain at least two valid characters.", "danger")
                category_creation_error = True
            elif Category.query.filter(
                db.or_(Category.name.ilike(new_category_name), Category.key == new_category_key)
            ).first():
                flash("That category already exists. Select it from the category list.", "danger")
                category_creation_error = True
            else:
                new_category = Category(
                    key=new_category_key,
                    name=new_category_name,
                    description=f"Resources about {new_category_name}.",
                )
                form.category.choices.append((new_category.key, new_category.name))
                form.category.data = new_category.key

        if not category_creation_error and form.validate_on_submit():
            file = request.files.get("resource_file")
            original_filename = secure_filename(file.filename) if file and file.filename else ""
            if not original_filename:
                flash("Please choose a file to upload.", "danger")
                return render_template("upload.html", form=form)

            if len(original_filename) > 200:
                flash("The filename must be 200 characters or fewer.", "danger")
                return render_template("upload.html", form=form)

            if not allowed_file(original_filename):
                flash("That file type is not allowed.", "danger")
                return render_template("upload.html", form=form)

            ext = original_filename.rsplit(".", 1)[-1].lower()
            if not valid_file_signature(file, ext):
                flash("The file content does not match its extension.", "danger")
                return render_template("upload.html", form=form)
            stored_filename = f"{uuid.uuid4().hex}.{ext}"

            if cloudinary_enabled():
                try:
                    cloudinary_result = cloudinary.uploader.upload(
                        file,
                        resource_type=cloudinary_resource_type(original_filename),
                        folder="student-learning-hub",
                        public_id=uuid.uuid4().hex,
                    )
                except Exception:
                    app.logger.exception("Cloudinary upload failed for %s", original_filename)
                    flash("The file could not be uploaded to cloud storage. Please try again.", "danger")
                    return render_template("upload.html", form=form)
                stored_filename = cloudinary_result["public_id"]
                stored_file_path = cloudinary_result["secure_url"]
            else:
                if os.getenv("VERCEL"):
                    flash("Cloudinary must be configured before uploading on Vercel.", "danger")
                    return render_template("upload.html", form=form)
                upload_dir = os.path.join(app.root_path, "instance", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, stored_filename))
                stored_file_path = os.path.join(upload_dir, stored_filename)

            category = Category.query.filter_by(key=form.category.data).first()
            if new_category is not None:
                category = new_category
                db.session.add(category)
                db.session.flush()
            if category is None:
                remove_stored_file(stored_filename, original_filename, stored_file_path)
                flash("Please select an available category.", "danger")
                return render_template("upload.html", form=form)

            resource_item = Resource(
                title=form.title.data.strip(),
                description=form.description.data.strip(),
                file_name=original_filename,
                stored_file_name=stored_filename,
                file_path=stored_file_path,
                category_id=category.id,
                uploaded_by=user.id,
            )
            db.session.add(resource_item)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                remove_stored_file(stored_filename, original_filename, stored_file_path)
                app.logger.exception("Unable to save resource metadata for %s", original_filename)
                flash("The resource could not be saved. Please try again.", "danger")
                return render_template("upload.html", form=form)
            flash("Resource uploaded successfully!", "success")
            return redirect(url_for("dashboard"))

        return render_template("upload.html", form=form)

    # ── Dashboard & Account ──────────────────────────────────────────

    @app.route("/dashboard")
    def dashboard():
        user = current_user()
        if user is None:
            return redirect(url_for("auth"))

        dashboard_search = request.args.get("search", "").strip()
        resources_query = Resource.query.filter_by(uploaded_by=user.id)
        if dashboard_search:
            like_pattern = f"%{dashboard_search}%"
            resources_query = resources_query.filter(
                db.or_(Resource.title.ilike(like_pattern), Resource.description.ilike(like_pattern))
            )
        user_resources = resources_query.order_by(Resource.created_at.desc()).all()
        password_form = ChangePasswordForm()
        profile_form = EditProfileForm(obj=user)
        return render_template(
            "dashboard.html", user_resources=user_resources,
            password_form=password_form, profile_form=profile_form,
            dashboard_search=dashboard_search,
        )

    @app.route("/account/password", methods=["POST"])
    def change_password():
        user = current_user()
        if user is None:
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth"))

        password_form = ChangePasswordForm()
        if password_form.validate_on_submit():
            if not check_password_hash(user.password, password_form.current_password.data):
                flash("Current password is incorrect.", "danger")
            else:
                user.password = generate_password_hash(password_form.new_password.data)
                db.session.commit()
                flash("Password changed successfully.", "success")
        else:
            for error_messages in password_form.errors.values():
                for error_message in error_messages:
                    flash(error_message, "danger")

        return redirect(url_for("dashboard"))

    @app.route("/account/profile", methods=["POST"])
    def edit_profile():
        user = current_user()
        if user is None:
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth"))

        form = EditProfileForm()
        if form.validate_on_submit():
            new_email = form.email.data.strip().lower()
            # Check if new email is taken by another user.
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != user.id:
                flash("That email is already in use.", "danger")
            else:
                user.name = form.name.data.strip()
                user.email = new_email
                session["user_name"] = user.name
                db.session.commit()
                flash("Profile updated successfully.", "success")
        else:
            for error_messages in form.errors.values():
                for msg in error_messages:
                    flash(msg, "danger")

        return redirect(url_for("dashboard"))

    # ── Admin ────────────────────────────────────────────────────────

    @app.route("/admin")
    def admin():
        user = current_user()
        if user is None or user.role != "admin":
            return redirect(url_for("auth"))

        page = request.args.get("page", 1, type=int)
        resource_search = request.args.get("resource_search", "").strip()
        resource_category = request.args.get("resource_category", "").strip()
        user_search = request.args.get("user_search", "").strip()
        if page < 1:
            page = 1

        resources_query = Resource.query
        if resource_search:
            like_pattern = f"%{resource_search}%"
            resources_query = resources_query.join(User).filter(
                db.or_(
                    Resource.title.ilike(like_pattern),
                    Resource.description.ilike(like_pattern),
                    User.name.ilike(like_pattern),
                )
            )
        if resource_category:
            resources_query = resources_query.join(Category).filter(Category.key == resource_category)
        resources_query = resources_query.order_by(Resource.created_at.desc())
        total_count = resources_query.count()
        total_pages = max(1, (total_count + RESOURCES_PER_PAGE - 1) // RESOURCES_PER_PAGE)
        page = min(page, total_pages)
        resources_list = resources_query.offset((page - 1) * RESOURCES_PER_PAGE).limit(RESOURCES_PER_PAGE).all()

        users_query = User.query.order_by(User.created_at.desc())
        if user_search:
            like_pattern = f"%{user_search}%"
            users_query = users_query.filter(
                db.or_(User.name.ilike(like_pattern), User.email.ilike(like_pattern))
            )
        users = users_query.all()
        categories_list = Category.query.order_by(Category.id.asc()).all()
        return render_template(
            "admin.html", resources_list=resources_list, users=users, categories=categories_list,
            total_resource_count=Resource.query.count(), page=page, total_pages=total_pages,
            resource_search=resource_search, resource_category=resource_category,
            user_search=user_search,
        )

    @app.route("/admin/category/<int:category_id>/edit", methods=["POST"])
    def edit_category(category_id):
        admin_user = current_user()
        if admin_user is None or admin_user.role != "admin":
            abort(403)

        category = db.session.get(Category, category_id)
        if category is None:
            abort(404)

        form = CategoryEditForm()
        if form.validate_on_submit():
            name = form.name.data.strip()
            duplicate = Category.query.filter(
                Category.id != category.id,
                db.or_(Category.name.ilike(name), Category.key == re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50]),
            ).first()
            if duplicate:
                flash("That category already exists.", "danger")
            else:
                category.name = name
                category.description = (form.description.data or "").strip() or f"Resources about {name}."
                db.session.commit()
                flash("Category updated successfully.", "success")
        else:
            flash("Please enter a valid category name.", "danger")
        return redirect(url_for("admin"))

    @app.route("/admin/category/<int:category_id>/delete", methods=["POST"])
    def delete_category(category_id):
        admin_user = current_user()
        if admin_user is None or admin_user.role != "admin":
            abort(403)

        category = db.session.get(Category, category_id)
        if category is None:
            abort(404)
        if category.resources:
            flash("This category still has resources. Delete or move those resources first.", "danger")
            return redirect(url_for("admin"))

        category_name = category.name
        db.session.delete(category)
        db.session.commit()
        flash(f"Category '{category_name}' deleted.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
    def delete_user(user_id):
        admin = current_user()
        if admin is None or admin.role != "admin":
            abort(403)

        target = db.session.get(User, user_id)
        if target is None:
            abort(404)
        if target.id == admin.id:
            flash("You cannot delete your own account.", "danger")
            return redirect(url_for("admin"))

        for res in target.resources:
            remove_stored_file(res.stored_file_name, res.file_name, res.file_path)
            db.session.delete(res)

        db.session.delete(target)
        db.session.commit()
        flash(f"User '{target.name}' and their resources have been deleted.", "success")
        return redirect(url_for("admin"))

    # ── Logout ───────────────────────────────────────────────────────

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("auth"))

    # ── Error handlers ───────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            "error.html", code=404,
            title="Page Not Found", message="The page you're looking for doesn't exist.",
        ), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template(
            "error.html", code=403,
            title="Access Forbidden", message="You don't have permission to do that.",
        ), 403

    @app.errorhandler(429)
    def rate_limited_error(error):
        return render_template(
            "error.html", code=429,
            title="Too Many Attempts", message="Please wait a bit before trying again.",
        ), 429

    @app.errorhandler(500)
    def server_error(error):
        return render_template(
            "error.html", code=500,
            title="Something Went Wrong", message="An unexpected error occurred. Please try again.",
        ), 500

    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="127.0.0.1", port=5000)
