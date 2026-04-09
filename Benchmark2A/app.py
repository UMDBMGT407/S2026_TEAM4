import os
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
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
    "Admin": "Admin",
    "Resident": "Resident",
    "Staff": "Maintenance",
}
ROLE_OPTIONS = ("Admin", "Resident", "Staff")
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
        "role_label": ROLE_LABELS[current_user.role],
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
        return User(*user_data)
    return None


@app.errorhandler(403)
def forbidden(_error):
    return render_template("403.html"), 403


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, name, email, password, role FROM users WHERE email = %s",
            (email,),
        )
        user_data = cur.fetchone()
        cur.close()

        if user_data and check_password_hash(user_data[3], password):
            login_user(User(*user_data))
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
    if current_user.role == "Admin":
        return render_template("Admindash.html")
    if current_user.role == "Resident":
        return render_template("Res_Dash2.html")
    if current_user.role == "Staff":
        return render_template("maintenance.html")
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


@app.route("/deposit")
def deposit():
    return render_template("deposit.html")


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
def status_page():
    return render_template("status.html")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
