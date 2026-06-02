from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory database arrays for quick setup
workers = []
shifts = []

# Task map defining the necessary work list relevant to each role
role_tasks = {
    "Owner": ["Review Finances", "Strategic Planning", "Supplier Meetings", "Final Approvals"],
    "Manager": ["Inventory Check", "Staff Scheduling", "Store Inspection", "Customer Relations"],
    "Worker": ["Stock Shelves", "Cashier Duties", "Aisle Cleaning", "Assist Customers"]
}

@app.route('/api/workers', methods=['GET', 'POST'])
def manage_workers():
    if request.method == 'POST':
        data = request.json
        worker = {
            "id": len(workers) + 1,
            "name": data.get("name"),
            "role": data.get("role"),
            "bio": data.get("bio")
        }
        workers.append(worker)
        return jsonify({"status": "success", "worker": worker}), 201
    return jsonify(workers)

@app.route('/api/tasks/<role>', methods=['GET'])
def get_tasks(role):
    tasks = role_tasks.get(role, [])
    return jsonify(tasks)

@app.route('/api/shifts', methods=['GET', 'POST'])
def manage_shifts():
    if request.method == 'POST':
        data = request.json
        shift = {
            "id": len(shifts) + 1,
            "date": data.get("date"),
            "worker_name": data.get("worker_name"),
            "role": data.get("role")
        }
        shifts.append(shift)
        return jsonify({"status": "success", "shift": shift}), 201
    return jsonify(shifts)

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(port=5000, debug=True)