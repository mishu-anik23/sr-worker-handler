import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

# Task map defining the necessary work list relevant to each role
role_tasks = {
    "Owner": ["Review Finances", "Strategic Planning", "Supplier Meetings", "Final Approvals",
              "Product Entry in Cash System", "Price Tag Generation", "Old Price Update", "Product Inventory & Order",
              "Customer Bill Generation", "Vegetable Pickup Kelsterbach", "Veg-Fruit Purchase from Frischezentrum",
              "Italian Vegetable Pickup from Frischezentrum", "Pickup Freezelog Products"],
    "Manager": ["Inventory Check", "Staff Scheduling", "Store Inspection", "Customer Relations"],
    "Worker": [
        "Stock Shelves", "Cashier Duties", "Aisle Cleaning", "Assist Customers",
        "Keller Water Empty", "Paper Tonne Taking Outside", "Vegetable Room Water empty", 
        "Vegtable Packing", "Product Inventory & Order List", "Product Expiry Date Checking", 
        "Shelf Arranging and Feeling"]
}

def get_db_connection():
    conn = sqlite3.connect('supermarket.db')
    # This allows us to access columns by name (like dictionaries) instead of numerical indices
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            bio TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            worker_name TEXT NOT NULL,
            role TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            tasks TEXT,
            timesheet_data TEXT,
            full_date TEXT
        )
    ''')
    
    # Safely alter table to add new columns if the database file already exists
    for col in ['start_time TEXT', 'end_time TEXT', 'tasks TEXT', 'timesheet_data TEXT', 'full_date TEXT']:
        try:
            conn.execute(f'ALTER TABLE shifts ADD COLUMN {col}')
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

@app.route('/api/workers', methods=['GET', 'POST'])
def manage_workers():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json
        cursor = conn.execute(
            'INSERT INTO workers (name, role, bio) VALUES (?, ?, ?)',
            (data.get("name"), data.get("role"), data.get("bio"))
        )
        conn.commit()
        worker = {
            "id": cursor.lastrowid,
            "name": data.get("name"),
            "role": data.get("role"),
            "bio": data.get("bio")
        }
        conn.close()
        return jsonify({"status": "success", "worker": worker}), 201
        
    workers = conn.execute('SELECT * FROM workers').fetchall()
    conn.close()
    return jsonify([dict(w) for w in workers])

@app.route('/api/tasks/<role>', methods=['GET'])
def get_tasks(role):
    tasks = role_tasks.get(role, [])
    return jsonify(tasks)

@app.route('/api/shifts', methods=['GET', 'POST'])
def manage_shifts():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json
        cursor = conn.execute(
            'INSERT INTO shifts (date, full_date, worker_name, role, start_time, end_time, tasks, timesheet_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get("date"), data.get("full_date"), data.get("worker_name"), data.get("role"), data.get("start_time"), data.get("end_time"), data.get("tasks"), data.get("timesheet_data"))
        )
        conn.commit()
        shift = {
            "id": cursor.lastrowid,
            "date": data.get("date"),
            "worker_name": data.get("worker_name"),
            "role": data.get("role"),
            "start_time": data.get("start_time"),
            "end_time": data.get("end_time"),
            "tasks": data.get("tasks"),
            "full_date": data.get("full_date"),
            "timesheet_data": data.get("timesheet_data")
        }
        conn.close()
        return jsonify({"status": "success", "shift": shift}), 201
        
    shifts = conn.execute('SELECT * FROM shifts').fetchall()
    conn.close()
    return jsonify([dict(s) for s in shifts])

@app.route('/api/shifts/<int:shift_id>', methods=['PUT'])
def update_shift(shift_id):
    conn = get_db_connection()
    data = request.json
    conn.execute('UPDATE shifts SET timesheet_data = ? WHERE id = ?', (data.get('timesheet_data'), shift_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/shifts/<day>', methods=['DELETE'])
def clear_shifts(day):
    conn = get_db_connection()
    conn.execute('DELETE FROM shifts WHERE date = ?', (day,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

def run_server():
    # Initialize the database and create tables if they don't exist
    init_db()
    # Run without debug/reloader so it can run safely in a background thread
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()