import sys
import requests
import threading
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QCalendarWidget, QDialog, QMessageBox,
                             QHeaderView, QGroupBox, QListWidget, QListWidgetItem,
                             QTimeEdit)
from PyQt6.QtCore import Qt, QDate, QTime

from api import run_server

API_URL = "http://127.0.0.1:5000/api"

class CalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Week")
        self.setFixedSize(350, 250)
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget(self)
        layout.addWidget(self.calendar)
        btn = QPushButton("Confirm Date")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_date(self):
        return self.calendar.selectedDate().toPyDate()


class WorkerRegistry(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Form for adding a new worker
        form_group = QGroupBox("Add New Worker")
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Owner", "Manager", "Worker"])
        self.bio_input = QTextEdit()
        self.bio_input.setFixedHeight(60)
        
        self.save_btn = QPushButton("Save Worker")
        self.save_btn.clicked.connect(self.save_worker)
        
        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Role:", self.role_combo)
        form_layout.addRow("Detailed Bio:", self.bio_input)
        form_layout.addRow("", self.save_btn)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Table for viewing workers
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Role", "Bio"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.load_workers()

    def save_worker(self):
        data = {
            "name": self.name_input.text(),
            "role": self.role_combo.currentText(),
            "bio": self.bio_input.toPlainText()
        }
        try:
            res = requests.post(f"{API_URL}/workers", json=data)
            res.raise_for_status()
            self.name_input.clear()
            self.bio_input.clear()
            self.load_workers()
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def load_workers(self):
        try:
            res = requests.get(f"{API_URL}/workers")
            res.raise_for_status()
            workers = res.json()
            self.table.setRowCount(len(workers))
            for row, w in enumerate(workers):
                self.table.setItem(row, 0, QTableWidgetItem(w['name']))
                self.table.setItem(row, 1, QTableWidgetItem(w['role']))
                self.table.setItem(row, 2, QTableWidgetItem(w['bio']))
        except requests.exceptions.RequestException:
            pass


class ShiftPlanner(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        
        # Left Panel - Planning
        plan_layout = QVBoxLayout()
        
        # Worker selection
        self.worker_combo = QComboBox()
        self.worker_combo.currentIndexChanged.connect(self.update_task_map)
        
        refresh_btn = QPushButton("Refresh Worker List")
        refresh_btn.clicked.connect(self.load_worker_combo)
        
        plan_layout.addWidget(QLabel("Select Worker to Assign:"))
        plan_layout.addWidget(self.worker_combo)
        plan_layout.addWidget(refresh_btn)
        
        # Time Picker Layout
        time_layout = QHBoxLayout()
        self.start_time = QTimeEdit()
        self.start_time.setTime(QTime(9, 0))
        self.end_time = QTimeEdit()
        self.end_time.setTime(QTime(17, 0))
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("End:"))
        time_layout.addWidget(self.end_time)
        plan_layout.addLayout(time_layout)
        
        # Planner Table
        self.table = QTableWidget(7, 3)
        self.table.setHorizontalHeaderLabels(["Day", "Assigned Worker", "Tasks"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            self.table.setItem(i, 0, QTableWidgetItem(day))
            self.table.setItem(i, 1, QTableWidgetItem("Unassigned"))
            self.table.setItem(i, 2, QTableWidgetItem(""))
        plan_layout.addWidget(self.table)
        
        assign_btn = QPushButton("Assign Selected Worker to Selected Day")
        assign_btn.clicked.connect(self.assign_shift)
        plan_layout.addWidget(assign_btn)
        
        # Right Panel - Task Map
        task_group = QGroupBox("Role Necessary Work List")
        task_layout = QVBoxLayout()
        self.task_list = QListWidget()
        task_layout.addWidget(self.task_list)
        task_group.setLayout(task_layout)
        
        layout.addLayout(plan_layout, 2)
        layout.addWidget(task_group, 1)
        
        self.load_worker_combo()
        self.load_shifts()

    def load_shifts(self):
        try:
            res = requests.get(f"{API_URL}/shifts")
            res.raise_for_status()
            shifts = res.json()
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            for shift in shifts:
                if shift.get("date") in days:
                    row = days.index(shift["date"])
                    worker_text = shift["worker_name"]
                    if shift.get("start_time") and shift.get("end_time"):
                        worker_text += f" ({shift['start_time']} - {shift['end_time']})"
                    self.table.setItem(row, 1, QTableWidgetItem(worker_text))
                    self.table.setItem(row, 2, QTableWidgetItem(shift.get("tasks", "")))
        except requests.exceptions.RequestException:
            pass

    def load_worker_combo(self):
        self.worker_combo.clear()
        try:
            res = requests.get(f"{API_URL}/workers")
            res.raise_for_status()
            for w in res.json():
                self.worker_combo.addItem(f"{w['name']} ({w['role']})", w)
            self.update_task_map()
        except requests.exceptions.RequestException:
            self.worker_combo.addItem("Backend Offline", None)

    def update_task_map(self):
        worker_data = self.worker_combo.currentData()
        self.task_list.clear()
        if worker_data:
            role = worker_data.get('role')
            try:
                res = requests.get(f"{API_URL}/tasks/{role}")
                res.raise_for_status()
                for task in res.json():
                    item = QListWidgetItem(task)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    self.task_list.addItem(item)
            except requests.exceptions.RequestException:
                self.task_list.addItem("Cannot load tasks - API offline")

    def assign_shift(self):
        current_row = self.table.currentRow()
        if current_row < 0: return
        
        worker_data = self.worker_combo.currentData()
        if worker_data:
            day = self.table.item(current_row, 0).text()
            
            start_time_str = self.start_time.time().toString("HH:mm")
            end_time_str = self.end_time.time().toString("HH:mm")
            
            selected_tasks = []
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_tasks.append(item.text())
            tasks_str = ", ".join(selected_tasks)
            
            data = {
                "date": day,
                "worker_name": worker_data['name'],
                "role": worker_data['role'],
                "start_time": start_time_str,
                "end_time": end_time_str,
                "tasks": tasks_str
            }
            try:
                res = requests.post(f"{API_URL}/shifts", json=data)
                res.raise_for_status()
                worker_display = f"{worker_data['name']} ({start_time_str} - {end_time_str})"
                self.table.setItem(current_row, 1, QTableWidgetItem(worker_display))
                self.table.setItem(current_row, 2, QTableWidgetItem(tasks_str))
            except requests.exceptions.RequestException as e:
                QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sunrise Supermarket - Employee Management")
        self.resize(900, 600)
        self.current_date = datetime.now()
        
        # Main Widget & Layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
        # Top Header Strip (Sunrise colors)
        header_layout = QHBoxLayout()
        title = QLabel("☀️ Sunrise Supermarket")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #E65100;")
        
        self.week_label = QLabel()
        self.update_week_label()
        self.week_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF8F00;")
        
        calendar_btn = QPushButton("📅 Select Calendar Week")
        calendar_btn.clicked.connect(self.open_calendar)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.week_label)
        header_layout.addWidget(calendar_btn)
        main_layout.addLayout(header_layout)
        
        # Content Area with Sidebar
        content_layout = QHBoxLayout()
        
        # Sidebar Buttons
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        btn_registry = QPushButton("Worker Registry")
        btn_planner = QPushButton("Weekly Shift Plan")
        
        btn_registry.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn_planner.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        
        sidebar_layout.addWidget(btn_registry)
        sidebar_layout.addWidget(btn_planner)
        
        # Stacked Widget to hold different views
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(WorkerRegistry())
        self.stacked_widget.addWidget(ShiftPlanner())
        
        content_layout.addLayout(sidebar_layout, 1)
        content_layout.addWidget(self.stacked_widget, 4)
        main_layout.addLayout(content_layout)
        
        # Apply application wide Sunrise stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #FAFAFA; }
            QPushButton { background-color: #9CA173; color: white; border-radius: 4px; padding: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #FF8F00; }
            QGroupBox { font-weight: bold; color: #E65100; border: 1px solid #FFB300; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        """)

    def update_week_label(self):
        week_num = self.current_date.isocalendar()[1]
        self.week_label.setText(f"Current Plan: Calendar Week {week_num}")

    def open_calendar(self):
        dialog = CalendarDialog(self)
        if dialog.exec():
            self.current_date = dialog.get_date()
            self.update_week_label()

if __name__ == '__main__':
    # Start the Flask backend server in a background daemon thread
    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
