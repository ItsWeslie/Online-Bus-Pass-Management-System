from datetime import timedelta
import io
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session,send_file,make_response
import mysql.connector
import random
import secrets
import hashlib
from functools import wraps
from flask import Response
import qrcode
from io import BytesIO


# Flask App Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(16)  # Secure session key
app.config["SESSION_COOKIE_SECURE"] = True  # For HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7) 

# Database Configuration
DB_USER = "root"
DB_PASSWORD = "SamWeslie@14"
DB_HOST = "localhost"
DB_NAME = "bus_pass_db"

# Database Connection
def get_db_connection():
    return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)

# Ensure Tables Exist
def user_tables():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            phone VARCHAR(15) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('user', 'admin') NOT NULL DEFAULT 'user'
        )
    """)

    

    connection.commit()
    cursor.close()
    connection.close()

user_tables()

def bus_pass_table():

    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bus_pass (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            age INT NOT NULL,
            gender ENUM('Male', 'Female', 'Other') NOT NULL,
            phone VARCHAR(15) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            bus_route VARCHAR(255) NOT NULL,
            father_name VARCHAR(100) NOT NULL,
            parent_phone VARCHAR(15) NOT NULL,
            address TEXT NOT NULL,
            blood_group ENUM('A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-') NOT NULL,
            pass_id VARCHAR(10) UNIQUE NOT NULL,
            status_application ENUM('Pending', 'Approved', 'Rejected') NOT NULL DEFAULT 'Pending',  
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fees INT NOT NULL DEFAULT 0,
            boarding_point VARCHAR(255) NOT NULL,
            course_title VARCHAR(255) NOT NULL  
        )
    """)
    
    connection.commit()
    cursor.close()
    connection.close()

bus_pass_table()

# bus route creation table
def bus_route_table():
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS bus_routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    route_name VARCHAR(255) NOT NULL UNIQUE,  
    start_location VARCHAR(255) NOT NULL,    
    end_location VARCHAR(255) NOT NULL,      
    stops TEXT NOT NULL,    
     fees INT NOT NULL DEFAULT 0,                 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    connection.commit()
    cursor.close()
    connection.close()


bus_route_table()    


def payment_table():
    
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- User's full name
    email VARCHAR(120) NOT NULL,  -- User's email
    phone VARCHAR(15) NOT NULL,  -- User's phone number
    amount INT NOT NULL,  -- Payment amount
    pass_id VARCHAR(10) NOT NULL,  -- Reference to the bus pass ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Payment timestamp
    payment_status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
    FOREIGN KEY (pass_id) REFERENCES bus_pass(pass_id) ON DELETE CASCADE,
    FOREIGN KEY (email) REFERENCES bus_pass(email) ON DELETE CASCADE
);""")

    connection.commit()
    cursor.close()
    connection.close()

payment_table()        

# Home Page
@app.route('/')
def home():
    return render_template("index.html")

# Login Required Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": "Unauthorized access. Please log in."}), 401
            flash("You must be logged in to access this page.", "error")
            session["next"] = request.path
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    data = request.form
    full_name, phone, email, password, confirm_password = (
        data.get("full_name", "").strip(),
        data.get("phone", "").strip(),
        data.get("email", "").strip(),
        data.get("password", "").strip(),
        data.get("confirm_password", "").strip()
    )

    if not all([full_name, phone, email, password, confirm_password]):
        return jsonify({"status": "error", "message": "All fields are required!"}), 400

    if password != confirm_password:
        return jsonify({"status": "error", "message": "Passwords do not match!"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s OR phone = %s", (email, phone))
    if cursor.fetchone():
        cursor.close()
        connection.close()
        return jsonify({"status": "error", "message": "Email or phone already registered!"}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    cursor.execute("INSERT INTO users (full_name, phone, email, password_hash) VALUES (%s, %s, %s, %s)",
                   (full_name, phone, email, password_hash))
    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"status": "success", "message": "Registration successful!"}), 201

# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.form
    email, password = data.get("email", "").strip(), data.get("password", "").strip()

    if not email or not password:
        return jsonify({"status": "error", "message": "All fields are required!"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, full_name, role, password_hash FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    if not user or hashlib.sha256(password.encode()).hexdigest() != user[3]:
        return jsonify({"status": "error", "message": "Invalid email or password!"}), 400

    session["user_id"] = user[0]
    session["user_name"] = user[1]
    session["user_role"] = user[2]  # Store user role
    
    if user[2]== "admin":
        
        return jsonify({"status": "success", "message": "Login successful!", "redirect": session.pop("next", "/admin-dash")}), 200
    else:
        return jsonify({"status": "success", "message": "Login successful!", "redirect": session.pop("next", "/")}), 200

    

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")


#admin route

@app.route("/admin-dash")
def admin_dashboard():
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM bus_pass WHERE status_application='Pending'")
    applications = cursor.fetchall()

    cursor.execute("SELECT * FROM bus_routes")
    routes = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("admin-dash.html", applications=applications, routes=routes)

#application approval
@app.route("/admin-dash/approve/<int:id>")
def approve_pass(id):
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("UPDATE bus_pass SET status_application='Approved' WHERE id=%s", (id,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("admin_dashboard"))

#appliacation rejection
@app.route("/admin-dash/reject/<int:id>")
def reject_pass(id):
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("UPDATE bus_pass SET status_application='Rejected' WHERE id=%s", (id,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("admin_dashboard"))

# bus pass deletion

@app.route("/admin-dash/delete/<int:id>")
def delete_pass(id):
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("DELETE FROM bus_pass WHERE id=%s", (id,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("admin_dashboard"))

# create bus route

@app.route("/admin-dash/create-route", methods=["POST"])
def create_route():
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    # Get form data
    route_name = request.form["route_name"]
    start_location = request.form["start_location"]
    end_location = request.form["end_location"]
    stops = request.form["stops"]
    fees =  request.form["fees"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Insert data into the database
    cursor.execute("""
        INSERT INTO bus_routes (route_name, start_location, end_location, stops, created_at, fees)
        VALUES (%s, %s, %s, %s, NOW(), %s)
    """, (route_name, start_location, end_location, stops, fees))

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))


#pdf generation

@app.route("/admin-dash/reports")
def report_page():
    if "user_id" not in session or session.get("user_role") != "admin":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch bus routes
    cursor.execute("SELECT * FROM bus_routes")
    bus_routes = cursor.fetchall()

    # Fetch bus passes
    cursor.execute("SELECT id, full_name, email, status_application, created_at FROM bus_pass")
    bus_passes = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("report.html", bus_routes=bus_routes, bus_passes=bus_passes)



# Apply for Bus Pass - Updated to handle both GET and POST
@app.route("/apply-pass", methods=["GET", "POST"])
@login_required

def apply_pass():
    if request.method == "GET":
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT route_name, fees, stops FROM bus_routes")  # <-- Modified: Fetch bus routes
        bus_routes = cursor.fetchall()
        
        for route in bus_routes:
         route["stops"] = route["stops"].strip("[]")  # Remove brackets
         route["stops"] = route["stops"].replace("'", "")  # Remove extra quotes if any
         route["stops"] = route["stops"].split(",")  # Convert to list
 
        conn.close()
        return render_template("apply.html",bus_routes=bus_routes)
        
    try:
        # Verify user is logged in (redundant with @login_required but good practice)
        if "user_id" not in session:
            return jsonify({"status": "error", "message": "Please login to continue"}), 401

        form = request.form
        full_name = form.get("full_name", "").strip()
        age = form.get("age", "").strip()
        gender = form.get("gender", "").strip()
        phone = form.get("phone", "").strip()
        email = form.get("email", "").strip()
        bus_route = form.get("bus_route", "").strip()
        fees = form.get("fees", "").strip()
        father_name = form.get("father_name", "").strip()
        parent_phone = form.get("parent_phone", "").strip()
        address = form.get("address", "").strip()
        blood_group = form.get("blood_group", "").strip()
        boarding_point = form.get("boarding_point","").strip()
        course_title =  form.get("course_title","").strip()
        
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT fees FROM bus_routes WHERE route_name = %s", (bus_route,))
        route_data = cursor.fetchone()

        if not route_data:
            conn.close()
            return jsonify({"status": "error", "message": "Invalid bus route selected!"}), 400

        fees = route_data["fees"]

        # Ensure all fields are filled
        if not all([full_name, age, gender, phone, email, bus_route, father_name, parent_phone, address, blood_group,fees,boarding_point,course_title]):
            return jsonify({"status": "error", "message": "All fields are required!"}), 400
        
        # Check if email already exists
        cursor.execute("SELECT * FROM bus_pass WHERE email = %s", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "A bus pass is already registered with this email!"}), 400

        # Generate a unique pass ID
        pass_id = str(random.randint(100000, 999999))

        # Insert new bus pass record
        cursor.execute("""
            INSERT INTO bus_pass (full_name, age, gender, phone, email, bus_route, father_name, parent_phone, address, blood_group, pass_id, fees,boarding_point, course_title)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s,%s)
        """, (full_name, age, gender, phone, email, bus_route, father_name, parent_phone, address, blood_group, pass_id, fees,boarding_point,course_title))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Application submitted successfully!", "pass_id": pass_id}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": f"Something went wrong: {str(e)}"}), 500
    
    
# Check Status (Requires Login)
@app.route("/status", methods=["GET", "POST"])
@login_required
def check_status():
    if request.method == "POST":
        email = request.form.get("email")

        if not email:
            return render_template("status.html", error="Email is required!")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT full_name, email, status_application,fees,phone,pass_id FROM bus_pass WHERE email = %s", (email,))
        user_pass = cursor.fetchone()

        cursor.close()
        connection.close()

        if user_pass:
            # If status is "Approved", redirect to the payment page
            if user_pass["status_application"].lower() == "approved":
                session["user_pass"] = user_pass  # Store user data in session
                return redirect(url_for("payment"))
            
            return render_template("status.html", user_pass=user_pass)
        else:
            return render_template("status.html", error="Invalid Email! No record found.")

    return render_template("status.html")

@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    # Fetch user_pass from session
    user_pass = session.get("user_pass")

    payment_status = None
    
    if not user_pass:
        return jsonify({"status": "error", "message": "User session not found. Please check your status."}), 400

    # Establish database connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch user details from the database
        cursor.execute("""
            SELECT full_name, email, fees, phone, pass_id 
            FROM bus_pass 
            WHERE email = %s
        """, (user_pass["email"],))  # Ensure email exists in session
        user_details = cursor.fetchone()

        if not user_details:
            return jsonify({"status": "error", "message": "User details not found in database."}), 404
        
        cursor.execute("""
            SELECT payment_status FROM payments WHERE email = %s
        """, (user_details["email"], ))
        payment_record = cursor.fetchone()

        if payment_record and payment_record["payment_status"].lower() == "completed":
             payment_status = "completed"
             
             
        if request.method == "POST":
            if payment_status == "completed":
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"status": "completed", "message": "Payment already completed!"})  # ✅ AJAX response
                return render_template("payment.html", user_pass=user_details, payment_status=payment_status)  # ✅ Render page
     

        if request.method == "POST":
            # Ensure MySQL connection is alive
            conn.ping(reconnect=True)

            # Insert payment record
            cursor.execute("""
                INSERT INTO payments (name, email, phone, amount, pass_id, payment_status) 
                VALUES (%s, %s, %s, %s, %s, 'Completed')
            """, (user_details["full_name"], user_details["email"], user_details["phone"], user_details["fees"], user_details["pass_id"]))

            conn.commit()
            return jsonify({"status": "success", "message": "Payment recorded successfully!"})  # Success message

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"Payment failed: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()

    return render_template("payment.html", user_pass=user_details)



@app.route("/bus_pass_card")
@login_required
def bus_pass_card():
    user_pass = session.get("user_pass")

    if not user_pass:
        return redirect(url_for("check_status"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # ✅ Use dictionary cursor
    

    # ✅ Fetch all required fields including expiry_date
    cursor.execute("""
        SELECT bp.full_name, bp.email, bp.phone, bp.pass_id,bp.boarding_point, bp.course_title,
        br.id AS id 
        FROM bus_pass bp
        JOIN bus_routes br ON bp.bus_route = br.route_name
        WHERE bp.email = %s
    """, (user_pass["email"],))
    
    user_pass_data = cursor.fetchone()
    conn.close()

    if not user_pass_data:
        return redirect(url_for("check_status"))

    return render_template("bus_pass_card.html", user_pass=user_pass_data)  # ✅ Pass correct data



# Admin Dashboard (Requires Login & Admin Role)
@app.route('/admin')
@login_required
def admin():
    if session.get("user_role") != "admin":
        flash("Access denied: Admins only!", "error")
        return redirect(url_for("home"))
    return render_template("admin-dash.html")


@app.route("/generate_qr")
@login_required
def generate_qr():
    user_pass = session.get("user_pass")

    if not user_pass:
        return "User session not found!", 400

    # Encode user details into the QR code
    pass_data = f"Name: {user_pass['full_name']}\nEmail: {user_pass['email']}\nPhone: {user_pass['phone']}\nPass ID: {user_pass['pass_id']}"

    qr = qrcode.make(pass_data)
    img_io = BytesIO()
    qr.save(img_io, format="PNG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/png")



@app.route('/receipt')
def receipt():
    
    user_pass = session.get("user_pass")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM payments WHERE email = %s", (user_pass["email"],))
    payment_detail = cursor.fetchone()
    
    if not payment:
        return "Payment record not found", 404
    
    return render_template('receipt.html', payment_detail=payment_detail)




if __name__ == '__main__':
    app.run(debug=True)