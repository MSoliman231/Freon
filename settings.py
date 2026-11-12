import re
import smtplib
from email.message import EmailMessage

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QStackedWidget, QListWidget, QDoubleSpinBox, QGroupBox,
    QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal

import auth
import payroll
import resources
from i18n import tr
from pathlib import Path

# ---------- Email sender settings ----------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = "freon.support@gmail.com"


def _load_app_password():
    """Reads the Gmail app password from email_password.txt (never uploaded to GitHub)."""
    try:
        text = (Path(__file__).resolve().parent / "email_password.txt").read_text(encoding="utf-8")
        return text.strip() or "your_app_password"
    except OSError:
        return "your_app_password"


SENDER_APP_PASSWORD = _load_app_password()
# -------------------------------------------

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_is_configured():
    return (
        SENDER_EMAIL != "your_email@gmail.com"
        and SENDER_APP_PASSWORD != "your_app_password"
    )


def send_password_email(to_addr, new_password):
    msg = EmailMessage()
    msg["Subject"] = tr("FREON - your new password")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_addr
    msg.set_content(tr("Your new FREON password is: {password}", password=new_password))

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.send_message(msg)


class EmailWorker(QThread):
    """Sends the email in the background so the window doesn't freeze."""
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, to_addr, new_password, parent=None):
        super().__init__(parent)
        self.to_addr = to_addr
        self.new_password = new_password

    def run(self):
        try:
            send_password_email(self.to_addr, self.new_password)
            self.succeeded.emit()
        except smtplib.SMTPAuthenticationError:
            self.failed.emit(tr("Login failed. Check the sender email and app password in settings.py."))
        except Exception as e:
            self.failed.emit(tr("Could not send the email: {error}", error=e))


class ChangePasswordPage(QWidget):
    def __init__(self, on_back):
        super().__init__()
        self.worker = None
        self.pending_password = None
        self.pending_email = None

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        back = QPushButton(tr("← Back"))
        back.setFixedWidth(100)
        back.clicked.connect(on_back)
        top.addWidget(back)
        top.addStretch()
        layout.addLayout(top)

        title = QLabel(tr("Change password"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel(tr("Enter the email that should receive the new password."))
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        self.email_input.setLayoutDirection(Qt.LeftToRight)  # emails are always left-to-right
        self.email_input.setText(auth.get_email())  # the email from the first-start setup
        self.email_input.returnPressed.connect(self.start_send)
        layout.addWidget(self.email_input)

        self.send_button = QPushButton(tr("Generate and send new password"))
        self.send_button.clicked.connect(self.start_send)
        layout.addWidget(self.send_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def show_status(self, text, error=False):
        self.status_label.setStyleSheet("color: red;" if error else "")
        self.status_label.setText(text)

    def set_busy(self, busy):
        self.send_button.setEnabled(not busy)
        self.email_input.setEnabled(not busy)

    def start_send(self):
        email = self.email_input.text().strip()
        if not EMAIL_PATTERN.match(email):
            self.show_status(tr("Please enter a valid email address."), error=True)
            return
        if not email_is_configured():
            self.show_status(
                tr("The sender email is not set up yet. Fill it in at the top of settings.py."),
                error=True
            )
            return

        self.pending_password = auth.generate_password()
        self.pending_email = email
        self.set_busy(True)
        self.show_status(tr("Sending..."))

        self.worker = EmailWorker(email, self.pending_password, self)
        self.worker.succeeded.connect(self.on_sent)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_sent(self):
        # The password only changes after the email was sent successfully
        try:
            auth.set_password(self.pending_password, email=self.pending_email)
        except OSError as e:
            self.show_status(
                tr("The email was sent but the password could not be saved ({error}). The old password is still active.", error=e),
                error=True
            )
        else:
            self.show_status(
                tr("New password sent to {email}. Use it the next time you unlock.",
                   email=self.pending_email)
            )
        self.pending_password = None
        self.pending_email = None
        self.set_busy(False)

    def on_failed(self, message):
        self.pending_password = None
        self.pending_email = None
        self.show_status(message + " " + tr("Your password was not changed."), error=True)
        self.set_busy(False)

    def wait_for_worker(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(20000)


class RulesPage(QWidget):
    def __init__(self, on_back, names):
        super().__init__()
        self.names = list(names)
        self.rules = payroll.load_rules()

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        back = QPushButton(tr("← Back"))
        back.setFixedWidth(100)
        back.clicked.connect(on_back)
        top.addWidget(back)
        top.addStretch()
        layout.addLayout(top)

        title = QLabel(tr("Attendance rules (salary)"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # ---------- Names and salary ----------
        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel(tr("Select a name:")))
        self.name_list = QListWidget()
        self.name_list.currentRowChanged.connect(self.on_name_selected)
        left.addWidget(self.name_list)

        right = QVBoxLayout()
        self.selected_label = QLabel("")
        self.selected_label.setStyleSheet("font-weight: bold;")
        self.salary_input = self.make_spin()
        self.salary_input.setLayoutDirection(Qt.LeftToRight)  # numbers stay left-to-right
        self.salary_input.setEnabled(False)
        self.salary_input.valueChanged.connect(self.on_salary_changed)
        right.addWidget(self.selected_label)
        right.addWidget(QLabel(tr("Salary:")))
        right.addWidget(self.salary_input)
        right.addStretch()

        body.addLayout(left, 1)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

        # ---------- Rules that apply to all names ----------
        group = QGroupBox(tr("Rules for all names (amount deducted each time)"))
        form = QFormLayout(group)
        for state in payroll.RULE_STATES:
            spin = self.make_spin()
            spin.setLayoutDirection(Qt.LeftToRight)
            spin.setValue(self.rules["deductions"][state])
            spin.valueChanged.connect(
                lambda value, s=state: self.on_deduction_changed(s, value)
            )
            form.addRow(tr(state), spin)
        layout.addWidget(group)

        self.refresh_list()
        if self.names:
            self.selected_label.setText(tr("Select a name on the left"))
        else:
            self.selected_label.setText(tr("No names yet. Add names on the attendance page."))

    @staticmethod
    def make_spin():
        spin = QDoubleSpinBox()
        spin.setRange(0, 100_000_000)
        spin.setDecimals(2)
        spin.setKeyboardTracking(False)  # saves when you press Enter or leave the field
        return spin

    def refresh_list(self):
        row = self.name_list.currentRow()
        self.name_list.blockSignals(True)
        self.name_list.clear()
        for name in self.names:
            salary = self.rules["salaries"].get(name)
            if salary is None:
                self.name_list.addItem(name)
            else:
                self.name_list.addItem(f"{name}  —  {payroll.format_amount(salary)}")
        self.name_list.setCurrentRow(row)
        self.name_list.blockSignals(False)

    def on_name_selected(self, row):
        if row < 0 or row >= len(self.names):
            self.salary_input.setEnabled(False)
            return
        name = self.names[row]
        self.selected_label.setText(tr("Salary for {name}", name=name))
        self.salary_input.blockSignals(True)
        self.salary_input.setValue(self.rules["salaries"].get(name, 0.0))
        self.salary_input.blockSignals(False)
        self.salary_input.setEnabled(True)

    def on_salary_changed(self, value):
        row = self.name_list.currentRow()
        if row < 0 or row >= len(self.names):
            return
        self.rules["salaries"][self.names[row]] = value
        payroll.save_rules(self.rules)
        self.refresh_list()

    def on_deduction_changed(self, state, value):
        self.rules["deductions"][state] = value
        payroll.save_rules(self.rules)


class SettingsWindow(QDialog):
    def __init__(self, parent=None, names=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.setWindowIcon(resources.icon("settings.png"))
        self.resize(720, 540)

        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.addWidget(self.stack)

        self.menu_page = self.build_menu()
        self.password_page = ChangePasswordPage(on_back=self.show_menu)
        self.rules_page = RulesPage(on_back=self.show_menu, names=names or [])

        self.stack.addWidget(self.menu_page)
        self.stack.addWidget(self.password_page)
        self.stack.addWidget(self.rules_page)

    def build_menu(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(tr("Settings"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(title)
        layout.addSpacing(20)

        password_btn = QPushButton(tr("Change password"))
        password_btn.setFixedSize(260, 45)
        password_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.password_page))

        rules_btn = QPushButton(tr("Attendance rules (salary)"))
        rules_btn.setFixedSize(260, 45)
        rules_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.rules_page))

        layout.addWidget(password_btn, alignment=Qt.AlignCenter)
        layout.addWidget(rules_btn, alignment=Qt.AlignCenter)
        return page

    def show_menu(self):
        self.stack.setCurrentWidget(self.menu_page)

    def done(self, result):
        # Don't close in the middle of sending the email
        self.password_page.wait_for_worker()
        super().done(result)