import calendar
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QPushButton,
    QWidget, QFileDialog, QMessageBox
)
from PySide6.QtGui import (
    QImage, QPainter, QPixmap, QFont, QFontMetrics, QColor, QPen, QPageSize
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

import i18n
import payroll
import resources
from i18n import tr

# A4 page in tenths of a millimetre (210 mm x 297 mm)
PAGE_W, PAGE_H = 2100, 2970
MARGIN_X = 40        # 4 mm on the left and right: the card uses the full width
MARGIN_TOP = 60
MARGIN_BOTTOM = 100
GAP = 30
CARDS_PER_PAGE = 4   # maximum names on one A4 page
CARD_W = PAGE_W - 2 * MARGIN_X
CARD_H = (PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - GAP * (CARDS_PER_PAGE - 1)) // CARDS_PER_PAGE

# Text sizes (tenths of a millimetre)
BODY_SIZE = 38
ROW_H = 66
STEP = 88

COUNTED_STATES = ("Present", "Late-1", "Late-2", "Absent")


def money(value):
    return f"{float(value):,.2f}"


def ltr(text):
    """Keeps numbers such as 2026-11-12  14:30 in reading order inside Arabic text."""
    return "\u202a" + text + "\u202c"


def warn(parent, title, text):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setWindowIcon(resources.icon("export.png"))
    box.setIcon(QMessageBox.Warning)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Ok)
    box.button(QMessageBox.Ok).setText(tr("OK"))
    box.exec()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def build_slip(name, year, month, records, notes, rules, printed_at):
    """Collects everything shown on one name's card."""
    days_in_month = calendar.monthrange(year, month)[1]

    marks = records.get((year, month, name), {})
    counts = {state: 0 for state in COUNTED_STATES}
    for day, state in marks.items():
        if 1 <= day <= days_in_month and state in counts:
            counts[state] += 1

    discounts = []  # (state, how many times, value each, total)
    for state in payroll.RULE_STATES:
        rate = rules["deductions"].get(state, 0.0)
        discounts.append((state, counts[state], rate, counts[state] * rate))

    borrowed = sum(notes.get((year, month, name), {}).values())
    total_discount = sum(d[3] for d in discounts) + borrowed

    # Only the days that were registered (present, late or absent) are paid.
    # Days that were never marked do not count.
    counted_days = sum(counts.values())

    salary = rules["salaries"].get(name)  # None = not set yet
    prorated = None
    after = None
    if salary is not None:
        prorated = round(salary * counted_days / days_in_month, 2)
        after = round(prorated - total_discount, 2)

    return {
        "name": name,
        "year": year,
        "month": month,
        "printed_at": printed_at,
        "days_in_month": days_in_month,
        "counts": counts,
        "late_days": counts["Late-1"] + counts["Late-2"],
        "not_marked": days_in_month - counted_days,
        "counted_days": counted_days,
        "discounts": discounts,
        "borrowed": borrowed,
        "total_discount": total_discount,
        "salary_before": salary,
        "salary_prorated": prorated,
        "salary_after": after,
    }


# ---------------------------------------------------------------------------
# Drawing (the same code is used for the preview, the printer, PDF and PNG)
# ---------------------------------------------------------------------------
def make_font(size, bold=False):
    font = QFont()
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def text_width(text, size, bold=False):
    return QFontMetrics(make_font(size, bold)).horizontalAdvance(text)


def put(painter, rect, text, side, rtl):
    """Draws text against the 'left' or 'right' edge of rect.
    rtl sets the reading direction of the text (True for Arabic)."""
    flags = Qt.AlignVCenter | Qt.AlignAbsolute
    flags |= Qt.AlignLeft if side == "left" else Qt.AlignRight
    painter.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
    painter.drawText(rect, flags, text)


def draw_row(painter, x, y, w, label, value, rtl, bold=False, color="#212121"):
    start = "right" if rtl else "left"
    end = "left" if rtl else "right"

    size = BODY_SIZE
    # Shrinks a little only when a very long label + value would not fit
    while size > 22 and text_width(label, size, bold) + text_width(value, size, bold) + 30 > w:
        size -= 2
    painter.setFont(make_font(size, bold))
    painter.setPen(QColor(color))
    rect = QRectF(x, y, w, ROW_H)
    put(painter, rect, label, start, rtl)
    put(painter, rect, value, end, False)  # numbers always read left-to-right


def column_positions(x, inner_w, widths, gap, rtl):
    """Left edge of each column. In Arabic the first column is on the right."""
    if not rtl:
        xs = [x]
        for w in widths[:-1]:
            xs.append(xs[-1] + w + gap)
        return xs
    xs = []
    right = x + inner_w
    for w in widths:
        xs.append(right - w)
        right -= w + gap
    return xs


def draw_card(painter, rect, s, rtl):
    painter.save()
    pad = 40
    start = "right" if rtl else "left"
    end = "left" if rtl else "right"

    # Paper-like card
    painter.setPen(QPen(QColor("#9e9e9e"), 3))
    painter.setBrush(QColor("#fcfcfc"))
    painter.drawRoundedRect(rect, 25, 25)

    x = rect.x() + pad
    top = rect.y()
    inner_w = rect.width() - 2 * pad

    # ----- Header: name, month and date/time -----
    name_w = inner_w * 0.55
    if rtl:
        name_rect = QRectF(x + inner_w - name_w, top + 15, name_w, 100)
        info_rect = QRectF(x, top + 15, inner_w - name_w, 100)
    else:
        name_rect = QRectF(x, top + 15, name_w, 100)
        info_rect = QRectF(x + name_w, top + 15, inner_w - name_w, 100)

    name_font = make_font(60, True)
    name = QFontMetrics(name_font).elidedText(s["name"], Qt.ElideRight, int(name_w))
    painter.setFont(name_font)
    painter.setPen(QColor("#111111"))
    put(painter, name_rect, name, start, rtl)

    painter.setFont(make_font(30))
    painter.setPen(QColor("#444444"))
    printed = s["printed_at"].strftime("%Y-%m-%d  %H:%M")
    info = (
        f"{tr('Month:')} {i18n.month_name(s['month'])} {s['year']}\n"
        f"{tr('Printed:')} {ltr(printed)}"
    )
    put(painter, info_rect, info, end, rtl)

    painter.setPen(QPen(QColor("#bdbdbd"), 2))
    painter.drawLine(QPointF(x, top + 125), QPointF(x + inner_w, top + 125))

    # ----- Three columns -----
    col_gap = 40
    usable = inner_w - 2 * col_gap
    widths = [usable * 0.23, usable * 0.41, usable * 0.36]
    xs = column_positions(x, inner_w, widths, col_gap, rtl)
    title_y = top + 138
    row_y = top + 205

    # Vertical lines between the three columns
    painter.setPen(QPen(QColor("#bdbdbd"), 2))
    ordered = sorted(zip(xs, widths))  # left to right
    for (left_x, left_w), _ in zip(ordered, ordered[1:]):
        line_x = left_x + left_w + col_gap / 2
        painter.drawLine(QPointF(line_x, top + 145), QPointF(line_x, rect.bottom() - 30))

    painter.setFont(make_font(38, True))
    painter.setPen(QColor("#1565c0"))
    titles = (tr("Attendance"), tr("Discounts"), tr("Salary"))
    for cx, cw, title in zip(xs, widths, titles):
        put(painter, QRectF(cx, title_y, cw, 56), title, start, rtl)

    # Column 1: attendance
    counts = s["counts"]
    attendance_rows = [
        (tr("Days in month"), str(s["days_in_month"])),
        (tr("Present"), str(counts["Present"])),
        (tr("Late days"), str(s["late_days"])),
        (tr("Absent"), str(counts["Absent"])),
        (tr("Not marked"), str(s["not_marked"])),
    ]
    for i, (label, value) in enumerate(attendance_rows):
        draw_row(painter, xs[0], row_y + i * STEP, widths[0], label, value, rtl)

    # Column 2: discounts (Late-1: 3 x 10.00 = 30.00 ...)
    for i, (state, count, rate, amount) in enumerate(s["discounts"]):
        draw_row(painter, xs[1], row_y + i * STEP, widths[1], tr(state),
                 f"{count} × {money(rate)} = {money(amount)}", rtl)
    borrowed_y = row_y + len(s["discounts"]) * STEP
    draw_row(painter, xs[1], borrowed_y, widths[1], tr("Borrowed"),
             money(s["borrowed"]), rtl)

    total_y = borrowed_y + STEP
    painter.setPen(QPen(QColor("#bdbdbd"), 2))
    painter.drawLine(QPointF(xs[1], total_y), QPointF(xs[1] + widths[1], total_y))
    draw_row(painter, xs[1], total_y + 6, widths[1], tr("Total discount"),
             money(s["total_discount"]), rtl, bold=True)

    # Column 3: monthly salary / salary for the counted days / discount / after
    before = s["salary_before"]
    prorated = s["salary_prorated"]
    after = s["salary_after"]
    not_set = tr("Not set")

    draw_row(painter, xs[2], row_y, widths[2], tr("Monthly salary"),
             not_set if before is None else money(before), rtl)
    draw_row(painter, xs[2], row_y + STEP, widths[2],
             tr("Salary for {days}/{total} days",
                days=s["counted_days"], total=s["days_in_month"]),
             not_set if prorated is None else money(prorated), rtl)
    draw_row(painter, xs[2], row_y + 2 * STEP, widths[2], tr("Discount"),
             "- " + money(s["total_discount"]), rtl)

    positive = after is None or after >= 0
    box = QRectF(xs[2] - 10, row_y + 3 * STEP + 14, widths[2] + 20, 150)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#e8f5e9" if positive else "#ffebee"))
    painter.drawRoundedRect(box, 15, 15)

    painter.setPen(QColor("#2e7d32" if positive else "#c62828"))
    painter.setFont(make_font(32, True))
    put(painter, QRectF(box.x() + 15, box.y() + 8, box.width() - 30, 45),
        tr("Salary after"), start, rtl)

    value = "—" if after is None else money(after)
    size = 60
    while size > 30 and text_width(value, size, True) > box.width() - 30:
        size -= 4
    painter.setFont(make_font(size, True))
    put(painter, QRectF(box.x() + 15, box.y() + 52, box.width() - 30, 92),
        value, end, False)

    painter.restore()


def draw_page(painter, target, slips, page_no, page_count):
    """Draws one A4 page, fitted and centred inside the target rectangle."""
    rtl = i18n.is_rtl()
    scale = min(target.width() / PAGE_W, target.height() / PAGE_H)
    painter.save()
    painter.translate(
        target.x() + (target.width() - PAGE_W * scale) / 2,
        target.y() + (target.height() - PAGE_H * scale) / 2,
    )
    painter.scale(scale, scale)

    for i, s in enumerate(slips):
        top = MARGIN_TOP + i * (CARD_H + GAP)
        draw_card(painter, QRectF(MARGIN_X, top, CARD_W, CARD_H), s, rtl)

    painter.setPen(QColor("#777777"))
    painter.setFont(make_font(26))
    footer = f"FREON  -  {tr('Page')} {ltr(f'{page_no} / {page_count}')}"
    put(painter, QRectF(MARGIN_X, PAGE_H - MARGIN_BOTTOM + 25, CARD_W, 50),
        footer, "left" if rtl else "right", rtl)
    painter.restore()


# ---------------------------------------------------------------------------
# Preview window
# ---------------------------------------------------------------------------
class PayslipPreviewDialog(QDialog):
    def __init__(self, slips, parent=None):
        super().__init__(parent)
        self.year = slips[0]["year"]
        self.month = slips[0]["month"]
        self.pages = [
            slips[i:i + CARDS_PER_PAGE]
            for i in range(0, len(slips), CARDS_PER_PAGE)
        ]

        self.setWindowTitle(f"{tr('Export')} - {i18n.month_name(self.month)} {self.year}")
        self.setWindowIcon(resources.icon("export.png"))
        self.resize(780, 900)

        layout = QVBoxLayout(self)

        info = QLabel(tr("{count} name(s) on {pages} A4 page(s)",
                         count=len(slips), pages=len(self.pages)))
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        # Scrollable list of A4 pages
        holder = QWidget()
        holder.setObjectName("pages")
        holder.setStyleSheet("#pages { background: #cfcfcf; }")
        pages_layout = QVBoxLayout(holder)
        pages_layout.setSpacing(20)
        for index in range(len(self.pages)):
            image = self.render_image(index, 1240, 1754)  # 150 dpi
            pixmap = QPixmap.fromImage(image).scaledToWidth(680, Qt.SmoothTransformation)
            label = QLabel()
            label.setPixmap(pixmap)
            label.setFixedSize(pixmap.size())
            pages_layout.addWidget(label, alignment=Qt.AlignHCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        layout.addWidget(scroll)

        # Buttons
        bar = QHBoxLayout()
        save_image_button = QPushButton(tr("Save image"))
        save_pdf_button = QPushButton(tr("Save PDF"))
        print_button = QPushButton(tr("Print"))
        close_button = QPushButton(tr("Close"))
        for button in (save_image_button, save_pdf_button, print_button, close_button):
            button.setFixedWidth(120)
        save_image_button.clicked.connect(self.save_images)
        save_pdf_button.clicked.connect(self.save_pdf)
        print_button.clicked.connect(self.print_pages)
        close_button.clicked.connect(self.accept)

        bar.addWidget(save_image_button)
        bar.addWidget(save_pdf_button)
        bar.addStretch()
        bar.addWidget(print_button)
        bar.addWidget(close_button)
        layout.addLayout(bar)

    def render_image(self, index, width, height):
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(Qt.white)
        # Tells other programs this is a real A4 sheet (width / 210 mm)
        dots_per_meter = int(width / 0.210)
        image.setDotsPerMeterX(dots_per_meter)
        image.setDotsPerMeterY(dots_per_meter)

        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        draw_page(painter, QRectF(0, 0, width, height),
                  self.pages[index], index + 1, len(self.pages))
        painter.end()
        return image

    def paint_to_printer(self, printer):
        painter = QPainter()
        if not painter.begin(printer):
            warn(self, tr("Print"), tr("Could not start printing."))
            return
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        area = printer.pageLayout().paintRectPixels(printer.resolution())
        target = QRectF(0, 0, area.width(), area.height())
        for index, page in enumerate(self.pages):
            if index > 0:
                printer.newPage()
            draw_page(painter, target, page, index + 1, len(self.pages))
        painter.end()

    def print_pages(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.Accepted:
            self.paint_to_printer(printer)

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save PDF"), f"FREON-{self.year}-{self.month:02d}.pdf",
            "PDF (*.pdf)"
        )
        if not path:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setOutputFileName(path)
        self.paint_to_printer(printer)

    def save_images(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save image"), f"FREON-{self.year}-{self.month:02d}.png",
            "PNG (*.png)"
        )
        if not path:
            return
        base = Path(path)
        for index in range(len(self.pages)):
            image = self.render_image(index, 2480, 3508)  # 300 dpi A4
            if len(self.pages) == 1:
                target = base
            else:
                target = base.with_name(f"{base.stem}-page{index + 1}{base.suffix}")
            if not image.save(str(target)):
                warn(self, tr("Save image"), tr("Could not save {path}", path=target))
                return