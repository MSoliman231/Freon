import sys
import ctypes

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QButtonGroup, QStackedWidget,
    QGraphicsOpacityEffect
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import (
    Qt, Signal, QEasingCurve, QPropertyAnimation, QParallelAnimationGroup,
    QSequentialAnimationGroup
)

import auth
import i18n
import resources
from i18n import tr
from attend import AttendancePage
from settings import EMAIL_PATTERN, ForgotPasswordDialog

# Unlock animation timing (maximum allowed is 2 seconds)
FADE_MS = 900   # lock -> unlock cross-fade
HOLD_MS = 500   # short pause on the open lock before the next page
# Total: 1.4 seconds


class LockIcon(QWidget):
    """Shows lock.png and cross-fades to unlock.png when play() is called."""
    unlocked = Signal()  # emitted when the animation has finished
    SIZE = 72

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)

        self.lock_label = self.make_label("lock.png")
        self.unlock_label = self.make_label("unlock.png")

        self.lock_effect = QGraphicsOpacityEffect(self.lock_label)
        self.unlock_effect = QGraphicsOpacityEffect(self.unlock_label)
        self.lock_label.setGraphicsEffect(self.lock_effect)
        self.unlock_label.setGraphicsEffect(self.unlock_effect)

        fade_out = QPropertyAnimation(self.lock_effect, b"opacity", self)
        fade_out.setDuration(FADE_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InOutCubic)

        fade_in = QPropertyAnimation(self.unlock_effect, b"opacity", self)
        fade_in.setDuration(FADE_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutCubic)

        fade = QParallelAnimationGroup(self)
        fade.addAnimation(fade_out)
        fade.addAnimation(fade_in)

        self.animation = QSequentialAnimationGroup(self)
        self.animation.addAnimation(fade)
        self.animation.addPause(HOLD_MS)
        self.animation.finished.connect(self.unlocked.emit)

        self.reset()

    def make_label(self, name):
        label = QLabel(self)
        label.setGeometry(0, 0, self.SIZE, self.SIZE)
        label.setAlignment(Qt.AlignCenter)
        pixmap = resources.pixmap(name)
        if not pixmap.isNull():
            dpr = self.devicePixelRatioF()
            size = int(self.SIZE * dpr)
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            label.setPixmap(scaled)
        return label

    def reset(self):
        """Back to the locked look."""
        self.animation.stop()
        self.lock_effect.setOpacity(1.0)
        self.unlock_effect.setOpacity(0.0)

    def play(self):
        self.reset()
        self.animation.start()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FREON")
        self.setWindowIcon(resources.icon("icon.png"))
        self.resize(900, 600)
        self.unlocking = False
        self.language_buttons = []  # (language code, button) on every page

        # Pages container
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.setup_page = self.build_setup_page()
        self.home_page = self.build_home_page()
        self.attendance_page = AttendancePage(on_lock=self.lock)

        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.attendance_page)

        # Fresh start: set up the password first
        if auth.is_configured():
            self.stack.setCurrentWidget(self.home_page)
        else:
            self.stack.setCurrentWidget(self.setup_page)

        # Esc leaves full screen, F11 toggles it
        QShortcut(QKeySequence("Esc"), self, activated=self.showMaximized)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    # ---------- Shared: language buttons ----------
    def make_language_row(self):
        """English / Arabic buttons (always English left, Arabic right)."""
        box = QWidget()
        box.setLayoutDirection(Qt.LeftToRight)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        group = QButtonGroup(box)
        for code, label in i18n.LANGUAGES.items():
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(code == i18n.get_language())
            button.setFixedSize(110, 34)
            button.setStyleSheet(
                "QPushButton:checked { background-color: #1976d2; "
                "color: white; font-weight: bold; }"
            )
            button.clicked.connect(lambda checked=False, c=code: self.change_language(c))
            group.addButton(button)
            row.addWidget(button)
            self.language_buttons.append((code, button))
        return box

    # ---------- Setup page (first start) ----------
    def build_setup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("FREON")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: bold;")

        self.setup_heading = QLabel(tr("Set up your password"))
        self.setup_heading.setAlignment(Qt.AlignCenter)
        self.setup_heading.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.setup_info = QLabel(tr("Enter your email and choose a password for the app."))
        self.setup_info.setAlignment(Qt.AlignCenter)
        self.setup_info.setWordWrap(True)
        self.setup_info.setFixedWidth(320)

        self.setup_email = QLineEdit()
        self.setup_email.setPlaceholderText("name@example.com")
        self.setup_email.setLayoutDirection(Qt.LeftToRight)  # emails are always left-to-right
        self.setup_email.setAlignment(Qt.AlignCenter)
        self.setup_email.setFixedSize(320, 40)

        self.setup_password = QLineEdit()
        self.setup_password.setEchoMode(QLineEdit.Password)
        self.setup_password.setPlaceholderText(tr("New password"))
        self.setup_password.setAlignment(Qt.AlignCenter)
        self.setup_password.setFixedSize(320, 40)

        self.setup_confirm = QLineEdit()
        self.setup_confirm.setEchoMode(QLineEdit.Password)
        self.setup_confirm.setPlaceholderText(tr("Confirm password"))
        self.setup_confirm.setAlignment(Qt.AlignCenter)
        self.setup_confirm.setFixedSize(320, 40)

        # Enter moves to the next field, and saves on the last one
        self.setup_email.returnPressed.connect(self.setup_password.setFocus)
        self.setup_password.returnPressed.connect(self.setup_confirm.setFocus)
        self.setup_confirm.returnPressed.connect(self.save_setup)

        self.setup_show = QCheckBox(tr("Show password"))
        self.setup_show.toggled.connect(self.toggle_setup_visibility)

        self.setup_button = QPushButton(tr("Save and continue"))
        self.setup_button.setFixedSize(320, 42)
        self.setup_button.clicked.connect(self.save_setup)

        self.setup_error = QLabel("")
        self.setup_error.setAlignment(Qt.AlignCenter)
        self.setup_error.setWordWrap(True)
        self.setup_error.setFixedWidth(320)
        self.setup_error.setStyleSheet("color: red;")

        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(self.setup_heading)
        layout.addWidget(self.setup_info, alignment=Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.setup_email, alignment=Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.setup_password, alignment=Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.setup_confirm, alignment=Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.setup_show, alignment=Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.setup_button, alignment=Qt.AlignCenter)
        layout.addWidget(self.setup_error, alignment=Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.make_language_row(), alignment=Qt.AlignCenter)
        return page

    def toggle_setup_visibility(self, checked):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.setup_password.setEchoMode(mode)
        self.setup_confirm.setEchoMode(mode)

    def save_setup(self):
        email = self.setup_email.text().strip()
        password = self.setup_password.text()
        confirm = self.setup_confirm.text()

        if not EMAIL_PATTERN.match(email):
            self.setup_error.setText(tr("Please enter a valid email address."))
            return
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            self.setup_error.setText(
                tr("The password must be at least {count} characters.",
                   count=auth.MIN_PASSWORD_LENGTH)
            )
            return
        if password != confirm:
            self.setup_error.setText(tr("The passwords do not match."))
            return

        try:
            auth.setup(email, password)
        except OSError as e:
            self.setup_error.setText(tr("Could not save the password ({error}).", error=e))
            return

        for field in (self.setup_email, self.setup_password, self.setup_confirm):
            field.clear()
        self.setup_show.setChecked(False)
        self.setup_error.setText("")
        self.stack.setCurrentWidget(self.home_page)
        self.password_input.setFocus()

    # ---------- Lock screen ----------
    def build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        # Lock icon beside the FREON title
        title_box = QWidget()
        title_row = QHBoxLayout(title_box)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(14)

        self.lock_icon = LockIcon()
        self.lock_icon.unlocked.connect(self.finish_unlock)

        title = QLabel("FREON")
        title.setStyleSheet("font-size: 36px; font-weight: bold;")

        title_row.addWidget(self.lock_icon)
        title_row.addWidget(title)

        self.prompt_label = QLabel(tr("Type your password"))
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setStyleSheet("font-size: 14px;")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setAlignment(Qt.AlignCenter)
        self.password_input.setFixedSize(250, 40)
        self.password_input.returnPressed.connect(self.check_password)

        self.show_password = QCheckBox(tr("Show password"))
        self.show_password.toggled.connect(self.toggle_password_visibility)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: red;")

        # "Forgot password?" link-style button
        self.forgot_button = QPushButton(tr("Forgot password?"))
        self.forgot_button.setFlat(True)
        self.forgot_button.setCursor(Qt.PointingHandCursor)
        self.forgot_button.setStyleSheet(
            "QPushButton { border: none; color: #4da3ff; "
            "text-decoration: underline; padding: 4px; }"
            "QPushButton:hover { color: #80bfff; }"
        )
        self.forgot_button.clicked.connect(self.open_forgot_password)

        layout.addWidget(title_box, alignment=Qt.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(self.prompt_label)
        layout.addSpacing(6)
        layout.addWidget(self.password_input, alignment=Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.show_password, alignment=Qt.AlignCenter)
        layout.addWidget(self.error_label)
        layout.addWidget(self.forgot_button, alignment=Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.make_language_row(), alignment=Qt.AlignCenter)
        return page

    def open_forgot_password(self):
        if self.unlocking:
            return
        self.forgot_dialog = ForgotPasswordDialog(self)
        self.forgot_dialog.exec()
        self.password_input.setFocus()

    # ---------- Language ----------
    def change_language(self, code):
        if code == i18n.get_language() or self.unlocking:
            return
        i18n.set_language(code)
        QApplication.setLayoutDirection(i18n.direction())

        # Keep the buttons on every page in sync
        for lang_code, button in self.language_buttons:
            button.setChecked(lang_code == code)

        # Lock screen texts
        self.prompt_label.setText(tr("Type your password"))
        self.show_password.setText(tr("Show password"))
        self.forgot_button.setText(tr("Forgot password?"))
        self.error_label.setText("")
        self.password_input.clear()

        # Setup screen texts
        self.setup_heading.setText(tr("Set up your password"))
        self.setup_info.setText(tr("Enter your email and choose a password for the app."))
        self.setup_password.setPlaceholderText(tr("New password"))
        self.setup_confirm.setPlaceholderText(tr("Confirm password"))
        self.setup_show.setText(tr("Show password"))
        self.setup_button.setText(tr("Save and continue"))
        self.setup_error.setText("")

        # Rebuild the attendance page in the new language (data is auto-saved,
        # so it is simply loaded again)
        old_page = self.attendance_page
        self.stack.removeWidget(old_page)
        old_page.deleteLater()
        self.attendance_page = AttendancePage(on_lock=self.lock)
        self.stack.addWidget(self.attendance_page)

    # ---------- Password ----------
    def toggle_password_visibility(self, checked):
        self.password_input.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def set_inputs_enabled(self, enabled):
        self.password_input.setEnabled(enabled)
        self.show_password.setEnabled(enabled)
        self.forgot_button.setEnabled(enabled)
        for _, button in self.language_buttons:
            button.setEnabled(enabled)

    def check_password(self):
        if self.unlocking:
            return
        if auth.verify_password(self.password_input.text()):
            self.unlocking = True
            self.error_label.setText("")
            self.password_input.clear()
            self.show_password.setChecked(False)
            self.set_inputs_enabled(False)
            self.lock_icon.play()  # next page opens when it finishes
        else:
            self.error_label.setText(tr("Wrong password"))
            self.password_input.clear()

    def finish_unlock(self):
        self.unlocking = False
        self.set_inputs_enabled(True)
        self.stack.setCurrentWidget(self.attendance_page)

    def lock(self):
        self.lock_icon.reset()
        self.password_input.clear()
        self.show_password.setChecked(False)
        self.error_label.setText("")
        self.stack.setCurrentWidget(self.home_page)
        self.password_input.setFocus()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()


if __name__ == "__main__":
    # Makes Windows show your icon in the taskbar instead of the Python icon
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("freon.app")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setWindowIcon(resources.icon("icon.png"))
    app.setLayoutDirection(i18n.direction())
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())