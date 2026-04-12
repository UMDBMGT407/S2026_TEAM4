import os
import secrets
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from MySQLdb import IntegrityError
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = "skiddy00 "  # Replace with a secure secret in production.
# MySQL configuration
app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "127.0.0.1")
app.config["MYSQL_PORT"] = int(os.getenv("MYSQL_PORT", "3306"))
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "skiddy00")
app.config["MYSQL_DB"] = os.getenv("MYSQL_DB", "407_courtyards")
mysql = MySQL(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

ROLE_LABELS = {
    "admin": "Admin",
    "resident": "Resident",
    "staff": "Maintenance",
    "prospect": "Prospect",
}
ROLE_OPTIONS = ("admin", "resident", "staff", "prospect")


def canonical_role(role):
    """Match DB/form casing to ROLE_LABELS keys (Python role checks are case-sensitive)."""
    if role is None:
        return role
    r = str(role).strip()
    if not r:
        return r
    if r in ROLE_LABELS:
        return r
    lower = r.lower()
    for key in ROLE_LABELS:
        if key.lower() == lower:
            return key
    return r


USER_DEPENDENCIES = (
    ("leases", "resident_user_id", "lease records"),
    ("payments", "resident_user_id", "payment records"),
    ("maintenance_requests", "resident_user_id", "maintenance requests"),
    ("work_orders", "assigned_staff_id", "assigned work orders"),
    ("staff_schedule", "staff_user_id", "staff schedule entries"),
)


class User(UserMixin):
    def __init__(self, id, name, email, password, role):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role


def is_admin():
    return current_user.is_authenticated and current_user.role == "Admin"


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


def admin_staff_context():
    is_admin_view = current_user.role == "Admin"
    return {
        "is_admin_view": is_admin_view,
        "role_label": ROLE_LABELS.get(current_user.role, current_user.role or ""),
        "dashboard_endpoint": "home" if is_admin_view else "maintenance_page",
        "show_payments_link": is_admin_view,
        "work_order_label": "Work Orders" if is_admin_view else "My Work Orders",
        "back_endpoint": "home" if is_admin_view else "maintenance_page",
    }


def user_delete_blockers(user_id):
    blockers = []

    if int(user_id) == int(current_user.id):
        blockers.append("You cannot delete the account you are currently using.")

    cur = mysql.connection.cursor()
    for table, column, label in USER_DEPENDENCIES:
        cur.execute(
            f"SELECT COUNT(*) FROM `{table}` WHERE `{column}` = %s",
            (user_id,),
        )
        if cur.fetchone()[0]:
            blockers.append(f"This user has related {label}.")
    cur.close()
    return blockers


def _latest_application_row_for_email(email):
    """Latest row: (application_code, submitted_at) for applicant_email, or None."""
    if email is None or not str(email).strip():
        return None
    normalized = str(email).strip().lower()
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "SELECT application_code, submitted_at FROM applications "
            "WHERE LOWER(TRIM(applicant_email)) = %s "
            "ORDER BY submitted_at DESC LIMIT 1",
            (normalized,),
        )
        row = cur.fetchone()
    except Exception:
        row = None
    finally:
        cur.close()
    if not row or not row[0]:
        return None
    return row


def _application_code_for_email(email):
    """Latest applications.application_code for the given email (matches apply submit)."""
    row = _latest_application_row_for_email(email)
    return row[0] if row else None


def _deposit_page_context(email):
    """Values for deposit.html: code from DB, $100 deposit, due = submitted_at + 30 days."""
    deposit_amount = 100
    application_code = None
    due_date_display = None
    row = _latest_application_row_for_email(email)
    if row:
        application_code = row[0] or None
        submitted_at = row[1]
        if submitted_at is not None:
            if isinstance(submitted_at, datetime):
                base = submitted_at
            elif isinstance(submitted_at, date):
                base = datetime.combine(submitted_at, datetime.min.time())
            else:
                base = None
            if base is not None:
                due = base + timedelta(days=30)
                due_date_display = due.strftime("%B %d, %Y")
    return {
        "application_code": application_code,
        "deposit_amount": deposit_amount,
        "due_date_display": due_date_display,
    }


def serialize_user(user_row):
    user_id, name, email, role = user_row
    blockers = user_delete_blockers(user_id)
    return {
        "id": user_id,
        "name": name,
        "email": email,
        "role": role,
        "can_delete": not blockers,
        "delete_reason": " ".join(blockers),
    }


@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, name, email, password, role FROM users WHERE id = %s",
        (user_id,),
    )
    user_data = cur.fetchone()
    cur.close()
    if user_data:
        uid, name, email, password, role = user_data
        return User(uid, name, email, password, canonical_role(role))
    return None


@app.errorhandler(403)
def forbidden(_error):
    return render_template("403.html"), 403


@app.route("/access-denied-exit")
def access_denied_exit():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, name, email, password, role FROM users WHERE LOWER(TRIM(email)) = %s",
            (email,),
        )
        user_data = cur.fetchone()
        cur.close()

        if user_data and check_password_hash(user_data[3], password):
            uid, name, em, pw_hash, role = user_data
            login_user(User(uid, name, em, pw_hash, canonical_role(role)))
            return redirect(url_for("home"))

        return render_template("index.html", error="Invalid credentials"), 401

    return render_template("index.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    if current_user.role == "admin":
        return render_template("Admindash.html")
    if current_user.role == "resident":
        return render_template("Res_Dash2.html")
    if current_user.role == "staff":
        return render_template("maintenance.html")
    if current_user.role == "prospect":
        application_code = _application_code_for_email(current_user.email)
        return render_template("status.html", application_code=application_code)
    abort(403)


@app.route("/users", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def users():
    if request.method == "GET":
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, email, role FROM users ORDER BY id")
        users_data = cur.fetchall()
        cur.close()
        return jsonify([serialize_user(user_row) for user_row in users_data])

    payload = request.get_json(silent=True) or request.form
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "").strip()

    if not all([name, email, password, role]):
        return jsonify({"error": "All fields are required."}), 400

    if role not in ROLE_OPTIONS:
        return jsonify({"error": "Please choose a valid role."}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "A user with that email already exists."}), 409

    hashed_password = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
        (name, email, hashed_password, role),
    )
    new_user_id = cur.lastrowid
    mysql.connection.commit()
    cur.close()

    return (
        jsonify(
            {
                "message": "User added successfully.",
                "user": serialize_user((new_user_id, name, email, role)),
            }
        ),
        201,
    )


@app.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
@role_required("Admin")
def delete_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, role FROM users WHERE id = %s", (user_id,))
    user_row = cur.fetchone()
    cur.close()

    if not user_row:
        return jsonify({"error": "User not found."}), 404

    blockers = user_delete_blockers(user_id)
    if blockers:
        return jsonify({"error": " ".join(blockers)}), 409

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "User deleted successfully."})


@app.route("/payments")
@login_required
@role_required("Admin")
def payments():
    return render_template("payments.html")


@app.route("/work_order")
@login_required
@role_required("Admin", "Staff")
def work_order():
    context = admin_staff_context()
    context["page_title"] = (
        "Courtyards Work Orders"
        if context["is_admin_view"]
        else "Courtyards My Work Orders"
    )
    return render_template("work_order.html", **context)


@app.route("/schedule")
@login_required
@role_required("Admin", "Staff")
def schedule():
    context = admin_staff_context()
    context["page_title"] = "Admin Schedule" if context["is_admin_view"] else "Schedule"
    return render_template("schedule.html", **context)


@app.route("/apply")
def apply():
    return render_template("apply.html")


def _apply_validation_errors(form, files):
    """Return list of human-readable errors, or empty list if OK."""
    errors = []
    first = (form.get("first_name") or "").strip()
    last = (form.get("last_name") or "").strip()
    email = (form.get("email") or "").strip()
    password = (form.get("password") or "").strip()
    student_id = (form.get("student_id") or "").strip()
    phone = (form.get("phone") or "").strip()
    floor_plan = (form.get("floor_plan") or "").strip()
    move_in = (form.get("move_in_date") or "").strip()
    emergency_name = (form.get("emergency_contact_name") or "").strip()
    emergency_phone = (form.get("emergency_contact_phone") or "").strip()

    if not first:
        errors.append("First Name")
    if not last:
        errors.append("Last Name")
    if not email:
        errors.append("Email")
    if not password:
        errors.append("Password")
    if not student_id:
        errors.append("Student ID")
    if not phone:
        errors.append("Phone Number")
    if not floor_plan:
        errors.append("Preferred Floor plan/Unit")
    if not move_in:
        errors.append("Move-In Date")
    if not emergency_name:
        errors.append("Emergency Contact Name")
    if not emergency_phone:
        errors.append("Emergency Contact Phone")

    id_upload = files.get("id_upload")
    if not id_upload or not (id_upload.filename or "").strip():
        errors.append("Upload ID")

    return errors


def _generate_application_code():
    """Public application id: letter A plus four random digits (e.g. A7381)."""
    return "A" + f"{secrets.randbelow(10000):04d}"


def _unique_application_code(cursor):
    """Avoid collision with an existing applications.application_code."""
    for _ in range(200):
        code = _generate_application_code()
        cursor.execute(
            "SELECT 1 FROM applications WHERE application_code = %s LIMIT 1",
            (code,),
        )
        if cursor.fetchone() is None:
            return code
    raise RuntimeError("Could not allocate a unique application_code")


def _mysql_table_columns(cursor, table_name):
    """Column names for the current database's table (lowercase keys for matching)."""
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table_name,),
    )
    return {row[0] for row in cursor.fetchall()}


def _applications_insert(cursor, app_columns, values_by_key):
    """INSERT only columns that exist on `applications` (e.g. optional id_document_path)."""
    order = [
        "application_code",
        "applicant_name",
        "applicant_email",
        "applicant_phone",
        "floorplan_id",
        "desired_move_in",
        "student_id",
        "emergency_name",
        "emergency_phone",
        "applicant_notes",
        "id_document_path",
        "status",
        "submitted_at",
    ]
    keys = [k for k in order if k in app_columns]
    if not keys:
        raise RuntimeError("applications table has no recognized columns for apply flow")
    cols_sql = ", ".join(f"`{k}`" for k in keys)
    placeholders = ", ".join(["%s"] * len(keys))
    params = [values_by_key[k] for k in keys]
    cursor.execute(
        f"INSERT INTO applications ({cols_sql}) VALUES ({placeholders})",
        params,
    )


@app.route("/apply/submit", methods=["POST"])
def apply_submit():
    errors = _apply_validation_errors(request.form, request.files)
    if errors:
        return (
            jsonify(
                {
                    "error": "Please complete all required fields: "
                    + ", ".join(errors),
                }
            ),
            400,
        )

    first = (request.form.get("first_name") or "").strip()
    last = (request.form.get("last_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    student_id = (request.form.get("student_id") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    floor_plan = (request.form.get("floor_plan") or "").strip()
    move_in = (request.form.get("move_in_date") or "").strip()
    emergency_name = (request.form.get("emergency_contact_name") or "").strip()
    emergency_phone = (request.form.get("emergency_contact_phone") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    applicant_notes = notes if notes else None
    applicant_full_name = f"{first} {last}".strip()

    id_file = request.files.get("id_upload")

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM floorplans WHERE name = %s", (floor_plan,))
    fp_row = cur.fetchone()
    if not fp_row:
        cur.close()
        return jsonify({"error": "Selected floor plan was not found in the database."}), 400
    floorplan_id = fp_row[0]

    upload_dir = os.path.join(app.root_path, "instance", "application_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_fn = secure_filename(id_file.filename) or "id_upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_fn}"
    id_path = os.path.join(upload_dir, stored_name)
    id_file.save(id_path)
    id_document_rel = os.path.join("instance", "application_uploads", stored_name)

    hashed_password = generate_password_hash(password)
    submitted_at = datetime.now()

    try:
        app_columns = _mysql_table_columns(cur, "applications")
    except Exception:
        app_columns = {
            "application_code",
            "applicant_name",
            "applicant_email",
            "applicant_phone",
            "floorplan_id",
            "desired_move_in",
            "student_id",
            "emergency_name",
            "emergency_phone",
            "applicant_notes",
            "status",
            "submitted_at",
        }

    if "application_code" not in app_columns:
        cur.close()
        try:
            os.remove(id_path)
        except OSError:
            pass
        return (
            jsonify(
                {
                    "error": "The applications table must have an application_code column. "
                    "Run the SQL in sql/applications_schema.sql (or add that column) and retry.",
                }
            ),
            500,
        )

    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (applicant_full_name, email, hashed_password, "prospect"),
        )
        new_user_id = cur.lastrowid

        app_values = {
            "application_code": _unique_application_code(cur),
            "applicant_name": applicant_full_name,
            "applicant_email": email,
            "applicant_phone": phone,
            "floorplan_id": floorplan_id,
            "desired_move_in": move_in,
            "student_id": student_id,
            "emergency_name": emergency_name,
            "emergency_phone": emergency_phone,
            "applicant_notes": applicant_notes,
            "id_document_path": id_document_rel,
            "status": "pending",
            "submitted_at": submitted_at,
        }
        _applications_insert(cur, app_columns, app_values)
        mysql.connection.commit()

        cur.execute(
            "SELECT id, name, email, password, role FROM users WHERE id = %s",
            (new_user_id,),
        )
        logged_in_row = cur.fetchone()
        if logged_in_row:
            uid, name, em, pw_hash, role = logged_in_row
            login_user(User(uid, name, em, pw_hash, canonical_role(role)))
    except IntegrityError:
        mysql.connection.rollback()
        try:
            os.remove(id_path)
        except OSError:
            pass
        cur.close()
        return (
            jsonify(
                {
                    "error": "An account with this email already exists. "
                    "Please log in or use a different email.",
                }
            ),
            409,
        )
    except Exception:
        mysql.connection.rollback()
        try:
            os.remove(id_path)
        except OSError:
            pass
        cur.close()
        raise
    cur.close()

    return jsonify({"ok": True, "redirect": url_for("deposit")})


@app.route("/deposit")
@login_required
def deposit():
    ctx = _deposit_page_context(current_user.email)
    return render_template(
        "deposit.html",
        application_code=ctx["application_code"],
        deposit_amount=ctx["deposit_amount"],
        due_date_display=ctx["due_date_display"],
    )


@app.route("/floorplan")
def floorplan():
    return render_template("floorplan.html")


@app.route("/lease_info")
@login_required
@role_required("Resident")
def lease_info():
    return render_template("Lease_info.html")


@app.route("/maint_req")
@login_required
@role_required("Resident")
def maint_req():
    return render_template("Maint_Req.html")


@app.route("/maintenance")
@login_required
@role_required("Staff")
def maintenance_page():
    return render_template("maintenance.html")


@app.route("/pay_rent")
@login_required
@role_required("Resident")
def pay_rent():
    return render_template("Pay_rent.html")


@app.route("/res_dash2")
@login_required
@role_required("Resident")
def res_dash2():
    return render_template("Res_Dash2.html")


@app.route("/status")
@login_required
def status_page():
    if current_user.role != "prospect":
        return redirect(url_for("home"))
    application_code = _application_code_for_email(current_user.email)
    return render_template("status.html", application_code=application_code)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
