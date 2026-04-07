import os
from functools import wraps

from flask import Flask, abort, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash


app = Flask(__name__)
app.secret_key = "skiddy00"  # Replace with a secure secret in production.

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
    "Admin": "Admin",
    "Resident": "Resident",
    "Staff": "Maintenance",
}


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
