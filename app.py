import os
from datetime import datetime, timedelta
from functools import wraps
from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-local-development-secret")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "smart_city_smart_parking")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client[DB_NAME]

# Exactly the seven collections in the supplied ER diagram.
citizens = db["citizens"]
admins = db["admins"]
parking_lots = db["parking_lots"]
parking_slots = db["parking_slots"]
parking_bookings = db["parking_bookings"]
payments = db["payments"]
vehicles = db["vehicles"]

def oid(value):
    try:
        return ObjectId(value)
    except Exception:
        return None

def current_user():
    return session.get("user")

def citizen_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user() or current_user().get("role") != "citizen":
            flash("Please log in as a citizen first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user() or current_user().get("role") != "admin":
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def seed_admin():
    if admins.count_documents({}) == 0:
        admins.insert_one({
            "name": "Admin User",
            "email": os.getenv("ADMIN_EMAIL", "admin@smartparking.local"),
            "password": generate_password_hash(os.getenv("ADMIN_PASSWORD", "Admin@123")),
            "role": "Super Admin",
            "phone": "0000000000",
            "createdAt": datetime.utcnow()
        })

def ensure_connection():
    client.admin.command("ping")
    seed_admin()

@app.context_processor
def inject_globals():
    return {"logged_user": current_user(), "now": datetime.utcnow()}

@app.route("/")
def index():
    try:
        lots = list(parking_lots.find().sort("name", 1))
        for lot in lots:
            lot["id"] = str(lot["_id"])
            lot["availableSlots"] = parking_slots.count_documents({"parkingLotId": lot["_id"], "status": "Available"})
    except PyMongoError:
        lots = []
    return render_template("index.html", lots=lots)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        address = {
            "houseNo": request.form.get("houseNo", "").strip(),
            "area": request.form.get("area", "").strip(),
            "city": request.form.get("city", "").strip()
        }
        if not name or not email or len(password) < 6:
            flash("Enter your name, email and a password of at least 6 characters.", "danger")
            return redirect(url_for("register"))
        if citizens.find_one({"email": email}):
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("register"))
        citizens.insert_one({
            "name": name, "email": email,
            "password": generate_password_hash(password),
            "phone": phone, "address": address,
            "vehicleDetails": [], "createdAt": datetime.utcnow()
        })
        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        citizen = citizens.find_one({"email": email})
        admin = admins.find_one({"email": email})
        record = citizen or admin
        if record and check_password_hash(record.get("password", ""), password):
            session["user"] = {
                "id": str(record["_id"]), "name": record.get("name", "User"),
                "email": record["email"], "role": "citizen" if citizen else "admin"
            }
            flash(f"Welcome, {record.get('name', 'User')}!", "success")
            return redirect(url_for("admin_dashboard" if admin and not citizen else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@citizen_required
def dashboard():
    uid = oid(current_user()["id"])
    my_vehicles = list(vehicles.find({"userId": uid}).sort("createdAt", -1))
    my_bookings = list(parking_bookings.find({"citizen_id": uid}).sort("createdAt", -1))
    for b in my_bookings:
        b["slot"] = parking_slots.find_one({"_id": b.get("slotId")}) or {}
        b["lot"] = parking_lots.find_one({"_id": b["slot"].get("parkingLotId")}) if b["slot"] else {}
        b["id"] = str(b["_id"])
    return render_template("dashboard.html", my_vehicles=my_vehicles, bookings=my_bookings)

@app.route("/vehicles", methods=["GET", "POST"])
@citizen_required
def vehicle_page():
    uid = oid(current_user()["id"])
    if request.method == "POST":
        vehicle_no = request.form.get("vehicleNo", "").strip().upper()
        vehicle_type = request.form.get("vehicleType", "Car")
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        color = request.form.get("color", "").strip()
        if not vehicle_no:
            flash("Vehicle number is required.", "danger")
        elif vehicles.find_one({"vehicleNo": vehicle_no}):
            flash("This vehicle number is already registered.", "danger")
        else:
            vehicle_doc = {
                "userId": uid, "vehicleNo": vehicle_no, "vehicleType": vehicle_type,
                "brand": brand, "model": model, "color": color,
                "isActive": True, "createdAt": datetime.utcnow()
            }
            vehicles.insert_one(vehicle_doc)
            citizens.update_one({"_id": uid}, {"$push": {"vehicleDetails": {
                "vehicleNo": vehicle_no, "vehicleType": vehicle_type, "model": model
            }}})
            flash("Vehicle added successfully.", "success")
            return redirect(url_for("vehicle_page"))
    items = list(vehicles.find({"userId": uid}).sort("createdAt", -1))
    return render_template("vehicles.html", vehicles=items)

@app.route("/parking")
def parking_page():
    lots = list(parking_lots.find().sort("name", 1))
    for lot in lots:
        lot["id"] = str(lot["_id"])
        lot["slots"] = list(parking_slots.find({"parkingLotId": lot["_id"]}).sort("slotNumber", 1))
        for slot in lot["slots"]:
            slot["id"] = str(slot["_id"])
    my_vehicle_list = list(vehicles.find({"userId": oid(current_user()["id"])})) if current_user() and current_user().get("role") == "citizen" else []
    return render_template("parking.html", lots=lots, my_vehicle_list=my_vehicle_list)

@app.route("/book/<slot_id>", methods=["POST"])
@citizen_required
def book_slot(slot_id):
    uid = oid(current_user()["id"])
    sid = oid(slot_id)
    slot = parking_slots.find_one({"_id": sid, "status": "Available"}) if sid else None
    vehicle_id = oid(request.form.get("vehicleId"))
    vehicle = vehicles.find_one({"_id": vehicle_id, "userId": uid}) if vehicle_id else None
    if not slot:
        flash("That slot is no longer available.", "danger")
        return redirect(url_for("parking_page"))
    if not vehicle:
        flash("Add a vehicle before booking a parking slot.", "warning")
        return redirect(url_for("vehicle_page"))
    entry = datetime.utcnow()
    exit_time = entry + timedelta(hours=2)
    booking = {
        "citizen_id": uid, "slotId": sid, "vehicleId": vehicle_id,
        "entryTime": entry, "exitTime": exit_time, "status": "Active",
        "totalAmount": 60, "paymentId": None, "createdAt": entry
    }
    result = parking_bookings.insert_one(booking)
    parking_slots.update_one({"_id": sid, "status": "Available"}, {
        "$set": {"status": "Reserved", "currentBookingId": result.inserted_id}
    })
    flash("Parking slot booked. Complete the payment to record your payment.", "success")
    return redirect(url_for("payment_page", booking_id=str(result.inserted_id)))

@app.route("/payment/<booking_id>", methods=["GET", "POST"])
@citizen_required
def payment_page(booking_id):
    uid = oid(current_user()["id"])
    bid = oid(booking_id)
    booking = parking_bookings.find_one({"_id": bid, "citizen_id": uid}) if bid else None
    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        method = request.form.get("paymentMethod", "UPI")
        transaction = "TXN" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        payment = {
            "bookingId": bid, "amount": booking.get("totalAmount", 0),
            "paymentMethod": method, "paymentStatus": "Success",
            "transactionId": transaction, "paidAt": datetime.utcnow()
        }
        payment_result = payments.insert_one(payment)
        parking_bookings.update_one({"_id": bid}, {"$set": {"paymentId": payment_result.inserted_id}})
        flash("Payment recorded successfully (demo payment).", "success")
        return redirect(url_for("dashboard"))
    return render_template("payment.html", booking=booking)

@app.route("/cancel/<booking_id>", methods=["POST"])
@citizen_required
def cancel_booking(booking_id):
    uid = oid(current_user()["id"])
    bid = oid(booking_id)
    booking = parking_bookings.find_one({"_id": bid, "citizen_id": uid, "status": "Active"}) if bid else None
    if booking:
        parking_bookings.update_one({"_id": bid}, {"$set": {"status": "Cancelled"}})
        parking_slots.update_one({"_id": booking["slotId"]}, {"$set": {"status": "Available", "currentBookingId": None}})
        flash("Booking cancelled.", "success")
    else:
        flash("Active booking not found.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "citizens": citizens.count_documents({}),
        "lots": parking_lots.count_documents({}),
        "slots": parking_slots.count_documents({}),
        "bookings": parking_bookings.count_documents({})
    }
    lots = list(parking_lots.find().sort("name", 1))
    for lot in lots:
        lot["id"] = str(lot["_id"])
        lot["available"] = parking_slots.count_documents({"parkingLotId": lot["_id"], "status": "Available"})
    recent = list(parking_bookings.find().sort("createdAt", -1).limit(8))
    for b in recent:
        b["citizen"] = citizens.find_one({"_id": b.get("citizen_id")}) or {}
        b["slot"] = parking_slots.find_one({"_id": b.get("slotId")}) or {}
    return render_template("admin.html", stats=stats, lots=lots, recent=recent)

@app.route("/admin/lots", methods=["POST"])
@admin_required
def add_lot():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()
    area = request.form.get("area", "").strip()
    landmark = request.form.get("landmark", "").strip()
    total = max(1, int(request.form.get("totalSlots", 1)))
    car = max(0, int(request.form.get("car", 0)))
    bike = max(0, int(request.form.get("bike", 0)))
    ev = max(0, int(request.form.get("ev", 0)))
    disabled = max(0, int(request.form.get("disabled", 0)))
    if not name or not city:
        flash("Parking lot name and city are required.", "danger")
        return redirect(url_for("admin_dashboard"))
    lot_id = parking_lots.insert_one({
        "name": name, "address": {"city": city, "area": area, "landmark": landmark},
        "totalSlots": total, "availableSlots": total,
        "slotTypes": {"car": car, "bike": bike, "ev": ev, "disabled": disabled},
        "operatingHours": {"open": "06:00", "close": "23:00"},
        "location": {"type": "Point", "coordinates": []}
    }).inserted_id
    for i in range(1, total + 1):
        kind = "Car" if i <= car else ("Bike" if i <= car + bike else ("EV" if i <= car + bike + ev else "Disabled"))
        parking_slots.insert_one({
            "parkingLotId": lot_id, "slotNumber": str(i), "slotType": kind,
            "status": "Available", "currentBookingId": None,
            "location": {"floor": "Ground", "zone": "A"}
        })
    flash(f"Parking lot added with {total} slots.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/slots/<slot_id>", methods=["POST"])
@admin_required
def change_slot_status(slot_id):
    sid = oid(slot_id)
    status = request.form.get("status")
    if sid and status in ["Available", "Disabled"]:
        parking_slots.update_one({"_id": sid, "currentBookingId": None}, {"$set": {"status": status}})
        flash("Slot status updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/payments")
@admin_required
def admin_payments():
    records = list(payments.find().sort("paidAt", -1))
    for p in records:
        p["id"] = str(p["_id"])
        p["booking"] = parking_bookings.find_one({"_id": p.get("bookingId")}) or {}
    return render_template("admin_payments.html", records=records)

@app.errorhandler( PyMongoError )
def database_error(error):
    return render_template("error.html", message="Cannot connect to MongoDB. Start the MongoDB service and check MONGO_URI in the .env file.", detail=str(error)), 503

if __name__ == "__main__":
    try:
        ensure_connection()
        print(f"Connected to MongoDB database: {DB_NAME}")
        print("Default admin: admin@smartparking.local / Admin@123")
    except Exception as exc:
        print("MongoDB connection failed:", exc)
        print("Start MongoDB Community Server, then run this application again.")
    app.run(host="127.0.0.1", port=5000, debug=True)
