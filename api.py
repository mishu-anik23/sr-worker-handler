import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

# Task map defining the necessary work list relevant to each role
role_tasks = {
    "Owner": ["Review Finances", "Strategic Planning", "Supplier Meetings", "Final Approvals"],
    "Manager": ["Inventory Check", "Staff Scheduling", "Store Inspection", "Customer Relations"],
    "Worker": ["Stock Shelves", "Cashier Duties", "Aisle Cleaning", "Assist Customers"]
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
            role TEXT NOT NULL
        )
    ''')
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
            'INSERT INTO shifts (date, worker_name, role) VALUES (?, ?, ?)',
            (data.get("date"), data.get("worker_name"), data.get("role"))
        )
        conn.commit()
        shift = {
            "id": cursor.lastrowid,
            "date": data.get("date"),
            "worker_name": data.get("worker_name"),
            "role": data.get("role")
        }
        conn.close()
        return jsonify({"status": "success", "shift": shift}), 201
        
    shifts = conn.execute('SELECT * FROM shifts').fetchall()
    conn.close()
    return jsonify([dict(s) for s in shifts])

def run_server():
    # Initialize the database and create tables if they don't exist
    init_db()
    # Run without debug/reloader so it can run safely in a background thread
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()