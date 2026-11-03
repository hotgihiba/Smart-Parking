# ParkSmart — Smart City Digital Platform / Smart Parking

A local full-stack DBMS project built with Flask, MongoDB, PyMongo, HTML, CSS and Bootstrap.

## Database design

This project uses **only the seven collections shown in the supplied ER diagram**:

1. `citizens`
2. `admins`
3. `parking_lots`
4. `parking_slots`
5. `parking_bookings`
6. `payments`
7. `vehicles`

No additional application collections are created. Relationships are represented using MongoDB `ObjectId` references and the `citizens.vehicleDetails` embedded array as illustrated in the diagram.

## Requirements

- Windows 10/11
- Python 3.10 or newer
- MongoDB Community Server running locally
- VS Code (recommended)

## Run on Windows

1. Install Python and MongoDB Community Server.
2. During Python installation, select **Add Python to PATH**.
3. Start the MongoDB service:
   - Press `Win + R`, enter `services.msc`.
   - Find **MongoDB Server** and choose **Start**.
   - If it is already running, leave it running.
4. Extract this ZIP file.
5. Double-click `run.bat`.
   - It creates a virtual environment.
   - Installs the required Python packages.
   - Creates `.env` from `.env.example` if needed.
   - Starts Flask.
6. Open **http://127.0.0.1:5000** in Chrome.

You can also open the extracted folder in VS Code and run `app.py` after installing `requirements.txt`.

## Default administrator login

- Email: `admin@smartparking.local`
- Password: `Admin@123`

Change these values in `.env` before using the project beyond a local demonstration. The default admin is created automatically only when the `admins` collection is empty.

## Suggested demonstration

1. Log in as admin.
2. Add a parking lot and define its total slots and slot types.
3. Log out and register a citizen.
4. Log in as the citizen.
5. Add a vehicle in **My Vehicles**.
6. Open **Find Parking**, select a vehicle and book an available slot.
7. Complete the demo payment.
8. Show the booking in the citizen dashboard and payment record in the admin panel.

## MongoDB Compass

Connect Compass to:

`mongodb://localhost:27017/`

Open database:

`smart_city_smart_parking`

You should see the seven collections listed above. Collections are created as the application inserts its first records.

## Notes

- Payment is a **demo record only**. No real payment gateway or money transfer is connected.
- A booking is for a two-hour demo period and currently has a sample amount of ₹60.
- The application uses a local MongoDB server; it does not require MongoDB Atlas.
- The map coordinates field is kept in the parking lot document as shown in the ER diagram. Live maps and GPS tracking are not implemented.
- For a fresh demonstration database, remove the `smart_city_smart_parking` database in Compass and restart the app. This permanently deletes its data.
