import os
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from MySQLdb import IntegrityError
from MySQLdb.cursors import DictCursor
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
app.secret_key = " "  # Replace with a secure secret in production.
# MySQL configuration
app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "127.0.0.1")
app.config["MYSQL_PORT"] = int(os.getenv("MYSQL_PORT", "3306"))
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", " ")
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


def db_all(sql, params=()):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return [dict(row) for row in rows]


def db_one(sql, params=()):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None


def money(value):
    if value is None:
        return "$0.00"
    amount = float(value)
    return f"${amount:,.2f}"


def date_display(value, fmt="%m/%d/%Y"):
    if not value:
        return "--"
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, date):
        return value.strftime(fmt)
    return str(value)


def iso_date(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def serializable_amount(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def unique_code(cursor, table, column, prefix, digits=4):
    for _ in range(200):
        code = prefix + f"{secrets.randbelow(10 ** digits):0{digits}d}"
        cursor.execute(
            f"SELECT 1 FROM `{table}` WHERE `{column}` = %s LIMIT 1",
            (code,),
        )
        if cursor.fetchone() is None:
            return code
    raise RuntimeError(f"Could not allocate a unique {prefix} code")


def is_admin():
    return current_user.is_authenticated and current_user.role == "admin"


def role_required(*roles):
    allowed_roles = {canonical_role(role) for role in roles}

    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if (
                not current_user.is_authenticated
                or canonical_role(current_user.role) not in allowed_roles
            ):
                abort(403)
            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


def admin_staff_context():
    is_admin_view = current_user.role == "admin"
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


def _latest_application_for_email(email):
    if email is None or not str(email).strip():
        return None
    row = db_one(
        "SELECT a.application_code, a.status, a.submitted_at, a.desired_move_in, "
        "a.applicant_name, a.applicant_email, a.applicant_phone, fp.name AS floorplan_name "
        "FROM applications a "
        "JOIN floorplans fp ON a.floorplan_id = fp.id "
        "WHERE LOWER(TRIM(a.applicant_email)) = %s "
        "ORDER BY a.submitted_at DESC LIMIT 1",
        (str(email).strip().lower(),),
    )
    if not row:
        return None
    submitted_at = row.get("submitted_at")
    return {
        "application_code": row.get("application_code"),
        "status": row.get("status") or "Pending",
        "submitted_at": date_display(submitted_at),
        "due_date": date_display(
            submitted_at + timedelta(days=30), "%B %d, %Y"
        )
        if isinstance(submitted_at, (date, datetime))
        else None,
        "desired_move_in": date_display(row.get("desired_move_in")),
        "applicant_name": row.get("applicant_name"),
        "applicant_email": row.get("applicant_email"),
        "applicant_phone": row.get("applicant_phone"),
        "floorplan_name": row.get("floorplan_name"),
    }


def _floorplan_rows():
    rows = db_all(
        "SELECT fp.id, fp.name, fp.rent, fp.bedrooms, fp.bathrooms, fp.size, "
        "SUM(CASE WHEN u.status = 'Available' THEN 1 ELSE 0 END) AS available_units "
        "FROM floorplans fp "
        "LEFT JOIN units u ON u.floorplan_id = fp.id "
        "GROUP BY fp.id, fp.name, fp.rent, fp.bedrooms, fp.bathrooms, fp.size "
        "ORDER BY fp.id"
    )
    for row in rows:
        row["rent_display"] = money(row.get("rent")).replace(".00", "")
        row["summary"] = (
            f"{row.get('bedrooms')} Bed / {row.get('bathrooms')} Bath - "
            f"{row.get('size'):,} sq. ft"
        )
        row["available_units"] = int(row.get("available_units") or 0)
    return rows


def _resident_lease(user_id):
    row = db_one(
        "SELECT l.id, l.lease_code, l.start_date, l.end_date, l.monthly_rent, "
        "l.security_deposit, l.status, u.building, u.unit_number, fp.name AS floorplan_name "
        "FROM leases l "
        "JOIN units u ON l.unit_id = u.id "
        "JOIN floorplans fp ON u.floorplan_id = fp.id "
        "WHERE l.resident_user_id = %s "
        "ORDER BY FIELD(l.status, 'Active', 'Pending', 'Ended'), l.end_date DESC LIMIT 1",
        (user_id,),
    )
    if not row:
        return None
    return {
        **row,
        "monthly_rent_value": float(row.get("monthly_rent") or 0),
        "monthly_rent_display": money(row.get("monthly_rent")),
        "security_deposit_display": money(row.get("security_deposit")),
        "start_date_display": date_display(row.get("start_date")),
        "end_date_display": date_display(row.get("end_date")),
        "end_date_short": date_display(row.get("end_date"), "%m/%d"),
    }


def _resident_payments(user_id, limit=None):
    sql = (
        "SELECT p.id, p.payment_code, p.lease_id, p.amount, p.method, p.status, "
        "p.payment_date, p.confirmation_number, p.notes, l.lease_code "
        "FROM payments p "
        "JOIN leases l ON p.lease_id = l.id "
        "WHERE p.resident_user_id = %s "
        "ORDER BY p.payment_date DESC, p.id DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = db_all(sql, (user_id,))
    for row in rows:
        row["amount_value"] = float(row.get("amount") or 0)
        row["amount_display"] = money(row.get("amount"))
        row["payment_date_display"] = date_display(row.get("payment_date"))
        row["payment_date_short"] = date_display(row.get("payment_date"), "%m/%d")
    return rows


def _resident_maintenance_requests(user_id, limit=None):
    sql = (
        "SELECT request_code, category, issue_title, description, priority, status, created_at "
        "FROM maintenance_requests "
        "WHERE resident_user_id = %s "
        "ORDER BY created_at DESC, id DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = db_all(sql, (user_id,))
    for row in rows:
        row["created_display"] = date_display(row.get("created_at"), "%m/%d")
    return rows


def _resident_dashboard_context(user_id):
    lease = _resident_lease(user_id)
    payments = _resident_payments(user_id, limit=5)
    requests = _resident_maintenance_requests(user_id, limit=4)
    unpaid_total = sum(
        payment["amount_value"]
        for payment in payments
        if payment.get("status") in {"Pending", "Failed"}
    )
    monthly_rent = lease["monthly_rent_value"] if lease else 0
    balance_due = unpaid_total or monthly_rent
    last_payment = next(
        (payment for payment in payments if payment.get("status") == "Paid"), None
    )
    return {
        "lease": lease,
        "balance_due": money(balance_due),
        "monthly_rent": money(monthly_rent),
        "utility_charges": money(95),
        "parking_fee": money(40),
        "last_payment_date": last_payment["payment_date_display"] if last_payment else "--",
        "next_due_date": "05/01/2026",
        "next_due_short": "05/01",
        "maintenance_requests": requests,
    }


def _payment_rows():
    rows = db_all(
        "SELECT p.id, p.payment_code, p.amount, p.method, p.status, p.payment_date, "
        "p.confirmation_number, p.notes, l.lease_code, u.building, u.unit_number, "
        "r.name AS resident_name, r.email AS resident_email "
        "FROM payments p "
        "JOIN leases l ON p.lease_id = l.id "
        "JOIN units u ON l.unit_id = u.id "
        "JOIN users r ON p.resident_user_id = r.id "
        "ORDER BY p.payment_date DESC, p.id DESC"
    )
    for row in rows:
        row["amount_value"] = float(row.get("amount") or 0)
        row["amount"] = money(row.get("amount"))
        row["date"] = date_display(row.get("payment_date"))
        row["resident"] = row.get("resident_name")
        row["phone"] = row.get("resident_email")
        row["leaseId"] = row.get("lease_code")
        row["unit"] = row.get("unit_number")
        row["confirmation"] = row.get("confirmation_number") or "--"
    return rows


def _payments_context():
    rows = _payment_rows()
    total_collected = sum(
        row["amount_value"] for row in rows if row.get("status") == "Paid"
    )
    summary = {
        "total_collected": money(total_collected),
        "overdue_accounts": sum(
            1 for row in rows if row.get("status") in {"Pending", "Failed"}
        ),
        "failed_payments": sum(1 for row in rows if row.get("status") == "Failed"),
    }
    return {
        "payments": rows,
        "payments_by_code": {row["payment_code"]: row for row in rows},
        "payments_summary": summary,
        "building_options": sorted({row["building"] for row in rows if row.get("building")}),
        "first_payment": rows[0] if rows else None,
    }


def _work_order_rows(staff_id=None, limit=None):
    params = []
    where = ""
    if staff_id is not None:
        where = "WHERE wo.assigned_staff_id = %s "
        params.append(staff_id)
    sql = (
        "SELECT wo.id AS db_id, wo.work_order_code, wo.scheduled_date, wo.time_window, "
        "wo.status, wo.notes, mr.request_code, mr.category, mr.issue_title, "
        "mr.description, mr.priority, mr.created_at, mr.attachment_name, "
        "u.building, u.unit_number, r.name AS resident_name, r.email AS resident_email, "
        "s.name AS assigned_staff_name "
        "FROM work_orders wo "
        "JOIN maintenance_requests mr ON wo.request_id = mr.id "
        "JOIN leases l ON mr.lease_id = l.id "
        "JOIN units u ON l.unit_id = u.id "
        "JOIN users r ON mr.resident_user_id = r.id "
        "JOIN users s ON wo.assigned_staff_id = s.id "
        f"{where}"
        "ORDER BY wo.scheduled_date DESC, wo.id DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = db_all(sql, tuple(params))
    for row in rows:
        scheduled_date = row.get("scheduled_date")
        created_at = row.get("created_at")
        row["id"] = row.get("work_order_code")
        row["building"] = row.get("building") or ""
        row["unit"] = row.get("unit_number") or ""
        row["resident"] = row.get("resident_name") or "Resident"
        row["phone"] = row.get("resident_email") or "--"
        row["issue"] = row.get("issue_title") or row.get("category") or "Work order"
        row["requested"] = date_display(created_at, "%m/%d/%y")
        row["due"] = date_display(scheduled_date, "%m/%d/%y")
        row["scheduled_date_iso"] = iso_date(scheduled_date)
        row["scheduled_date"] = iso_date(scheduled_date)
        row["created_at"] = date_display(created_at)
        row["attachment"] = row.get("attachment_name") or "No attachment"
        row["description"] = row.get("description") or ""
    return rows


def _work_order_summary(rows):
    return {
        "assigned_open": sum(
            1 for row in rows if row.get("status") in {"Open", "Assigned", "In Progress"}
        ),
        "due_today": sum(
            1 for row in rows if row.get("scheduled_date_iso") == date.today().isoformat()
        ),
        "closed": sum(1 for row in rows if row.get("status") == "Closed"),
    }


def _schedule_context():
    shifts = db_all(
        "SELECT ss.shift_date, ss.start_time, ss.end_time, ss.assignment_note, u.name AS staff_name "
        "FROM staff_schedule ss "
        "JOIN users u ON ss.staff_user_id = u.id "
        "ORDER BY ss.shift_date, ss.start_time"
    )
    shift_rows = []
    for shift in shifts:
        staff = shift.get("staff_name") or "Staff"
        slug = "".join(ch.lower() for ch in staff if ch.isalnum()) or "staff"
        shift_rows.append(
            {
                "date": iso_date(shift.get("shift_date")),
                "staff": staff,
                "shift": f"{shift.get('start_time')} - {shift.get('end_time')}",
                "className": f"staff-{slug}",
                "note": shift.get("assignment_note") or "",
            }
        )
    work_orders = _work_order_rows()
    return {
        "schedule_shifts": shift_rows,
        "schedule_work_orders": work_orders,
        "staff_options": sorted({shift["staff"] for shift in shift_rows}),
        "schedule_summary": {
            "staff_scheduled": len({shift["staff"] for shift in shift_rows}),
            "work_orders": len(work_orders),
            "open_shifts": len(shift_rows),
        },
    }


def _maintenance_dashboard_context(staff_id):
    rows = _work_order_rows(staff_id, limit=10)
    return {
        "work_orders": rows,
        "work_orders_by_code": {row["id"]: row for row in rows},
        "summary": _work_order_summary(rows),
        "first_order": rows[0] if rows else None,
    }


def _active_lease_row_for_user(user_id):
    return db_one(
        "SELECT id, lease_code, monthly_rent "
        "FROM leases "
        "WHERE resident_user_id = %s "
        "ORDER BY FIELD(status, 'Active', 'Pending', 'Ended'), end_date DESC LIMIT 1",
        (user_id,),
    )


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
    role = canonical_role(current_user.role)
    if role == "admin":
        return render_template("Admindash.html")
    if role == "resident":
        return render_template(
            "Res_Dash2.html", **_resident_dashboard_context(current_user.id)
        )
    if role == "staff":
        return render_template(
            "maintenance.html", **_maintenance_dashboard_context(current_user.id)
        )
    if role == "prospect":
        application = _latest_application_for_email(current_user.email)
        return render_template(
            "status.html",
            application=application,
            application_code=application["application_code"] if application else None,
        )
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
    role = canonical_role(payload.get("role") or "")

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
    return render_template("payments.html", **_payments_context())


@app.route("/payments/<payment_code>/status", methods=["POST"])
@login_required
@role_required("Admin")
def update_payment_status(payment_code):
    payload = request.get_json(silent=True) or request.form
    status = (payload.get("status") or "").strip()
    notes = (payload.get("notes") or "").strip()
    allowed_statuses = {"Pending", "Paid", "Failed", "Resolved"}
    if status not in allowed_statuses:
        return jsonify({"error": "Please choose a valid payment status."}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id FROM payments WHERE payment_code = %s",
        (payment_code,),
    )
    if cur.fetchone() is None:
        cur.close()
        return jsonify({"error": "Payment not found."}), 404
    cur.execute(
        "UPDATE payments SET status = %s, notes = %s WHERE payment_code = %s",
        (status, notes or None, payment_code),
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Payment updated.", "status": status})


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
    staff_id = None if context["is_admin_view"] else current_user.id
    rows = _work_order_rows(staff_id=staff_id)
    context.update(
        {
            "work_orders": rows,
            "work_orders_by_code": {row["id"]: row for row in rows},
            "building_options": sorted(
                {row["building"] for row in rows if row.get("building")}
            ),
        }
    )
    return render_template("work_order.html", **context)


@app.route("/work_order/update", methods=["POST"])
@login_required
@role_required("Admin", "Staff")
def work_order_update():
    payload = request.get_json(silent=True) or request.form
    work_order_code = (payload.get("work_order_code") or "").strip()
    status = (payload.get("status") or "").strip()
    notes = (payload.get("notes") or "").strip()
    scheduled_date = (payload.get("scheduled_date") or "").strip() or None
    time_window = (payload.get("time_window") or "").strip() or None
    allowed_statuses = {"Open", "Assigned", "In Progress", "Closed"}

    if not work_order_code:
        return jsonify({"error": "Missing work order code."}), 400
    if status and status not in allowed_statuses:
        return jsonify({"error": "Please choose a valid work order status."}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, request_id, assigned_staff_id FROM work_orders "
        "WHERE work_order_code = %s",
        (work_order_code,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"error": "Work order not found."}), 404

    if canonical_role(current_user.role) == "staff" and int(row[2]) != int(current_user.id):
        cur.close()
        abort(403)

    assignments = []
    params = []
    if status:
        assignments.append("status = %s")
        params.append(status)
        assignments.append("closed_at = %s")
        params.append(datetime.now() if status == "Closed" else None)
    if notes:
        assignments.append("notes = %s")
        params.append(notes)
    if canonical_role(current_user.role) == "admin":
        if scheduled_date:
            assignments.append("scheduled_date = %s")
            params.append(scheduled_date)
        if time_window:
            assignments.append("time_window = %s")
            params.append(time_window)

    if not assignments:
        cur.close()
        return jsonify({"error": "No work order updates were provided."}), 400

    params.append(work_order_code)
    cur.execute(
        f"UPDATE work_orders SET {', '.join(assignments)} WHERE work_order_code = %s",
        tuple(params),
    )
    if status:
        cur.execute(
            "UPDATE maintenance_requests mr "
            "JOIN work_orders wo ON mr.id = wo.request_id "
            "SET mr.status = %s "
            "WHERE wo.work_order_code = %s",
            (status, work_order_code),
        )
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Work order updated.", "status": status})


@app.route("/schedule")
@login_required
@role_required("Admin", "Staff")
def schedule():
    context = admin_staff_context()
    context["page_title"] = "Admin Schedule" if context["is_admin_view"] else "Schedule"
    context.update(_schedule_context())
    return render_template("schedule.html", **context)


@app.route("/apply")
def apply():
    return render_template("apply.html", floorplans=_floorplan_rows())


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
    """Column names as returned by MySQL (casing may vary by server / definition)."""
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table_name,),
    )
    return {row[0] for row in cursor.fetchall()}


def _applications_column_sql_name(app_columns, logical_name):
    """Resolve logical insert key to actual table column name (case-insensitive)."""
    want = logical_name.lower()
    for col in app_columns:
        if col.lower() == want:
            return col
    return None


def _applications_insert(cursor, app_columns, values_by_key):
    """INSERT only columns that exist on `applications` (e.g. optional app_supp_docs)."""
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
        "app_id",
        "app_supp_docs",
        "id_document_path",
        "status",
        "submitted_at",
    ]
    resolved = []
    for logical in order:
        sql_col = _applications_column_sql_name(app_columns, logical)
        if sql_col is None and logical == "app_supp_docs":
            for legacy in ("app_supporting_docs", "app_supporting_doc"):
                sql_col = _applications_column_sql_name(app_columns, legacy)
                if sql_col is not None:
                    break
        if sql_col is None or logical not in values_by_key:
            continue
        resolved.append((sql_col, logical))
    if not resolved:
        raise RuntimeError("applications table has no recognized columns for apply flow")
    cols_sql = ", ".join(f"`{sql_col}`" for sql_col, _ in resolved)
    placeholders = ", ".join(["%s"] * len(resolved))
    params = [values_by_key[logical] for _, logical in resolved]
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

    upload_dir = os.path.join(
        app.root_path, "static", "images", "application_uploads"
    )
    os.makedirs(upload_dir, exist_ok=True)
    safe_fn = secure_filename(id_file.filename) or "id_upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_fn}"
    id_path = os.path.join(upload_dir, stored_name)
    id_file.save(id_path)
    id_document_rel = os.path.join("images", "application_uploads", stored_name)

    saved_absolute_paths = [id_path]
    supporting_rel_paths = []
    supporting_files = list(request.files.getlist("supporting_docs"))
    supporting_files.extend(request.files.getlist("supporting_doc"))
    for sup in supporting_files:
        if not sup:
            continue
        fn = getattr(sup, "filename", None) or ""
        if not str(fn).strip() and not getattr(sup, "content_length", None):
            continue
        sup_safe = secure_filename(fn) or "document"
        sup_stored = f"{uuid.uuid4().hex}_{sup_safe}"
        sup_abs = os.path.join(upload_dir, sup_stored)
        sup.save(sup_abs)
        saved_absolute_paths.append(sup_abs)
        supporting_rel_paths.append(
            os.path.join("images", "application_uploads", sup_stored)
        )
    app_supp_docs_val = ";".join(supporting_rel_paths) if supporting_rel_paths else None

    def _cleanup_uploaded_files():
        for path in saved_absolute_paths:
            try:
                os.remove(path)
            except OSError:
                pass

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
            "app_id",
            "app_supp_docs",
            "status",
            "submitted_at",
        }

    if _applications_column_sql_name(app_columns, "application_code") is None:
        cur.close()
        _cleanup_uploaded_files()
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
            "app_id": id_document_rel,
            "app_supp_docs": app_supp_docs_val,
            "id_document_path": id_document_rel,
            "status": "Pending",
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
        _cleanup_uploaded_files()
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
        _cleanup_uploaded_files()
        cur.close()
        raise
    cur.close()

    return jsonify({"ok": True, "redirect": url_for("deposit")})


@app.route("/deposit")
@login_required
def deposit():
    if canonical_role(current_user.role) != "prospect":
        return redirect(url_for("home"))
    ctx = _deposit_page_context(current_user.email)
    application = _latest_application_for_email(current_user.email)
    return render_template(
        "deposit.html",
        application_code=ctx["application_code"],
        deposit_amount=ctx["deposit_amount"],
        due_date_display=ctx["due_date_display"],
        application=application,
    )


@app.route("/deposit/pay", methods=["POST"])
@login_required
@role_required("Prospect")
def deposit_pay():
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id FROM applications "
        "WHERE LOWER(TRIM(applicant_email)) = %s "
        "ORDER BY submitted_at DESC LIMIT 1",
        (current_user.email.strip().lower(),),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"error": "Application not found."}), 404
    cur.execute(
        "UPDATE applications SET status = %s, notes = %s WHERE id = %s",
        ("Deposit Paid", "Deposit payment submitted online.", row[0]),
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Deposit marked as paid.", "redirect": url_for("status_page")})


@app.route("/floorplan")
def floorplan():
    return render_template("floorplan.html", floorplans=_floorplan_rows())


@app.route("/lease_info")
@login_required
@role_required("Resident")
def lease_info():
    return render_template("Lease_info.html", lease=_resident_lease(current_user.id))


@app.route("/maint_req")
@login_required
@role_required("Resident")
def maint_req():
    return render_template(
        "Maint_Req.html",
        recent_requests=_resident_maintenance_requests(current_user.id, limit=5),
    )


@app.route("/maintenance/request", methods=["POST"])
@login_required
@role_required("Resident")
def maintenance_request_submit():
    category_raw = (request.form.get("category") or "").strip()
    priority_raw = (request.form.get("priority") or "").strip()
    location = (request.form.get("location") or "").strip()
    access_time = (request.form.get("access_time") or "").strip()
    description = (request.form.get("description") or "").strip()

    category_labels = {
        "plumbing": "Plumbing",
        "electrical": "Electrical",
        "hvac": "HVAC",
        "appliance": "Appliance",
        "pest": "Pest Control",
        "other": "Other",
    }
    priority_labels = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "urgent": "Urgent",
    }
    category = category_labels.get(category_raw.lower())
    priority = priority_labels.get(priority_raw.lower())
    if not category or not priority or not description:
        return jsonify({"error": "Category, priority, and description are required."}), 400

    lease = _active_lease_row_for_user(current_user.id)
    if not lease:
        return jsonify({"error": "No active lease was found for this resident."}), 400

    attachment_name = None
    attachment = request.files.get("attachment")
    if attachment and (attachment.filename or "").strip():
        upload_dir = os.path.join(
            app.root_path, "static", "images", "maintenance_uploads"
        )
        os.makedirs(upload_dir, exist_ok=True)
        safe_fn = secure_filename(attachment.filename) or "maintenance_upload"
        attachment_name = f"{uuid.uuid4().hex}_{safe_fn}"
        attachment.save(os.path.join(upload_dir, attachment_name))

    issue_title = category
    if location:
        issue_title = f"{category} - {location}"
    if access_time:
        description = f"{description}\nPreferred access time: {access_time}"

    cur = mysql.connection.cursor()
    request_code = unique_code(cur, "maintenance_requests", "request_code", "MR", 3)
    cur.execute(
        "INSERT INTO maintenance_requests "
        "(request_code, resident_user_id, lease_id, category, issue_title, description, "
        "priority, status, created_at, attachment_name) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'Open', %s, %s)",
        (
            request_code,
            current_user.id,
            lease["id"],
            category,
            issue_title,
            description,
            priority,
            datetime.now(),
            attachment_name,
        ),
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Maintenance request submitted.", "request_code": request_code})


@app.route("/maintenance")
@login_required
@role_required("Staff")
def maintenance_page():
    return render_template(
        "maintenance.html", **_maintenance_dashboard_context(current_user.id)
    )


@app.route("/pay_rent")
@login_required
@role_required("Resident")
def pay_rent():
    return render_template("Pay_rent.html", **_resident_dashboard_context(current_user.id))


@app.route("/pay_rent/submit", methods=["POST"])
@login_required
@role_required("Resident")
def pay_rent_submit():
    lease = _active_lease_row_for_user(current_user.id)
    if not lease:
        return jsonify({"error": "No active lease was found for this resident."}), 400

    method_raw = (request.form.get("method") or "").strip().lower()
    method = "Bank Transfer" if "bank" in method_raw else "Card"
    account_to_pay = (request.form.get("account_to_pay") or "").strip()
    last4 = (request.form.get("last4") or "").strip()[-4:]
    billing_zip = (request.form.get("billing_zip") or "").strip()
    if not method_raw or not account_to_pay or not last4 or not billing_zip:
        return jsonify({"error": "Please complete the payment form before submitting."}), 400

    cur = mysql.connection.cursor()
    payment_code = unique_code(cur, "payments", "payment_code", "P", 4)
    confirmation = "CNF" + f"{secrets.randbelow(100000):05d}"
    cur.execute(
        "INSERT INTO payments "
        "(payment_code, lease_id, resident_user_id, amount, method, status, "
        "payment_date, confirmation_number, notes) "
        "VALUES (%s, %s, %s, %s, %s, 'Pending', %s, %s, %s)",
        (
            payment_code,
            lease["id"],
            current_user.id,
            lease["monthly_rent"],
            method,
            date.today(),
            confirmation,
            f"Submitted online for {account_to_pay}; ending {last4}.",
        ),
    )
    mysql.connection.commit()
    cur.close()
    return jsonify(
        {
            "message": "Payment submitted.",
            "payment_code": payment_code,
            "confirmation": confirmation,
        }
    )


@app.route("/res_dash2")
@login_required
@role_required("Resident")
def res_dash2():
    return render_template("Res_Dash2.html", **_resident_dashboard_context(current_user.id))


@app.route("/status")
@login_required
def status_page():
    if canonical_role(current_user.role) != "prospect":
        return redirect(url_for("home"))
    application = _latest_application_for_email(current_user.email)
    return render_template(
        "status.html",
        application=application,
        application_code=application["application_code"] if application else None,
    )


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
