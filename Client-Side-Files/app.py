from dataclasses import fields
from re import match

from flask import Flask, request, jsonify, render_template, abort, redirect
# Flask: Initializes the Flask app
# request: Handles incoming data (form or JSON)
# jsonify: Returns a response in JSON format
# render_template: Renders HTML templates like home.html or login.html
# abort: Used to return error responses like 403 Forbidden
# redirect: Redirects users (e.g., after login or logout)

from flask_mysqldb import MySQL
# Connects Flask with MYSQL database

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
# LoginManager: Initializes session management
# login_user: Logs in a user after checking credentials
# logout_user: Logs out the current user
# login_required: Decorator to protect routes (only accessible to logged-in users)
# current_user: Tracks the user who is currently logged in
# UserMixin: Provides default implementations for user model methods

from werkzeug.security import generate_password_hash, check_password_hash
# generate_password_hash: Converts a plain password into a secure hashed format
# check_password_hash: Validates a login password against the stored hash

from functools import wraps
# Used to build custom decorators, such as role-based access control (@role_required)

app = Flask(__name__)
app.secret_key = 'skiddy00' # don't share or hardcode in public code repositories

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'skiddy00' #replace with actual DB password
app.config['MYSQL_DB'] = '407_courtyards'
mysql = MySQL(app)

login_manager = LoginManager() # Creates an instance to manage user logins and sessions
login_manager.init_app(app) # Initializes Flask-Login with your Flask app instance
login_manager.login_view = 'login' # Redirect to login page if not authenticated or access protected page w/o login
# ^ allows you to use session based authentication and protect specific routes using @login_required



def is_admin():
    return current_user.role in ['Admin']

def role_required(*roles): #decorator function that allows you to define which roles can access a specific route. Can use it above any route to control access like: @role_required('Admin') or @role_required('Admin', 'Customer')
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                return abort(403) # Forbidden
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# User Loader Class
# User Class inherits from UserMixin, which provides default implementations for authentication methods. Stores details such as id, name, email, password, and role
# load_user(user_id): required function for Flask-Login that tells app how to load a user object from the session ID.
class User(UserMixin):
    def __init__(self, id, name, email, password, role):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role

#Function is automatically called by Flask_login whenever the user session is active
@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("Select * FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()
    if user_data:
        return User(*user_data)
    return None 

# Login Route. POST retrieves email and password from form. GET renders the login form
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cur.fetchone()
        cur.close()

        if user_data and check_password_hash(user_data[3], password): #user_data[3] is the password field in the database
            user = User(*user_data)
            login_user(user)
            return redirect('/')
        else:
            return render_template('index.html', error="Invalid credentials")
    return render_template('index.html')

# Logout Route: Logs out the current user and redirects to the login page. @login_required ensures only logged-in users can access this route. logiut_user() clears the session
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# Home Page Route
@app.route('/')
@login_required
def home():
    if current_user.role == 'Admin':
        return render_template('Admindash.html')
    elif current_user.role == 'Resident':
        return render_template('Res_Dash2.html')
    elif current_user.role == 'Staff':
        return render_template('maintenance.html')


# Additional simple page routes so template links resolve when clicked
@app.route('/payments')
@login_required
def payments():
    return render_template('payments.html')


@app.route('/work_order')
@login_required
def work_order():
    return render_template('work_order.html')


@app.route('/schedule')
@login_required
def schedule():
    return render_template('schedule.html')


@app.route('/apply')
def apply():
    return render_template('apply.html')


@app.route('/deposit')
def deposit():
    return render_template('deposit.html')


@app.route('/floorplan')
def floorplan():
    return render_template('floorplan.html')


@app.route('/lease_info')
@login_required
def lease_info():
    return render_template('Lease_info.html')


@app.route('/maint_req')
@login_required
def maint_req():
    return render_template('Maint_Req.html')


@app.route('/maintenance')
@login_required
def maintenance_page():
    return render_template('maintenance.html')


@app.route('/pay_rent')
@login_required
def pay_rent():
    return render_template('Pay_rent.html')


@app.route('/res_dash2')
@login_required
def res_dash2():
    return render_template('Res_Dash2.html')


@app.route('/status')
def status_page():
    return render_template('status.html')

""" #Add User (Admin Only)
@app.route('/user', methods=['POST'])
@login_required
@role_required('Admin') # Only users with the 'Admin' role can access this route
def add_user():
    if request.is_json:
        data = request.get_json() # Get data as JSON
        name = data['name']
        email = data['email']
        role = data.get('role', 'Admin') # Default role is Admin if not provided
        password = generate_password_hash(data.get('password', 'test123')) # Hash the password before storing it in the database. No PW provided defaults to "test123"
        
        cur = mysql.connection.cursor()
        # SQL query string
        sql = "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)"
        # Execute the SQL command
        cur.execute(sql, (name, email, password, role))
        # Commit the changes in the database
        mysql.connection.commit()
        # Close the cursor
        cur.close()
        return jsonify(message="User added successfully"), 201
    return jsonify(error="Error in submission"), 400

# View Users (All Logged-in Users). Returns user ID, name, and role for everyone. Only users with admin roles ('Professor', 'TA', 'Admin") can also see email address. Customers will not see email field in response
@app.route('/users', methods=['GET'])
@login_required
def get_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, role FROM users") # Ensure the fields match what's expected in the frontend
    users = cur.fetchall()
    cur.close()
    # Convert query results to a list of dicts to jsonify them easily
    user_dicts = []
    for user in users:
        user_dict = {'id': user[0], 'name': user[1], 'role': user[3]} # Always include ID, name, and role
        if is_admin(): # Only include email if the current user is an admin
            user_dict['email'] = user[2]
        user_dicts.append(user_dict)
    return jsonify(user_dicts)

# Delete User (Admin Only)
@app.route('/user/<int:id>', methods=['DELETE'])
@login_required
@role_required('Admin') # Only users with the 'Admin' role can access this route
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", [id])
    mysql.connection.commit()
    cur.close()
    return jsonify(message="User deleted successfully") """

# Add debugging statement
if __name__ == '__main__': # app only runs when executed directly
    app.run(debug=True) # enables auto-reload and better error messages during development


""" #Ensure Flask serves HTML file when accessing the ROOT URL
@app.route('/')
def home():
    return render_template('index.html') """



""" #Create User (C in CRUD)
@app.route('/user', methods=['POST'])
def add_user():
    if request.is_json:
        data = request.get_json() # Get data as JSON
        name = data['name']
        email = data['email']
        
        cur = mysql.connection.cursor()
        # SQL query string
        sql = "INSERT INTO users (name, email) VALUES (%s, %s)"
        # Execute the SQL command
        cur.execute(sql, (name, email))
        # Commit the changes in the database
        mysql.connection.commit()
        # Close the cursor
        cur.close()
        # Insert into database or process data here
        return jsonify(message="User added successfully"), 201
    else:
        return jsonify(error="Error in submission"), 400

#Read Users (R in CRUD)
@app.route('/users', methods=['GET'])
def get_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email FROM users") # Ensure the fields match what's expected in the frontend
    users = cur.fetchall()
    cur.close()
    # Convert query results to a list of dicts to jsonify them easily
    user_dicts = [{'id': user[0], 'name': user[1], 'email': user[2]} for user in users]
    return jsonify(user_dicts)

#Delete User (D in CRUD)
@app.route('/user/<int:id>', methods=['DELETE'])
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", [id])
    mysql.connection.commit()
    cur.close()
    return jsonify(message="User deleted successfully")
 """
# Add debugging statement
if __name__ == '__main__':
    app.run(debug=True)

