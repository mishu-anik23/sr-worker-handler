import sys
import os
import requests
import threading
import json
import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit,
                             QComboBox, QTextEdit, QCalendarWidget, QDialog, QMessageBox, QFileDialog,
                             QHeaderView, QGroupBox, QListWidget, QListWidgetItem,
                             QTimeEdit, QScrollArea, QProgressBar, QDateTimeEdit, QFrame, QLayout, QSizePolicy)
from PyQt6.QtCore import Qt, QDate, QTime, QRectF, pyqtSignal, QPoint, QSize, QRect, QMarginsF
from PyQt6.QtGui import QPainter, QColor, QFont, QPdfWriter, QPageLayout, QPageSize

from api import run_server

API_URL = "http://127.0.0.1:5000/api"

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=-1, hSpacing=-1, vSpacing=-1, alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(parent)
        self._hSpace = hSpacing
        self._vSpace = vSpacing
        self._alignment = alignment
        self.itemList = []
        if margin > -1:
            self.setContentsMargins(margin, margin, margin, margin)
            
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
            
    def addItem(self, item):
        self.itemList.append(item)
        
    def horizontalSpacing(self):
        if self._hSpace >= 0:
            return self._hSpace
        return self.spacing()
        
    def verticalSpacing(self):
        if self._vSpace >= 0:
            return self._vSpace
        return self.spacing()
        
    def count(self):
        return len(self.itemList)
        
    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None
        
    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None
        
    def expandingDirections(self):
        return Qt.Orientation(0)
        
    def hasHeightForWidth(self):
        return True
        
    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)
        
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)
        
    def sizeHint(self):
        return self.minimumSize()
        
    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size
        
    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        
        rows = []
        current_row = []
        row_width = 0
        
        for item in self.itemList:
            wid = item.widget()
            spaceX = self.horizontalSpacing() if wid else 0
            
            item_w = item.sizeHint().width()
            item_h = item.sizeHint().height()
            
            if row_width + item_w > rect.width() and current_row:
                rows.append((current_row, row_width - spaceX, lineHeight))
                current_row = []
                row_width = 0
                lineHeight = 0
                
            current_row.append(item)
            row_width += item_w + spaceX
            lineHeight = max(lineHeight, item_h)
            
        if current_row:
            rows.append((current_row, row_width - spaceX, lineHeight))
            
        y = rect.y()
        for row, r_width, r_height in rows:
            if self._alignment == Qt.AlignmentFlag.AlignRight:
                x = rect.right() - r_width + 1
            else:
                x = rect.x()
                
            for item in row:
                wid = item.widget()
                spaceX = self.horizontalSpacing() if wid else 0
                if not testOnly:
                    item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
                x += item.sizeHint().width() + spaceX
            y += r_height + self.verticalSpacing()
            
        if rows:
            y -= self.verticalSpacing()
            
        return y - rect.y()

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

class SetLateEntryDialog(QDialog):
    def __init__(self, shift_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Late Entry")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        form.addRow("Worker:", QLabel(shift_data.get('name', '')))
        form.addRow("Scheduled Start:", QLabel(shift_data.get('start_time', '')))
        
        self.entry_time = QComboBox()
        time_intervals = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        self.entry_time.addItems(time_intervals)
        self.entry_time.setCurrentText(shift_data.get('entry_time') or shift_data.get('start_time', '00:00'))
        
        form.addRow("Late Entry / Arrival:", self.entry_time)
        layout.addLayout(form)
        
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save Entry Time")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)
        
    def get_data(self):
        return {"entry_time": self.entry_time.currentText()}

class VoluntaryShiftDialog(QDialog):
    def __init__(self, worker_name, tasks, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Voluntary Shift - {worker_name}")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.start_dt = QDateTimeEdit(datetime.now())
        self.start_dt.setCalendarPopup(True)
        self.end_dt = QDateTimeEdit(datetime.now() + timedelta(hours=2))
        self.end_dt.setCalendarPopup(True)
        
        form.addRow("Start:", self.start_dt)
        form.addRow("End:", self.end_dt)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Select Voluntary Tasks:"))
        self.task_list = QListWidget()
        for task in tasks:
            item = QListWidgetItem(task)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.task_list.addItem(item)
        layout.addWidget(self.task_list)
        
        btn_box = QHBoxLayout()
        assign_btn = QPushButton("Assign Shift")
        assign_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(assign_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def get_data(self):
        selected_tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_tasks.append(item.text())
        return {
            "start_dt": self.start_dt.dateTime().toPyDateTime(),
            "end_dt": self.end_dt.dateTime().toPyDateTime(),
            "tasks": ", ".join(selected_tasks)
        }


class EditShiftDialog(QDialog):
    def __init__(self, shift_data, workers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Shift")
        self.setMinimumWidth(400)
        self.shift_data = shift_data
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.worker_combo = QComboBox()
        current_idx = 0
        for i, w in enumerate(workers):
            self.worker_combo.addItem(f"{w['name']} ({w['role']})", w)
            if w['name'] == shift_data.get('name'):
                current_idx = i
        self.worker_combo.currentIndexChanged.connect(self.update_task_list)
        
        time_intervals = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        self.start_time = QComboBox()
        self.start_time.addItems(time_intervals)
        self.start_time.setCurrentText(shift_data.get('start_time', '09:00'))
        
        self.end_time = QComboBox()
        self.end_time.addItems(time_intervals)
        self.end_time.setCurrentText(shift_data.get('end_time', '17:00'))
        
        form.addRow("Worker:", self.worker_combo)
        form.addRow("Start:", self.start_time)
        form.addRow("End:", self.end_time)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Tasks:"))
        self.task_list = QListWidget()
        layout.addWidget(self.task_list)
        
        # Force an update for tasks relative to the selected worker initially
        self.worker_combo.setCurrentIndex(-1)
        self.worker_combo.setCurrentIndex(current_idx)
        
        selected_tasks = [t.strip() for t in shift_data.get('tasks', '').split(',')]
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.text() in selected_tasks:
                item.setCheckState(Qt.CheckState.Checked)
                
        btn_box = QHBoxLayout()
        self.update_btn = QPushButton("Update Shift")
        self.update_btn.clicked.connect(self.accept)
        
        self.delete_btn = QPushButton("Delete Shift")
        self.delete_btn.setStyleSheet("background-color: #D32F2F;")
        self.delete_btn.clicked.connect(self.delete_shift)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_box.addWidget(self.update_btn)
        btn_box.addWidget(self.delete_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)
        
        self.action = 'update'
        
    def update_task_list(self):
        self.task_list.clear()
        worker_data = self.worker_combo.currentData()
        if worker_data:
            role = worker_data.get('role')
            try:
                # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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
                
    def delete_shift(self):
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this shift?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.action = 'delete'
            self.accept()

    def get_data(self):
        worker_data = self.worker_combo.currentData()
        selected_tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_tasks.append(item.text())
                
        return {
            'action': self.action,
            'id': self.shift_data.get('id'),
            'worker_name': worker_data['name'] if worker_data else "",
            'role': worker_data['role'] if worker_data else "",
            'start_time': self.start_time.currentText(),
            'end_time': self.end_time.currentText(),
            'tasks': ", ".join(selected_tasks)
        }


class OccupancyWidget(QWidget):
    shiftClicked = pyqtSignal(dict)
    def __init__(self, start_hour, end_hour, shifts, show_actuals=False, parent=None):
        super().__init__(parent)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.shifts = shifts
        self.show_actuals = show_actuals
        self.setMinimumHeight(max(35, 12 + len(self.shifts) * 20))
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
            "Owner": QColor("#27BBF5"),    # Light Blue
            "Manager": QColor("#F59527"),  # Light Orange
            "Worker": QColor("#4CCC35")    # Light Green
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
            entry = shift.get('entry', s)
            
            # Ensure shifts stay within operational hours
            s_clamped = max(self.start_hour, min(s, self.end_hour))
            e_clamped = max(self.start_hour, min(e, self.end_hour))
            entry_clamped = max(self.start_hour, min(entry, self.end_hour))
            
            if e_clamped <= s_clamped: 
                continue
            
            x = ((s_clamped - self.start_hour) / total_hours) * width
            w = ((e_clamped - s_clamped) / total_hours) * width
            y = margin_y + i * shift_height
            
            if shift.get('is_voluntary'):
                color = QColor("#B3B39B") # greenish grey for Voluntary Shifts
            else:
                color = role_colors.get(shift.get('role', ''), QColor("#757575"))
                
            painter.setPen(Qt.PenStyle.NoPen)
            
            actual_shift_height = shift_height * (2 / 3)
            y_adjusted = y + (shift_height - actual_shift_height) / 2
            rect_f = QRectF(x, y_adjusted, w, actual_shift_height)
            
            painter.setBrush(color)
            painter.drawRoundedRect(rect_f, 2, 2)
            
            # Draw red overlay for late entry portion
            if self.show_actuals and entry_clamped > s_clamped:
                late_w = ((entry_clamped - s_clamped) / total_hours) * width
                late_rect_f = QRectF(x, y_adjusted, late_w, actual_shift_height)
                painter.setBrush(QColor("#EF5350")) # Red for late absent
                painter.drawRoundedRect(late_rect_f, 2, 2)
                
            self.shift_rects.append((rect_f, shift))
            
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            text_rect = QRectF(x, y_adjusted, w, actual_shift_height)
            if w > 30:
                shift_text = f"{shift.get('name', '')} ({shift.get('start_time', '')} - {shift.get('end_time', '')})"
                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(shift_text)
                
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, shift_text)
                
                if self.show_actuals and entry > s:
                    late_text = f" [Entry: {shift.get('entry_time')}]"
                    late_width = fm.horizontalAdvance(late_text)
                    center_x = x + w/2
                    start_x = center_x + text_width/2
                    late_text_rect = QRectF(start_x, y_adjusted, late_width, actual_shift_height)
                    painter.setPen(QColor("#FF0000")) # Draw late entry explicitly red
                    painter.drawText(late_text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, late_text)

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, shift in self.shift_rects:
            if rect.contains(pos):
                self.setToolTip(shift.get('tooltip', ''))
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        self.setToolTip('')
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for rect, shift in self.shift_rects:
                if rect.contains(pos):
                    self.shiftClicked.emit(shift)
                    return

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
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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


class BaseShiftManager(QWidget):
    def __init__(self, show_actuals=False):
        super().__init__()
        self._adjusting_heights = False
        self.current_date = datetime.now()
        self.show_actuals = show_actuals
        layout = QHBoxLayout(self)
        
        # Left Panel - Planning
        plan_layout = QVBoxLayout()
        self.plan_layout = plan_layout
        
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
        self.start_time = QComboBox()
        self.end_time = QComboBox()
        time_intervals = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        self.start_time.addItems(time_intervals)
        self.end_time.addItems(time_intervals)
        self.start_time.setCurrentText("09:00")
        self.end_time.setCurrentText("17:00")
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("End:"))
        time_layout.addWidget(self.end_time)
        plan_layout.addLayout(time_layout)
        
        # Planner Table
        self.table = QTableWidget(7, 3)
        timeline_lbl = "Shift Timeline (Actuals)" if self.show_actuals else "Shift Timeline"
        self.table.setHorizontalHeaderLabels(["Day", timeline_lbl, "Tasks"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            self.table.setItem(i, 0, QTableWidgetItem(day))
            self.table.setItem(i, 1, QTableWidgetItem("Unassigned"))
            self.table.setItem(i, 2, QTableWidgetItem(""))
        plan_layout.addWidget(self.table)
        
        original_resize = self.table.resizeEvent
        def resize_event_override(event):
            original_resize(event)
            self.adjust_row_heights()
        self.table.resizeEvent = resize_event_override
        
        assign_btn = QPushButton("Assign Selected Worker to Selected Day")
        assign_btn.clicked.connect(self.assign_shift)
        plan_layout.addWidget(assign_btn)
        
        vol_btn = QPushButton("Add Voluntary Shift")
        vol_btn.clicked.connect(self.add_voluntary_shift)
        plan_layout.addWidget(vol_btn)
        
        reset_btn = QPushButton("Reset Selected Day")
        reset_btn.clicked.connect(self.reset_row)
        plan_layout.addWidget(reset_btn)
        
        # Export layout
        export_layout = QHBoxLayout()
        btn_export_png = QPushButton("Export as PNG")
        btn_export_png.clicked.connect(self.export_png)
        btn_export_pdf = QPushButton("Export as PDF")
        btn_export_pdf.clicked.connect(self.export_pdf)
        export_layout.addWidget(btn_export_png)
        export_layout.addWidget(btn_export_pdf)
        plan_layout.addLayout(export_layout)
        
        # Right Panel - Task Map
        task_group = QGroupBox("Role Necessary Work List")
        task_layout = QVBoxLayout()
        self.task_list = QListWidget()
        task_layout.addWidget(self.task_list)
        task_group.setLayout(task_layout)
        
        layout.addLayout(plan_layout, 5)
        layout.addWidget(task_group, 1)

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
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            shifts = res.json()
            
            current_week_dates = []
            for i in range(7):
                item = self.table.item(i, 0)
                if item and '\n' in item.text():
                    current_week_dates.append(item.text().split('\n')[1])

            worker_hours = {}
            for s in shifts:
                if s.get("full_date") and s.get("start_time") and s.get("end_time"):
                    try:
                        dt = datetime.strptime(s["full_date"], "%Y-%m-%d")
                        w_name = s["worker_name"]
                        if w_name not in worker_hours:
                            worker_hours[w_name] = {'weekly': 0.0, 'monthly': 0.0, 'vol_weekly': 0.0, 'vol_monthly': 0.0}
                        entry_val = s.get("entry_time") or s["start_time"]
                        actual_start = max(self.time_to_float(s["start_time"]), self.time_to_float(entry_val))
                        hrs = max(0.0, self.time_to_float(s["end_time"]) - actual_start)
                        is_vol = s.get("is_voluntary", 0)
                        
                        if is_vol:
                            if dt.month == self.current_date.month and dt.year == self.current_date.year:
                                worker_hours[w_name]['vol_monthly'] += hrs
                            if dt.isocalendar()[1] == self.current_date.isocalendar()[1] and dt.year == self.current_date.year:
                                worker_hours[w_name]['vol_weekly'] += hrs
                        else:
                            if dt.month == self.current_date.month and dt.year == self.current_date.year:
                                worker_hours[w_name]['monthly'] += hrs
                            if dt.isocalendar()[1] == self.current_date.isocalendar()[1] and dt.year == self.current_date.year:
                                worker_hours[w_name]['weekly'] += hrs
                    except ValueError:
                        pass
            
            day_shifts = {day: [] for day in days}
            for shift in shifts:
                if shift.get("date") in days:
                    shift_full_date = shift.get("full_date")
                    if shift_full_date and shift_full_date not in current_week_dates:
                        continue
                    day_shifts[shift["date"]].append(shift)
                    
            for day, day_shift_list in day_shifts.items():
                if not day_shift_list:
                    continue
                row = days.index(day)
                
                start_hour = 10.0
                end_hour = 22.0
                for s in day_shift_list:
                    if s.get("start_time"):
                        start_hour = min(start_hour, int(self.time_to_float(s["start_time"])))
                    if s.get("end_time"):
                        end_hour = max(end_hour, int(self.time_to_float(s["end_time"])) + 1)
                
                parsed_shifts = []
                for s in day_shift_list:
                    wh = worker_hours.get(s['worker_name'], {'weekly': 0.0, 'monthly': 0.0, 'vol_weekly': 0.0, 'vol_monthly': 0.0})
                    type_str = "Voluntary" if s.get("is_voluntary") else "Regular"
                    display_role = "SalesEx" if s.get('role', '') == "Worker" else s.get('role', '')
                    tooltip = (f"Worker: {s['worker_name']}\nRole: {display_role}\n"
                               f"Shift: {s.get('start_time')} - {s.get('end_time')} ({type_str})\n"
                               f"Weekly Reg: {wh.get('weekly', 0):.1f}h | Vol: {wh.get('vol_weekly', 0):.1f}h\n"
                               f"Monthly Reg: {wh.get('monthly', 0):.1f}h | Vol: {wh.get('vol_monthly', 0):.1f}h")
                               
                    if s.get("start_time") and s.get("end_time"):
                        parsed_shifts.append({
                            'id': s.get('id'),
                            'start': self.time_to_float(s["start_time"]),
                            'entry': self.time_to_float(s.get("entry_time") or s["start_time"]),
                            'end': self.time_to_float(s["end_time"]),
                            'role': s.get('role', ''),
                            'name': s.get('worker_name', ''),
                            'tooltip': tooltip,
                            'is_voluntary': s.get("is_voluntary", 0),
                            'start_time': s.get('start_time'),
                            'entry_time': s.get('entry_time') or s.get('start_time'),
                            'end_time': s.get('end_time'),
                            'tasks': s.get('tasks', '')
                        })
                
                if parsed_shifts:
                    occupancy_widget = OccupancyWidget(start_hour, end_hour, parsed_shifts, show_actuals=self.show_actuals)
                    occupancy_widget.shiftClicked.connect(self.handle_shift_click)
                    self.table.setItem(row, 1, QTableWidgetItem(""))
                    self.table.setCellWidget(row, 1, occupancy_widget)

                tasks_container = QWidget()
                tasks_layout = QVBoxLayout(tasks_container)
                tasks_layout.setContentsMargins(4, 4, 4, 4)
                tasks_layout.setSpacing(6)
                
                for s in day_shift_list:
                    if s.get("tasks"):
                        display_role = "SalesEx" if s.get("role") == "Worker" else s.get("role", "")
                        icon = "👑" if display_role == "Owner" else "👔" if display_role == "Manager" else "🛒"
                        
                        shift_row_widget = QWidget()
                        shift_row_layout = QHBoxLayout(shift_row_widget)
                        shift_row_layout.setContentsMargins(0, 0, 0, 0)
                        shift_row_layout.setSpacing(6)
                        
                        worker_card = QFrame()
                        worker_card.setObjectName("workerCard")
                        worker_card.setStyleSheet("""
                            QFrame#workerCard {
                                background-color: #E3F2FD;
                                border: 1px solid #90CAF9;
                                border-radius: 6px;
                            }
                        """)
                        w_layout = QVBoxLayout(worker_card)
                        w_layout.setContentsMargins(8, 4, 8, 4)
                        header_lbl = QLabel(f"{icon} <b>{s['worker_name']} <br>({display_role})</b>")
                        header_lbl.setStyleSheet("border: none; background: transparent; color: #0D47A1; font-size: 12px;")
                        w_layout.addWidget(header_lbl)
                        
                        shift_row_layout.addWidget(worker_card, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                        
                        tasks_flow_widget = QWidget()
                        flow_layout = FlowLayout(tasks_flow_widget, margin=0, hSpacing=4, vSpacing=4, alignment=Qt.AlignmentFlag.AlignLeft)
                        
                        task_list = [t.strip() for t in s.get("tasks", "").split(",") if t.strip()]
                        for task in task_list:
                            card = QFrame()
                            card.setMaximumWidth(450)
                            card.setObjectName("taskCard")
                            card.setStyleSheet("""
                                QFrame#taskCard {
                                    background-color: #FFFFFF;
                                    border: 1px solid #E0E0E0;
                                    border-radius: 6px;
                                }
                            """)
                            card_layout = QVBoxLayout(card)
                            card_layout.setContentsMargins(8, 4, 8, 4)
                            
                            vol_mark = "<b style='color:#B3B39B;'>(Vol)</b> " if s.get("is_voluntary") else ""
                            tasks_lbl = QLabel(f"{vol_mark}{task}")
                            tasks_lbl.setWordWrap(True)
                            tasks_lbl.setStyleSheet("border: none; background: transparent; color: #546E7A; font-size: 11px;")
                            card_layout.addWidget(tasks_lbl)
                            
                            flow_layout.addWidget(card)
                            
                        shift_row_layout.addWidget(tasks_flow_widget, 1, Qt.AlignmentFlag.AlignTop)
                        tasks_layout.addWidget(shift_row_widget)
                        
                tasks_layout.addStretch()
                self.table.setItem(row, 2, QTableWidgetItem(""))
                self.table.setCellWidget(row, 2, tasks_container)
                
            self.adjust_row_heights()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load shifts: {e}")

    def handle_shift_click(self, shift_data):
        pass

    def load_worker_combo(self):
        self.worker_combo.clear()
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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
                # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a day (row) in the table first.")
            return
        
        worker_data = self.worker_combo.currentData()
        if not worker_data:
            QMessageBox.warning(self, "Warning", "Please select a worker first.")
            return
            
        day_text = self.table.item(current_row, 0).text()
        day = day_text.split('\n')[0]
        full_date_str = day_text.split('\n')[1] if '\n' in day_text else ""
        
        start_time_str = self.start_time.currentText()
        end_time_str = self.end_time.currentText()
        
        selected_tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_tasks.append(item.text())
                
        if not selected_tasks:
            QMessageBox.warning(self, "Warning", "Please select at least one task for this shift.")
            return
            
        tasks_str = ", ".join(selected_tasks)
        
        data = {
            "date": day,
            "full_date": full_date_str,
            "worker_name": worker_data['name'],
            "role": worker_data['role'],
            "start_time": start_time_str,
            "entry_time": start_time_str,
            "end_time": end_time_str,
            "tasks": tasks_str
        }
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.post(f"{API_URL}/shifts", json=data, timeout=3)
            res.raise_for_status()
            self.load_shifts()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error assigning shift: {e}")
            QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def add_voluntary_shift(self):
        worker_data = self.worker_combo.currentData()
        if not worker_data:
            QMessageBox.warning(self, "Warning", "Please select a worker first.")
            return
            
        if worker_data.get('role') not in ['Owner', 'Manager']:
            QMessageBox.warning(self, "Permission Denied", "Voluntary shifts can only be assigned to Owner or Manager roles.")
            return
            
        tasks = [self.task_list.item(i).text() for i in range(self.task_list.count())]
        dialog = VoluntaryShiftDialog(worker_data['name'], tasks, self)
        
        if dialog.exec():
            data_out = dialog.get_data()
            start_dt = data_out['start_dt']
            end_dt = data_out['end_dt']
            
            data = {
                "date": start_dt.strftime("%A"),
                "full_date": start_dt.strftime("%Y-%m-%d"),
                "worker_name": worker_data['name'],
                "role": worker_data['role'],
                "start_time": start_dt.strftime("%H:%M"),
                "entry_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M"),
                "tasks": data_out['tasks'],
                "is_voluntary": 1
            }
            
            try:
                # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
                res = requests.post(f"{API_URL}/shifts", json=data, timeout=3)
                res.raise_for_status()
                self.load_shifts()
            except requests.exceptions.RequestException as e:
                logging.error(f"Error assigning voluntary shift: {e}")
                QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def reset_row(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a day (row) in the table first.")
            return
            
        day_text = self.table.item(current_row, 0).text()
        day = day_text.split('\n')[0]
        full_date_str = day_text.split('\n')[1] if '\n' in day_text else ""
        
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.delete(f"{API_URL}/shifts/{day}?full_date={full_date_str}", timeout=3)
            res.raise_for_status()
            self.load_shifts()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error resetting row for {day}: {e}")
            QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

    def _get_export_dir(self):
        export_dir = os.path.join(os.getcwd(), "exports")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        return export_dir

    def _get_full_table_pixmap(self):
        original_min = self.table.minimumSize()
        original_max = self.table.maximumSize()
        original_size = self.table.size()
        original_h_policy = self.table.horizontalScrollBarPolicy()
        original_v_policy = self.table.verticalScrollBarPolicy()

        # Temporarily turn off scrollbars to prevent them from appearing in exports
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        total_width = int(self.table.verticalHeader().width() + self.table.horizontalHeader().length() + self.table.frameWidth() * 2)
        total_height = int(self.table.horizontalHeader().height() + self.table.verticalHeader().length() + self.table.frameWidth() * 2)
        
        # Temporarily stretch out the table bounds to capture its whole contents
        self.table.setFixedSize(total_width, total_height)
        QApplication.processEvents() 
        
        pixmap = self.table.grab()
        
        # Reset back to original metrics
        self.table.setMinimumSize(original_min)
        self.table.setMaximumSize(original_max)
        self.table.resize(original_size)
        self.table.setHorizontalScrollBarPolicy(original_h_policy)
        self.table.setVerticalScrollBarPolicy(original_v_policy)
        
        return pixmap

    def export_png(self):
        week_num = self.current_date.isocalendar()[1]
        monday = self.current_date - timedelta(days=self.current_date.weekday())
        sunday = monday + timedelta(days=6)
        date_range = f"{monday.strftime('%Y-%m-%d')}_to_{sunday.strftime('%Y-%m-%d')}"
        default_filename = f"shift_plan_CW{week_num}_{date_range}.png"
        default_path = os.path.join(self._get_export_dir(), default_filename)

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Shift Plan as PNG", default_path, "PNG Image (*.png)")
        if file_path:
            pixmap = self._get_full_table_pixmap()
            pixmap.save(file_path, "PNG")
            QMessageBox.information(self, "Success", f"Shift plan exported as PNG to:\n{file_path}")

    def export_pdf(self):
        week_num = self.current_date.isocalendar()[1]
        monday = self.current_date - timedelta(days=self.current_date.weekday())
        sunday = monday + timedelta(days=6)
        date_range = f"{monday.strftime('%Y-%m-%d')}_to_{sunday.strftime('%Y-%m-%d')}"
        default_filename = f"shift_plan_CW{week_num}_{date_range}.pdf"
        default_path = os.path.join(self._get_export_dir(), default_filename)

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Shift Plan as PDF", default_path, "PDF Document (*.pdf)")
        if file_path:
            pixmap = self._get_full_table_pixmap()
            writer = QPdfWriter(file_path)
            
            page_layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), 
                                      QPageLayout.Orientation.Landscape, 
                                      QMarginsF(15, 15, 15, 15),
                                      QPageLayout.Unit.Millimeter)
            writer.setPageLayout(page_layout)
            
            painter = QPainter(writer)
            rect = painter.viewport()
            size = pixmap.size()
            size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            QMessageBox.information(self, "Success", f"Shift plan exported as PDF to:\n{file_path}")

    def adjust_row_heights(self):
        if getattr(self, '_adjusting_heights', False):
            return
        self._adjusting_heights = True
        try:
            for i in range(7):
                widget1 = self.table.cellWidget(i, 1)
                widget2 = self.table.cellWidget(i, 2)
                
                h1 = widget1.minimumHeight() + 8 if widget1 else 30
                h2 = 10
                
                if widget2 and widget2.layout():
                    col_width = self.table.columnWidth(2)
                    if col_width < 50:
                        col_width = 300
                        
                    v_layout = widget2.layout()
                    margins = v_layout.contentsMargins()
                    h2 = margins.top() + margins.bottom()
                    
                    actual_items = 0
                    for c in range(v_layout.count()):
                        item = v_layout.itemAt(c)
                        if item and item.widget() and item.widget().layout():
                            child_layout = item.widget().layout()
                            if isinstance(child_layout, QHBoxLayout) and child_layout.count() >= 2:
                                w_card = child_layout.itemAt(0).widget()
                                t_flow = child_layout.itemAt(1).widget()
                                
                                if w_card and t_flow and t_flow.layout() and isinstance(t_flow.layout(), FlowLayout):
                                    flow_width = col_width - w_card.sizeHint().width() - child_layout.spacing() - margins.left() - margins.right() - 5
                                    flow_h = t_flow.layout().heightForWidth(max(10, flow_width))
                                    
                                    if actual_items > 0:
                                        h2 += v_layout.spacing()
                                    h2 += max(w_card.sizeHint().height(), flow_h)
                                    actual_items += 1
                    if actual_items == 0:
                        h2 = 30
                self.table.setRowHeight(i, int(max(30, h1, h2)))
        finally:
            self._adjusting_heights = False

class ShiftPlanner(BaseShiftManager):
    def __init__(self):
        super().__init__(show_actuals=False)
        self.load_worker_combo()
        self.load_shifts()

    def handle_shift_click(self, shift_data):
        self.edit_shift(shift_data)

    def edit_shift(self, shift_data):
        workers = []
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.get(f"{API_URL}/workers", timeout=3)
            res.raise_for_status()
            workers = res.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to load workers for editing shift: {e}")
            QMessageBox.critical(self, "Error", f"Cannot load workers: {e}")
            return
            
        dialog = EditShiftDialog(shift_data, workers, self)
        if dialog.exec():
            data_out = dialog.get_data()
            shift_id = data_out['id']
            if data_out['action'] == 'delete':
                try:
                    # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
                    res = requests.delete(f"{API_URL}/shifts/{shift_id}", timeout=3)
                    res.raise_for_status()
                    self.load_shifts()
                except requests.exceptions.RequestException as e:
                    logging.error(f"Error deleting shift: {e}")
                    QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")
            elif data_out['action'] == 'update':
                data = {
                    "worker_name": data_out['worker_name'],
                    "role": data_out['role'],
                    "start_time": data_out['start_time'],
                    "end_time": data_out['end_time'],
                    "tasks": data_out['tasks']
                }
                try:
                    # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
                    res = requests.put(f"{API_URL}/shifts/{shift_id}", json=data, timeout=3)
                    res.raise_for_status()
                    self.load_shifts()
                except requests.exceptions.RequestException as e:
                    logging.error(f"Error updating shift: {e}")
                    QMessageBox.critical(self, "Error", f"Cannot connect to Flask Backend.\n\nDetails: {e}")

class WeeklyOperationalOverview(BaseShiftManager):
    def __init__(self):
        super().__init__(show_actuals=True)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Click on any shift bar below to register a late entry / actual arrival.</b>"))
        header_layout.addStretch()
        refresh_btn = QPushButton("Refresh Overview")
        refresh_btn.clicked.connect(self.load_shifts)
        header_layout.addWidget(refresh_btn)
        
        self.plan_layout.insertLayout(0, header_layout)
        
        self.load_worker_combo()
        self.load_shifts()

    def handle_shift_click(self, shift_data):
        self.set_late_entry(shift_data)

    def set_late_entry(self, shift_data):
        dialog = SetLateEntryDialog(shift_data, self)
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
                res = requests.put(f"{API_URL}/shifts/{shift_data['id']}", json=new_data, timeout=3)
                res.raise_for_status()
                self.load_shifts()
            except Exception as e:
                logging.error(f"Error saving late entry: {e}")
                QMessageBox.critical(self, "Error", f"Could not save: {e}")

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
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
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
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            for s in res.json():
                if s.get('worker_name') == worker_name:
                    type_prefix = "[Vol] " if s.get('is_voluntary') else ""
                    entry_str = s.get('entry_time') or s.get('start_time')
                    late_info = f" [Entry: {entry_str}]" if entry_str != s.get('start_time') else ""
                    disp = f"{type_prefix}{s.get('full_date', s.get('date'))} ({s.get('start_time')} - {s.get('end_time')}){late_info}"
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
            entry_time_str = shift_data.get('entry_time') or shift_data.get('start_time', '00:00')
            e1, em1 = map(int, entry_time_str.split(':'))
            
            actual_start = max(h1 + m1/60.0, e1 + em1/60.0)
            self.total_assigned_hours = (h2 + m2/60.0) - actual_start
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
        
        # Late Entry Controller
        late_entry_layout = QHBoxLayout()
        entry_time_str = shift_data.get('entry_time') or shift_data.get('start_time', '00:00')
        self.ts_entry_label = QLabel(entry_time_str)
        
        late_entry_layout.addWidget(QLabel("<b>Late Entry / Actual Arrival:</b>"))
        late_entry_layout.addWidget(self.ts_entry_label)
        late_entry_layout.addStretch()
        self.tasks_layout.addLayout(late_entry_layout)

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
        
        # TODO: Ensure timesheet_data always passes cleanly through json.dumps() to prevent malformed string errors.
        payload = {
            'timesheet_data': json.dumps(ts_data)
        }
        
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.put(f"{API_URL}/shifts/{self.current_shift_id}", 
                               json=payload, timeout=3)
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
        
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Worker", "Regular Hours", "Voluntary Hours", "Absent/Late Hours", "Completed Tasks", "Pending/Working Tasks"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.load_stats()
        
    def load_stats(self):
        try:
            # TODO: Offload this HTTP request to a QThread to prevent blocking the main GUI thread.
            res = requests.get(f"{API_URL}/shifts", timeout=3)
            res.raise_for_status()
            shifts = res.json()
            
            stats = {}
            for s in shifts:
                w = s.get('worker_name')
                if not w: continue
                if w not in stats:
                    stats[w] = {'reg_hours': 0.0, 'vol_hours': 0.0, 'absent_hours': 0.0, 'completed': 0, 'pending': 0}
                    
                try:
                    h1, m1 = map(int, s['start_time'].split(':'))
                    h2, m2 = map(int, s['end_time'].split(':'))
                    e1, em1 = map(int, (s.get('entry_time') or s['start_time']).split(':'))
                    
                    start_flt = h1 + m1/60.0
                    end_flt = h2 + m2/60.0
                    actual_start = max(start_flt, e1 + em1/60.0)
                    hrs = max(0.0, end_flt - actual_start)
                    absent = max(0.0, actual_start - start_flt)
                    
                    if s.get('is_voluntary'):
                        stats[w]['vol_hours'] += hrs
                    else:
                        stats[w]['reg_hours'] += hrs
                    stats[w]['absent_hours'] += absent
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
                self.table.setItem(row, 1, QTableWidgetItem(f"{data['reg_hours']:.1f} hr(s)"))
                self.table.setItem(row, 2, QTableWidgetItem(f"{data['vol_hours']:.1f} hr(s)"))
                self.table.setItem(row, 3, QTableWidgetItem(f"-{data['absent_hours']:.1f} hr(s)"))
                self.table.setItem(row, 4, QTableWidgetItem(str(data['completed'])))
                self.table.setItem(row, 5, QTableWidgetItem(str(data['pending'])))
                
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
        btn_overview = QPushButton("Weekly Operational Overview")
        btn_stats = QPushButton("Statistics")
        
        btn_registry.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        btn_planner.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        btn_timesheet.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        btn_overview.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        btn_stats.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        
        sidebar_layout.addWidget(btn_registry)
        sidebar_layout.addWidget(btn_planner)
        sidebar_layout.addWidget(btn_timesheet)
        sidebar_layout.addWidget(btn_overview)
        sidebar_layout.addWidget(btn_stats)
        
        # Stacked Widget to hold different views
        self.stacked_widget = QStackedWidget()
        self.worker_registry = WorkerRegistry()
        self.shift_planner = ShiftPlanner()
        self.timesheet_widget = EmployeeTimesheet()
        self.overview_widget = WeeklyOperationalOverview()
        self.stats_widget = StatisticsWidget()
        self.stacked_widget.addWidget(self.worker_registry)
        self.stacked_widget.addWidget(self.shift_planner)
        self.stacked_widget.addWidget(self.timesheet_widget)
        self.stacked_widget.addWidget(self.overview_widget)
        self.stacked_widget.addWidget(self.stats_widget)
        self.update_week_label()
        
        content_layout.addLayout(sidebar_layout, 1)
        content_layout.addWidget(self.stacked_widget, 8)
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
            self.shift_planner.load_shifts()
        if hasattr(self, 'overview_widget'):
            self.overview_widget.update_dates(self.current_date)
            self.overview_widget.load_shifts()

    def open_calendar(self):
        dialog = CalendarDialog(self)
        if dialog.exec():
            self.current_date = dialog.get_date()
            self.update_week_label()

if __name__ == '__main__':
    # Start the Flask backend server in a background daemon thread
    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()

    # TODO: Add a startup retry mechanism or wait screen to handle the Flask server startup race condition.
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
