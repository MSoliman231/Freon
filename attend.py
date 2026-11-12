import calendar
import json
import os
from datetime import date, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QStyledItemDelegate,
    QDialog, QCheckBox, QScrollArea, QDialogButtonBox, QInputDialog,
    QMessageBox, QMenu
)
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtCore import Qt, Signal

import auth
import i18n
import payroll
import payslip
import resources
from i18n import tr
from settings import SettingsWindow

DATA_FILE = Path(__file__).resolve().parent / "attendance_data.json"

# Click a cell to cycle through these states (stored in English in the file)
STATES = ["", "Present", "Late-1", "Late-2", "Absent"]
STATE_COLORS = {  # state: (background, text)
    "Present": ("#2e7d32", "white"),
    "Late-1": ("#f9a825", "black"),
    "Late-2": ("#ef6c00", "white"),
    "Absent": ("#c62828", "white"),
}
LEGACY_STATES = {"Late": "Late-1"}  # old saved data used plain "Late"


def show_message(parent, title, text, icon_name, warning=False):
    """Message box that uses one of our own window icons."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setWindowIcon(resources.icon(icon_name))
    box.setIcon(QMessageBox.Warning if warning else QMessageBox.Information)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Ok)
    box.button(QMessageBox.Ok).setText(tr("OK"))
    box.exec()


class ClickTable(QTableWidget):
    """Emits cellTapped on every left press, including the second click of
    a fast double-click, so quick clicking cycles quickly."""
    cellTapped = Signal(int, int)

    def _tap(self, event):
        if event.button() == Qt.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self.cellTapped.emit(index.row(), index.column())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._tap(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self._tap(event)


class RowOutlineDelegate(QStyledItemDelegate):
    """Draws a thick blue outline around every cell of one row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outlined_row = None

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.row() != self.outlined_row:
            return

        painter.save()
        painter.setPen(QPen(QColor("#1976d2"), 4))
        r = option.rect.adjusted(2, 2, -2, -2)
        painter.drawLine(r.topLeft(), r.topRight())
        painter.drawLine(r.bottomLeft(), r.bottomRight())
        if index.column() == 0:
            painter.drawLine(r.topLeft(), r.bottomLeft())
        if index.column() == index.model().columnCount() - 1:
            painter.drawLine(r.topRight(), r.bottomRight())
        painter.restore()


class ExportDialog(QDialog):
    """Small window with a checkbox for each name."""

    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Export"))
        self.setWindowIcon(resources.icon("export.png"))
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Choose the names to export:")))

        self.select_all = QCheckBox(tr("Select all"))
        self.select_all.clicked.connect(self.toggle_all)
        layout.addWidget(self.select_all)

        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        self.checkboxes = []
        for name in names:
            box = QCheckBox(name)
            box.toggled.connect(self.update_state)
            holder_layout.addWidget(box)
            self.checkboxes.append(box)
        holder_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setMinimumHeight(200)
        layout.addWidget(scroll)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.buttons.button(QDialogButtonBox.Ok).setText(tr("Export"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.update_state()

    def toggle_all(self, checked):
        for box in self.checkboxes:
            box.setChecked(checked)

    def update_state(self):
        checked = [b for b in self.checkboxes if b.isChecked()]
        self.select_all.blockSignals(True)
        self.select_all.setChecked(
            bool(self.checkboxes) and len(checked) == len(self.checkboxes)
        )
        self.select_all.blockSignals(False)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(checked))

    def selected_names(self):
        return [b.text() for b in self.checkboxes if b.isChecked()]


class AttendancePage(QWidget):
    def __init__(self, on_lock=None):
        super().__init__()
        self.on_lock = on_lock

        today = date.today()
        self.year = today.year
        self.month = today.month
        self.names = []
        self.records = {}  # (year, month, name) -> {day: state}
        self.notes = {}    # (year, month, name) -> {day: money borrowed}

        self.load_data()

        layout = QVBoxLayout(self)

        # ---------- Top bar: lock + settings + month navigation ----------
        top_bar = QHBoxLayout()
        self.lock_button = QPushButton(tr("Lock"))
        self.lock_button.setFixedWidth(100)
        self.lock_button.clicked.connect(self.lock)

        self.settings_button = QPushButton(tr("Settings"))
        self.settings_button.setFixedWidth(100)
        self.settings_button.clicked.connect(self.open_settings)

        # Arrows point the right way in both languages
        rtl = i18n.is_rtl()
        self.prev_button = QPushButton("▶" if rtl else "◀")
        self.prev_button.setFixedWidth(40)
        self.prev_button.clicked.connect(lambda: self.change_month(-1))

        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setMinimumWidth(180)
        self.month_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.next_button = QPushButton("◀" if rtl else "▶")
        self.next_button.setFixedWidth(40)
        self.next_button.clicked.connect(lambda: self.change_month(1))

        top_bar.addWidget(self.lock_button)
        top_bar.addWidget(self.settings_button)
        top_bar.addStretch()
        top_bar.addWidget(self.prev_button)
        top_bar.addWidget(self.month_label)
        top_bar.addWidget(self.next_button)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # ---------- Name input ----------
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("Type a name and press Enter"))
        self.name_input.returnPressed.connect(self.add_name)
        layout.addWidget(self.name_input)

        # ---------- Attendance table (full width) ----------
        self.table = ClickTable()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.horizontalHeader().setDefaultSectionSize(80)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setSectionsClickable(True)
        self.table.cellTapped.connect(self.on_cell_clicked)
        self.table.verticalHeader().sectionClicked.connect(self.on_name_clicked)
        self.table.verticalHeader().sectionDoubleClicked.connect(self.rename_name)

        # Right click on a day opens the note menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_cell_menu)

        self.outline_delegate = RowOutlineDelegate(self.table)
        self.table.setItemDelegate(self.outline_delegate)
        layout.addWidget(self.table)

        hint = QLabel(tr(i18n.HINT))
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ---------- Bottom bar: delete and export ----------
        bottom_bar = QHBoxLayout()
        self.delete_button = QPushButton(tr("Delete name"))
        self.delete_button.setFixedWidth(120)
        self.delete_button.clicked.connect(self.delete_selected_name)
        bottom_bar.addWidget(self.delete_button)
        bottom_bar.addStretch()
        self.export_button = QPushButton(tr("Export"))
        self.export_button.setFixedWidth(120)
        self.export_button.clicked.connect(self.open_export_dialog)
        bottom_bar.addWidget(self.export_button)
        layout.addLayout(bottom_bar)

        self.refresh_table()

    # ---------- Saving / loading ----------
    def save_data(self):
        data = {"names": self.names, "records": {}, "notes": {}}
        for (year, month, name), days in self.records.items():
            days = {str(d): s for d, s in days.items() if s}
            if not days:
                continue
            key = f"{year}-{month:02d}"
            data["records"].setdefault(key, {})[name] = days

        for (year, month, name), days in self.notes.items():
            days = {str(d): a for d, a in days.items() if a > 0}
            if not days:
                continue
            key = f"{year}-{month:02d}"
            data["notes"].setdefault(key, {})[name] = days

        tmp = DATA_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)
        except OSError as e:
            print(f"Could not save attendance: {e}")

    def load_data(self):
        if not DATA_FILE.exists():
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.names = list(data.get("names", []))
            for key, people in data.get("records", {}).items():
                year, month = map(int, key.split("-"))
                for name, days in people.items():
                    self.records[(year, month, name)] = {
                        int(d): LEGACY_STATES.get(s, s) for d, s in days.items()
                    }
            for key, people in data.get("notes", {}).items():
                year, month = map(int, key.split("-"))
                for name, days in people.items():
                    self.notes[(year, month, name)] = {
                        int(d): float(a) for d, a in days.items()
                    }
        except (OSError, ValueError, AttributeError) as e:
            print(f"Could not load attendance: {e}")

    # ---------- Names ----------
    def add_name(self):
        name = self.name_input.text().strip()
        if name and name not in self.names:
            self.names.append(name)
            self.save_data()
            self.refresh_table()
        self.name_input.clear()

    def on_name_clicked(self, row):
        # Click again on the same name to remove the outline
        if self.outline_delegate.outlined_row == row:
            self.outline_delegate.outlined_row = None
        else:
            self.outline_delegate.outlined_row = row
        self.table.viewport().update()
        
    def rename_name(self, row):
        if row < 0 or row >= len(self.names):
            return
        old = self.names[row]

        dialog = QInputDialog(self)
        dialog.setWindowTitle(tr("Edit name"))
        dialog.setLabelText(tr('Enter the new name for "{name}":', name=old))
        dialog.setTextValue(old)
        dialog.setOkButtonText(tr("OK"))
        dialog.setCancelButtonText(tr("Cancel"))
        if dialog.exec() != QDialog.Accepted:
            return

        new = dialog.textValue().strip()
        if not new or new == old:
            return
        if new in self.names:
            show_message(
                self, tr("Edit name"),
                tr('"{name}" already exists.', name=new),
                "icon.png", warning=True
            )
            return

        # Move all their records, notes and salary to the new name
        self.names[row] = new
        self.records = {
            (y, m, new if n == old else n): v for (y, m, n), v in self.records.items()
        }
        self.notes = {
            (y, m, new if n == old else n): v for (y, m, n), v in self.notes.items()
        }
        payroll.rename_name(old, new)

        self.outline_delegate.outlined_row = row
        self.save_data()
        self.refresh_table()

    def ask_delete_password(self, name):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(tr("Confirm delete"))
        dialog.setWindowIcon(resources.icon("delete.png"))
        dialog.setLabelText(
            tr('Enter the password to delete "{name}" and all of their records:', name=name)
        )
        dialog.setTextEchoMode(QLineEdit.Password)
        dialog.setOkButtonText(tr("OK"))
        dialog.setCancelButtonText(tr("Cancel"))
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.textValue()

    def delete_selected_name(self):
        row = self.outline_delegate.outlined_row
        if row is None or row >= len(self.names):
            show_message(
                self, tr("Delete name"),
                tr("Click a name on the left first, then press Delete name."),
                "delete.png"
            )
            return

        name = self.names[row]
        password = self.ask_delete_password(name)
        if password is None:
            return
        if not auth.verify_password(password):
            show_message(
                self, tr("Wrong password"),
                tr("Wrong password. Nothing was deleted."),
                "delete.png", warning=True
            )
            return

        self.names.pop(row)
        self.records = {k: v for k, v in self.records.items() if k[2] != name}
        self.notes = {k: v for k, v in self.notes.items() if k[2] != name}
        payroll.remove_name(name)
        self.outline_delegate.outlined_row = None
        self.save_data()
        self.refresh_table()

    # ---------- Months ----------
    def change_month(self, step):
        self.month += step
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1
        self.refresh_table()

    # ---------- Table ----------
    def get_state(self, name, day):
        return self.records.get((self.year, self.month, name), {}).get(day, "")

    def set_state(self, name, day, state):
        key = (self.year, self.month, name)
        self.records.setdefault(key, {})[day] = state

    def get_note(self, name, day):
        return self.notes.get((self.year, self.month, name), {}).get(day, 0.0)

    def set_note(self, name, day, amount):
        key = (self.year, self.month, name)
        if amount > 0:
            self.notes.setdefault(key, {})[day] = amount
        else:
            self.notes.get(key, {}).pop(day, None)

    def borrowed_total(self, name, year, month):
        """Total money borrowed by a name in a month (to subtract from salary)."""
        return sum(self.notes.get((year, month, name), {}).values())

    def make_item(self, state, note=0.0):
        lines = [tr(state)] if state else []
        if note > 0:
            lines.append(f"-{payroll.format_amount(note)}")

        item = QTableWidgetItem("\n".join(lines))
        item.setTextAlignment(Qt.AlignCenter)
        if state in STATE_COLORS:
            bg, fg = STATE_COLORS[state]
            item.setBackground(QBrush(QColor(bg)))
            item.setForeground(QBrush(QColor(fg)))
        if note > 0:
            item.setToolTip(tr("Borrowed: {amount}", amount=payroll.format_amount(note)))
        return item

    def refresh_table(self):
        days = calendar.monthrange(self.year, self.month)[1]
        self.month_label.setText(f"{i18n.month_name(self.month)} {self.year}")

        self.table.clear()
        self.table.setColumnCount(days)
        self.table.setRowCount(len(self.names))

        headers = []
        for d in range(1, days + 1):
            weekday = date(self.year, self.month, d).weekday()
            headers.append(f"{d}\n{i18n.day_abbr(weekday)}")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setVerticalHeaderLabels(self.names)

        for row, name in enumerate(self.names):
            for col in range(days):
                day = col + 1
                self.table.setItem(
                    row, col,
                    self.make_item(self.get_state(name, day), self.get_note(name, day))
                )

    def on_cell_clicked(self, row, col):
        name = self.names[row]
        day = col + 1
        current = self.get_state(name, day)
        new_state = STATES[(STATES.index(current) + 1) % len(STATES)]
        self.set_state(name, day, new_state)
        self.table.setItem(row, col, self.make_item(new_state, self.get_note(name, day)))
        self.save_data()  # auto-save on every edit

    # ---------- Notes (right click) ----------
    def show_cell_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row, col = index.row(), index.column()
        name = self.names[row]
        day = col + 1
        has_note = self.get_note(name, day) > 0

        menu = QMenu(self)
        add_action = menu.addAction(tr("Edit note") if has_note else tr("Add note"))
        remove_action = menu.addAction(tr("Remove note")) if has_note else None

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == add_action:
            self.add_note(row, col)
        elif chosen == remove_action:
            self.set_note(name, day, 0)
            self.update_cell(row, col)
            self.save_data()

    def add_note(self, row, col):
        name = self.names[row]
        day = col + 1

        dialog = QInputDialog(self)
        dialog.setWindowTitle(tr("Add note"))
        dialog.setInputMode(QInputDialog.DoubleInput)
        dialog.setDoubleRange(0, 1_000_000_000)
        dialog.setDoubleDecimals(2)
        dialog.setDoubleValue(self.get_note(name, day))
        dialog.setLabelText(tr(
            "Money {name} borrowed on {day} {month}\n(it will be subtracted from their salary):",
            name=name, day=day, month=i18n.month_name(self.month)
        ))
        dialog.setOkButtonText(tr("OK"))
        dialog.setCancelButtonText(tr("Cancel"))
        if dialog.exec() != QDialog.Accepted:
            return

        self.set_note(name, day, dialog.doubleValue())
        self.update_cell(row, col)
        self.save_data()

    def update_cell(self, row, col):
        name = self.names[row]
        day = col + 1
        self.table.setItem(
            row, col,
            self.make_item(self.get_state(name, day), self.get_note(name, day))
        )

    # ---------- Export ----------
    def open_export_dialog(self):
        dialog = ExportDialog(self.names, self)
        if dialog.exec() == QDialog.Accepted:
            self.export_names(dialog.selected_names())

    def confirm_missing_salary(self, names):
        quoted = ", ".join(f'"{n}"' for n in names)
        key = "{names} doesn't have a salary yet." if len(names) == 1 \
            else "{names} don't have a salary yet."

        box = QMessageBox(self)
        box.setWindowTitle(tr("Salary missing"))
        box.setWindowIcon(resources.icon("export.png"))
        box.setIcon(QMessageBox.Warning)
        box.setText(tr(key, names=quoted) + "\n\n" + tr("Proceed anyway?"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText(tr("Yes"))
        box.button(QMessageBox.No).setText(tr("No"))
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def export_names(self, selected_names):
        if not selected_names:
            return
        rules = payroll.load_rules()  # always the latest salaries and rules

        # Warn about names that have no salary yet
        missing = [n for n in selected_names if rules["salaries"].get(n) is None]
        if missing and not self.confirm_missing_salary(missing):
            return

        now = datetime.now()
        slips = [
            payslip.build_slip(
                name, self.year, self.month,
                self.records, self.notes, rules, now
            )
            for name in selected_names
        ]
        preview = payslip.PayslipPreviewDialog(slips, self)
        preview.exec()

    # ---------- Settings / Lock ----------
    def open_settings(self):
        self.settings_window = SettingsWindow(self, self.names)
        self.settings_window.exec()

    def lock(self):
        if self.on_lock:
            self.on_lock()