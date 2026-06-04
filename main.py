import sys
import requests
import threading
import json
import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QCalendarWidget, QDialog, QMessageBox,
                             QHeaderView, QGroupBox, QListWidget, QListWidgetItem,
                             QTimeEdit, QScrollArea, QProgressBar)
from PyQt6.QtCore import Qt, QDate, QTime, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont

from api import run_server

API_URL = "http://127.0.0.1:5000/api"

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

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


class OccupancyWidget(QWidget):
    def __init__(self, start_hour, end_hour, shifts, parent=None):
        super().__init__(parent)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.shifts = shifts
        self.setMinimumHeight(max(50, 15 + len(self.shifts) * 20))
        self.setMouseTracking(True)
        self.shift_rects = []

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.shift_rects.clear()
        
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Draw background (remaining bar)
        painter.setBrush(QColor("#E0E0E0"))
        painter.setPen(Qt.PenStyle.NoPen)
        margin_y = 5
        bar_height = height - margin_y * 2
        painter.drawRoundedRect(0, margin_y, width, bar_height, 4, 4)
        
        total_hours = self.end_hour - self.start_hour
        if total_hours <= 0:
            return
            
        role_colors = {
            "Owner": QColor("#D32F2F"),    # Red
            "Manager": QColor("#1976D2"),  # Blue
            "Worker": QColor("#388E3C")    # Green
        }
        
        # Draw hour markers inside the bar
        painter.setPen(QColor("#9E9E9E"))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        for h in range(int(self.start_hour), int(self.end_hour) + 1):
            x = ((h - self.start_hour) / total_hours) * width
            painter.drawLine(int(x), margin_y, int(x), height - margin_y)
            if h != int(self.end_hour):
                painter.drawText(int(x) + 2, margin_y + 10, f"{h}:00")

        num_shifts = len(self.shifts)
        if num_shifts == 0:
            return
            
        shift_height = bar_height / num_shifts
        
        for i, shift in enumerate(self.shifts):
            s = shift['start']
            e = shift['end']
            
            # Ensure shifts stay within operational hours
            s_clamped = max(self.start_hour, min(s, self.end_hour))
            e_clamped = max(self.start_hour, min(e, self.end_hour))
            
            if e_clamped <= s_clamped: 
                continue
            
            x = ((s_clamped - self.start_hour) / total_hours) * width
            w = ((e_clamped - s_clamped) / total_hours) * width
            y = margin_y + i * shift_height
            
            color = role_colors.get(shift.get('role', ''), QColor("#757575"))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            rect_f = QRectF(x, y, w, shift_height)
            painter.drawRoundedRect(rect_f, 2, 2)
            self.shift_rects.append((rect_f, shift))
            
            painter.setPen(QColor("#FFFFFF"))
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            text_rect = QRectF(x, y, w, shift_height)
            if w > 30:
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, shift.get('name', ''))

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, shift in self.shift_rects:
            if rect.contains(pos):
                self.setToolTip(shift.get('tooltip', ''))
                return
        self.setToolTip('')

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
            res = requests.post(f"{API_URL}/workers", json=data, timeout=3)
            res.raise_for_status()
            self.name_input.clear()
            self.bio_input.clear()
            self.load_workers()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error saving worker: {e}")
            QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def load_workers(self):
        try:
            res = requests.get(f"{API_URL}/workers", timeout=3)
            res.raise_for_status()
            workers = res.json()
            self.table.setRowCount(len(workers))
            for row, w in enumerate(workers):
                self.table.setItem(row, 0, QTableWidgetItem(w['name']))
                self.table.setItem(row, 1, QTableWidgetItem(w['role']))
                self.table.setItem(row, 2, QTableWidgetItem(w['bio']))
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load workers: {e}")


class ShiftPlanner(QWidget):
    def __init__(self):
        super().__init__()
        self.current_date = datetime.now()
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
        self.table.setHorizontalHeaderLabels(["Day", "Shift Timeline", "Tasks"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            self.table.setItem(i, 0, QTableWidgetItem(day))
            self.table.setItem(i, 1, QTableWidgetItem("Unassigned"))
            self.table.setItem(i, 2, QTableWidgetItem(""))
        plan_layout.addWidget(self.table)
        
        assign_btn = QPushButton("Assign Selected Worker to Selected Day")
        assign_btn.clicked.connect(self.assign_shift)
        plan_layout.addWidget(assign_btn)
        
        reset_btn = QPushButton("Reset Selected Day")
        reset_btn.clicked.connect(self.reset_row)
        plan_layout.addWidget(reset_btn)
        
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

    def update_dates(self, base_date):
        if isinstance(base_date, datetime):
            self.current_date = base_date
            base_date = base_date.date()
        else:
            self.current_date = datetime.combine(base_date, datetime.min.time())
        monday = base_date - timedelta(days=base_date.weekday())
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            current = monday + timedelta(days=i)
            self.table.item(i, 0).setText(f"{day}\n{current.strftime('%Y-%m-%d')}")
        self.table.resizeRowsToContents()

    def time_to_float(self, t_str):
        try:
            h, m = map(int, t_str.split(':'))
            return h + m / 60.0
        except:
            return 0.0

    def load_shifts(self):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i in range(7):
            self.table.removeCellWidget(i, 1)
            self.table.removeCellWidget(i, 2)
            self.table.setItem(i, 1, QTableWidgetItem("Unassigned"))
            self.table.setItem(i, 2, QTableWidgetItem(""))

        try:
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            shifts = res.json()
            
            worker_hours = {}
            for s in shifts:
                if s.get("full_date") and s.get("start_time") and s.get("end_time"):
                    try:
                        dt = datetime.strptime(s["full_date"], "%Y-%m-%d")
                        w_name = s["worker_name"]
                        if w_name not in worker_hours:
                            worker_hours[w_name] = {'weekly': 0.0, 'monthly': 0.0}
                        hrs = self.time_to_float(s["end_time"]) - self.time_to_float(s["start_time"])
                        if dt.month == self.current_date.month and dt.year == self.current_date.year:
                            worker_hours[w_name]['monthly'] += hrs
                        if dt.isocalendar()[1] == self.current_date.isocalendar()[1] and dt.year == self.current_date.year:
                            worker_hours[w_name]['weekly'] += hrs
                    except ValueError:
                        pass
            
            day_shifts = {day: [] for day in days}
            for shift in shifts:
                if shift.get("date") in days:
                    day_shifts[shift["date"]].append(shift)
                    
            for day, day_shift_list in day_shifts.items():
                if not day_shift_list:
                    continue
                row = days.index(day)
                
                is_sunday = (day == "Sunday")
                start_hour = 14.0 if is_sunday else 10.0
                end_hour = 21.0 if is_sunday else 22.0
                
                parsed_shifts = []
                for s in day_shift_list:
                    wh = worker_hours.get(s['worker_name'], {})
                    tooltip = (f"Worker: {s['worker_name']}\nRole: {s['role']}\n"
                               f"Shift: {s.get('start_time')} - {s.get('end_time')}\n"
                               f"Weekly Hours: {wh.get('weekly', 0):.1f}\n"
                               f"Monthly Hours: {wh.get('monthly', 0):.1f}")
                               
                    if s.get("start_time") and s.get("end_time"):
                        parsed_shifts.append({
                            'start': self.time_to_float(s["start_time"]),
                            'end': self.time_to_float(s["end_time"]),
                            'role': s.get('role', ''),
                            'name': s.get('worker_name', ''),
                            'tooltip': tooltip
                        })
                
                if parsed_shifts:
                    occupancy_widget = OccupancyWidget(start_hour, end_hour, parsed_shifts)
                    self.table.setItem(row, 1, QTableWidgetItem(""))
                    self.table.setCellWidget(row, 1, occupancy_widget)

                tasks_container = QWidget()
                tasks_layout = QVBoxLayout(tasks_container)
                tasks_layout.setContentsMargins(5, 5, 5, 5)
                for s in day_shift_list:
                    if s.get("tasks"):
                        lbl = QLabel(f"<b>[{s['worker_name']}]</b> {s['tasks']}")
                        lbl.setWordWrap(True)
                        tasks_layout.addWidget(lbl)
                tasks_layout.addStretch()
                self.table.setItem(row, 2, QTableWidgetItem(""))
                self.table.setCellWidget(row, 2, tasks_container)
                
            self.table.resizeRowsToContents()
            for i in range(7):
                widget = self.table.cellWidget(i, 1)
                if widget:
                    self.table.setRowHeight(i, max(60, widget.minimumHeight() + 10))
                else:
                    self.table.setRowHeight(i, max(60, self.table.rowHeight(i)))
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load shifts: {e}")

    def load_worker_combo(self):
        self.worker_combo.clear()
        try:
            res = requests.get(f"{API_URL}/workers", timeout=3)
            res.raise_for_status()
            for w in res.json():
                self.worker_combo.addItem(f"{w['name']} ({w['role']})", w)
            self.update_task_map()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load worker combo: {e}")
            self.worker_combo.addItem("Backend Offline", None)

    def update_task_map(self):
        worker_data = self.worker_combo.currentData()
        self.task_list.clear()
        if worker_data:
            role = worker_data.get('role')
            try:
                res = requests.get(f"{API_URL}/tasks/{role}", timeout=3)
                res.raise_for_status()
                for task in res.json():
                    item = QListWidgetItem(task)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    self.task_list.addItem(item)
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to load tasks for role {role}: {e}")
                self.task_list.addItem("Cannot load tasks - API offline")

    def assign_shift(self):
        current_row = self.table.currentRow()
        if current_row < 0: return
        
        worker_data = self.worker_combo.currentData()
        if worker_data:
            day_text = self.table.item(current_row, 0).text()
            day = day_text.split('\n')[0]
            full_date_str = day_text.split('\n')[1] if '\n' in day_text else ""
            
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
                "full_date": full_date_str,
                "worker_name": worker_data['name'],
                "role": worker_data['role'],
                "start_time": start_time_str,
                "end_time": end_time_str,
                "tasks": tasks_str
            }
            try:
                res = requests.post(f"{API_URL}/shifts", json=data, timeout=3)
                res.raise_for_status()
                self.load_shifts()
            except requests.exceptions.RequestException as e:
                logging.error(f"Error assigning shift: {e}")
                QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def reset_row(self):
        current_row = self.table.currentRow()
        if current_row < 0: return
        day_text = self.table.item(current_row, 0).text()
        day = day_text.split('\n')[0]
        
        try:
            res = requests.delete(f"{API_URL}/shifts/{day}", timeout=3)
            res.raise_for_status()
            self.load_shifts()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error resetting row for {day}: {e}")
            QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")


class EmployeeTimesheet(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        self.worker_combo = QComboBox()
        self.worker_combo.currentIndexChanged.connect(self.load_tasks)
        refresh_btn = QPushButton("Refresh Workers")
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(QLabel("Select Worker:"))
        header.addWidget(self.worker_combo)
        header.addWidget(refresh_btn)
        layout.addLayout(header)
        
        # List of Shifts
        self.shift_combo = QComboBox()
        self.shift_combo.currentIndexChanged.connect(self.display_timesheet)
        layout.addWidget(QLabel("Select Active Shift Assignment:"))
        layout.addWidget(self.shift_combo)
        
        # Progress Bar Layout
        prog_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("Hours: 0.0 / 0.0")
        prog_layout.addWidget(QLabel("Shift Progression:"))
        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.progress_label)
        layout.addLayout(prog_layout)
        
        # Tasks Form
        self.tasks_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setMinimumWidth(850) # Ensures horizontal scrollability
        inner.setLayout(self.tasks_layout)
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        
        # Extra Hours Section
        self.extra_group = QGroupBox("Extra Hours Request")
        extra_layout = QHBoxLayout()
        self.extra_hours = QComboBox()
        self.extra_hours.setEditable(True)
        self.extra_hours.addItems([str(x/2.0) for x in range(0, 11)])
        self.extra_purpose = QLineEdit()
        self.extra_purpose.setPlaceholderText("Purpose / Reason")
        self.extra_ask_btn = QPushButton("Ask for Approval")
        self.extra_ask_btn.clicked.connect(self.ask_approval)
        self.extra_status_lbl = QLabel("Status: Not Requested")
        self.extra_status_lbl.setStyleSheet("font-weight: bold;")
        extra_layout.addWidget(QLabel("Extra Hours:"))
        extra_layout.addWidget(self.extra_hours)
        extra_layout.addWidget(self.extra_purpose)
        extra_layout.addWidget(self.extra_ask_btn)
        extra_layout.addWidget(self.extra_status_lbl)
        self.extra_group.setLayout(extra_layout)
        layout.addWidget(self.extra_group)
        
        # Save button
        self.save_btn = QPushButton("Save Timesheet Log")
        self.save_btn.clicked.connect(self.save_timesheet)
        layout.addWidget(self.save_btn)
        
        self.current_shift_id = None
        self.task_widgets = []
        self.total_assigned_hours = 0.0
        self.load_data()
        
    def load_data(self):
        self.worker_combo.clear()
        try:
            res = requests.get(f"{API_URL}/workers", timeout=3)
            res.raise_for_status()
            for w in res.json():
                self.worker_combo.addItem(w['name'], w['name'])
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load workers for timesheet: {e}")
            
    def load_tasks(self):
        self.shift_combo.clear()
        worker_name = self.worker_combo.currentData()
        if not worker_name: return
        try:
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            for s in res.json():
                if s.get('worker_name') == worker_name:
                    disp = f"{s.get('full_date', s.get('date'))} ({s.get('start_time')} - {s.get('end_time')})"
                    self.shift_combo.addItem(disp, s)
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load shifts for timesheet: {e}")
            
    def display_timesheet(self):
        for i in reversed(range(self.tasks_layout.count())): 
            widget = self.tasks_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
            else:
                layout = self.tasks_layout.itemAt(i).layout()
                if layout:
                    while layout.count():
                        item = layout.takeAt(0)
                        if item.widget(): item.widget().deleteLater()
                    layout.deleteLater()
                    
        self.task_widgets.clear()
        self.current_shift_id = None
        
        shift_data = self.shift_combo.currentData()
        if not shift_data: return
        self.current_shift_id = shift_data.get('id')
        
        # Calculate assigned hours
        try:
            h1, m1 = map(int, shift_data.get('start_time', '00:00').split(':'))
            h2, m2 = map(int, shift_data.get('end_time', '00:00').split(':'))
            self.total_assigned_hours = (h2 + m2/60.0) - (h1 + m1/60.0)
            if self.total_assigned_hours < 0: self.total_assigned_hours = 0.0
        except Exception:
            self.total_assigned_hours = 8.0 # Fallback
            
        tasks_str = shift_data.get('tasks', '')
        if not tasks_str: return
        tasks = [t.strip() for t in tasks_str.split(',') if t.strip()]
        
        timesheet_data = {}
        if shift_data.get('timesheet_data'):
            try:
                timesheet_data = json.loads(shift_data['timesheet_data'])
            except:
                pass
        
        # Header for columns
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("<b>Task</b>"), 3)
        header_row.addWidget(QLabel("<b>Hrs Spent</b>"), 1)
        header_row.addWidget(QLabel("<b>Status</b>"), 1)
        header_row.addWidget(QLabel("<b>Comment</b>"), 2)
        self.tasks_layout.addLayout(header_row)

        for task in tasks:
            row = QHBoxLayout()
            row.addWidget(QLabel(task), 3)
            
            hours_combo = QComboBox()
            hours_combo.setEditable(True)
            hours_combo.addItems(["0.0"] + [str(x/2.0) for x in range(1, 11)])
            saved_hours = timesheet_data.get(task, {}).get('hours', '0.0')
            hours_combo.setCurrentText(str(saved_hours))
            hours_combo.currentTextChanged.connect(self.update_progress)
            row.addWidget(hours_combo, 1)
            
            status_combo = QComboBox()
            status_combo.addItems(["Not Done", "Working", "Done"])
            saved_status = timesheet_data.get(task, {}).get('status', 'Not Done')
            status_combo.setCurrentText(saved_status)
            row.addWidget(status_combo, 1)
            
            comment_input = QLineEdit()
            comment_input.setPlaceholderText("Comment...")
            comment_input.setText(timesheet_data.get(task, {}).get('comment', ''))
            row.addWidget(comment_input, 2)
            
            self.tasks_layout.addLayout(row)
            self.task_widgets.append((task, hours_combo, status_combo, comment_input))
            
        self.tasks_layout.addStretch()
        
        extra_data = timesheet_data.get('__extra_hours__', {})
        self.extra_hours.setCurrentText(str(extra_data.get('hours', '0.0')))
        self.extra_purpose.setText(extra_data.get('purpose', ''))
        self.extra_status_lbl.setText(f"Status: {extra_data.get('status', 'Not Requested')}")
        
        self.update_progress()

    def update_progress(self, *args):
        total_spent = 0.0
        for _, h_combo, _, _ in self.task_widgets:
            try:
                total_spent += float(h_combo.currentText())
            except ValueError:
                pass
                
        self.progress_label.setText(f"Hours: {total_spent:.1f} / {self.total_assigned_hours:.1f}")
        
        max_val = int(self.total_assigned_hours * 10)
        spent_val = int(total_spent * 10)
        
        self.progress_bar.setMaximum(max_val if max_val > 0 else 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat(f"{total_spent:.1f} / {self.total_assigned_hours:.1f} hrs")
        
        base_style = "QProgressBar { text-align: center; border: 1px solid #BDBDBD; border-radius: 4px; color: black; font-weight: bold; background-color: #FAFAFA; }"
        if total_spent > self.total_assigned_hours:
            self.progress_bar.setValue(max_val)
            self.progress_bar.setStyleSheet(base_style + " QProgressBar::chunk { background-color: #D32F2F; border-radius: 4px; }")
        elif total_spent == self.total_assigned_hours and self.total_assigned_hours > 0:
            self.progress_bar.setValue(spent_val)
            self.progress_bar.setStyleSheet(base_style + " QProgressBar::chunk { background-color: #388E3C; border-radius: 4px; }")
        else:
            self.progress_bar.setValue(spent_val)
            self.progress_bar.setStyleSheet(base_style + " QProgressBar::chunk { background-color: #1976D2; border-radius: 4px; }")
            
    def ask_approval(self):
        self.extra_status_lbl.setText("Status: Pending Approval")
        self.extra_status_lbl.setStyleSheet("font-weight: bold; color: #1976D2;")
        self.save_timesheet()

    def save_timesheet(self):
        if not self.current_shift_id: return
        
        ts_data = {}
        for task, h_combo, s_combo, line_edit in self.task_widgets:
            ts_data[task] = {
                'hours': h_combo.currentText(),
                'status': s_combo.currentText(),
                'comment': line_edit.text()
            }
            
        ts_data['__extra_hours__'] = {
            'hours': self.extra_hours.currentText(),
            'purpose': self.extra_purpose.text(),
            'status': self.extra_status_lbl.text().replace("Status: ", "")
        }
            
        try:
            res = requests.put(f"{API_URL}/shifts/{self.current_shift_id}", 
                               json={'timesheet_data': json.dumps(ts_data)}, timeout=3)
            res.raise_for_status()
            
            shift_data = self.shift_combo.currentData()
            shift_data['timesheet_data'] = json.dumps(ts_data)
            QMessageBox.information(self, "Success", "Timesheet saved!")
        except Exception as e:
            logging.error(f"Error saving timesheet: {e}")
            QMessageBox.critical(self, "Error", f"Could not save: {e}")


class StatisticsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        refresh_btn = QPushButton("Refresh Statistics Data")
        refresh_btn.clicked.connect(self.load_stats)
        layout.addWidget(refresh_btn)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Worker", "Total Hours", "Completed Tasks", "Pending/Working Tasks"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.load_stats()
        
    def load_stats(self):
        try:
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            shifts = res.json()
            
            stats = {}
            for s in shifts:
                w = s.get('worker_name')
                if not w: continue
                if w not in stats:
                    stats[w] = {'hours': 0.0, 'completed': 0, 'pending': 0}
                    
                try:
                    h1, m1 = map(int, s['start_time'].split(':'))
                    h2, m2 = map(int, s['end_time'].split(':'))
                    hrs = (h2 + m2/60.0) - (h1 + m1/60.0)
                    stats[w]['hours'] += hrs
                except:
                    pass
                    
                ts_str = s.get('timesheet_data')
                if ts_str:
                    try:
                        ts_data = json.loads(ts_str)
                        for task, info in ts_data.items():
                            if task == '__extra_hours__':
                                continue
                            if info.get('status') == 'Done':
                                stats[w]['completed'] += 1
                            else:
                                stats[w]['pending'] += 1
                    except:
                        pass
                else:
                    tasks_str = s.get('tasks', '')
                    if tasks_str:
                        tasks = [t.strip() for t in tasks_str.split(',') if t.strip()]
                        stats[w]['pending'] += len(tasks)
                        
            self.table.setRowCount(len(stats))
            for row, (worker, data) in enumerate(stats.items()):
                self.table.setItem(row, 0, QTableWidgetItem(worker))
                self.table.setItem(row, 1, QTableWidgetItem(f"{data['hours']:.1f} hr(s)"))
                self.table.setItem(row, 2, QTableWidgetItem(str(data['completed'])))
                self.table.setItem(row, 3, QTableWidgetItem(str(data['pending'])))
                
        except Exception as e:
            logging.error(f"Failed to load statistics: {e}")

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
        btn_timesheet = QPushButton("Employee Timesheet")
        btn_stats = QPushButton("Statistics")
        
        btn_registry.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn_planner.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        btn_timesheet.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        btn_stats.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        
        sidebar_layout.addWidget(btn_registry)
        sidebar_layout.addWidget(btn_planner)
        sidebar_layout.addWidget(btn_timesheet)
        sidebar_layout.addWidget(btn_stats)
        
        # Stacked Widget to hold different views
        self.stacked_widget = QStackedWidget()
        self.worker_registry = WorkerRegistry()
        self.shift_planner = ShiftPlanner()
        self.timesheet_widget = EmployeeTimesheet()
        self.stats_widget = StatisticsWidget()
        self.stacked_widget.addWidget(self.worker_registry)
        self.stacked_widget.addWidget(self.shift_planner)
        self.stacked_widget.addWidget(self.timesheet_widget)
        self.stacked_widget.addWidget(self.stats_widget)
        self.update_week_label()
        
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
        if hasattr(self, 'shift_planner'):
            self.shift_planner.update_dates(self.current_date)

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
