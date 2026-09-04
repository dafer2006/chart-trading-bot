from __future__ import annotations

import re
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import settings
from app.scanner import load_watchlist
from app.ui_worker import ScannerWorker


APP_STYLE = """
QMainWindow, QWidget {
    background: #0b1220;
    color: #e5e7eb;
    font-family: Segoe UI;
    font-size: 10pt;
}
QFrame#Sidebar {
    background: #0f172a;
    border-right: 1px solid #1e293b;
}
QFrame#TopBar, QFrame#Panel, QFrame#MetricCard, QFrame#StatusCard {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
}
QFrame#MetricCard { padding: 2px; }
QFrame#StatusCard { border-radius: 8px; }
QLabel#Brand { font-size: 20pt; font-weight: 700; color: #f8fafc; }
QLabel#BrandSub { color: #64748b; font-size: 8pt; }
QLabel#PageTitle { font-size: 17pt; font-weight: 700; color: #f8fafc; }
QLabel#Muted { color: #94a3b8; }
QLabel#MetricValue { font-size: 16pt; font-weight: 700; color: #f8fafc; }
QLabel#MetricTitle { color: #94a3b8; font-size: 8pt; }
QLabel#StatusTitle { color: #94a3b8; font-size: 8pt; }
QLabel#StatusValue { font-weight: 700; color: #e2e8f0; }
QLabel#Positive { color: #34d399; font-weight: 700; }
QLabel#Warning { color: #fbbf24; font-weight: 700; }
QLabel#Danger { color: #fb7185; font-weight: 700; }
QPushButton {
    background: #172033;
    color: #dbeafe;
    border: 1px solid #26344d;
    border-radius: 7px;
    padding: 8px 12px;
}
QPushButton:hover { background: #1e293b; }
QPushButton:disabled { color: #475569; background: #111827; }
QPushButton#Primary { background: #2563eb; border: 1px solid #3b82f6; color: white; font-weight: 700; }
QPushButton#Stop { background: #3f1722; border: 1px solid #7f1d1d; color: #fecaca; font-weight: 700; }
QPushButton#Emergency { background: #450a0a; border: 1px solid #991b1b; color: #fecaca; font-weight: 700; }
QPushButton#Nav {
    text-align: left;
    background: transparent;
    border: 0;
    color: #94a3b8;
    padding: 10px 12px;
}
QPushButton#Nav:hover, QPushButton#Nav:checked { background: #172033; color: #f8fafc; }
QLineEdit, QComboBox {
    background: #0b1220;
    border: 1px solid #26344d;
    border-radius: 6px;
    padding: 7px;
    color: #e5e7eb;
}
QTableWidget {
    background: #0d1524;
    alternate-background-color: #101a2d;
    gridline-color: #1e293b;
    border: 0;
    selection-background-color: #1d4ed8;
    selection-color: white;
}
QHeaderView::section {
    background: #111827;
    color: #94a3b8;
    border: 0;
    border-bottom: 1px solid #1f2937;
    padding: 8px 6px;
    font-weight: 600;
}
QPlainTextEdit {
    background: #080f1b;
    color: #94a3b8;
    border: 0;
    font-family: Consolas;
    font-size: 9pt;
}
QProgressBar {
    background: #0b1220;
    border: 1px solid #26344d;
    border-radius: 5px;
    text-align: center;
    color: #cbd5e1;
}
QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
QSplitter::handle { background: #0b1220; }
"""


def label(text: str, object_name: str = "Muted") -> QLabel:
    w = QLabel(text)
    w.setObjectName(object_name)
    return w


def panel(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setStyleSheet("font-size: 10pt; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(t)
    return frame, layout


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—", subtitle: str = ""):
        super().__init__()
        self.setObjectName("MetricCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        lay.addWidget(label(title, "MetricTitle"))
        self.value = label(value, "MetricValue")
        lay.addWidget(self.value)
        self.subtitle = label(subtitle, "Muted")
        self.subtitle.setStyleSheet("font-size: 8pt; color: #64748b;")
        lay.addWidget(self.subtitle)


class StatusCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("StatusCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        lay.addWidget(label(title, "StatusTitle"))
        self.value = label("OFFLINE", "StatusValue")
        lay.addWidget(self.value)

    def set_state(self, text: str, state: str = "normal"):
        self.value.setText(text)
        if state == "good":
            self.value.setStyleSheet("color:#34d399;font-weight:700;")
        elif state == "warn":
            self.value.setStyleSheet("color:#fbbf24;font-weight:700;")
        elif state == "bad":
            self.value.setStyleSheet("color:#fb7185;font-weight:700;")
        else:
            self.value.setStyleSheet("color:#e2e8f0;font-weight:700;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Trader — IBKR Paper")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.thread = None
        self.worker = None
        self._last_symbol = "—"
        self._build_ui()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_clock)
        self._clock.start(1000)
        self._update_clock()

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 12)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_topbar())
        content_layout.addWidget(self._build_metrics())
        content_layout.addWidget(self._build_dashboard(), 1)
        content_layout.addLayout(self._build_footer())
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(14, 20, 14, 16)
        lay.setSpacing(4)

        brand = label("AI TRADER", "Brand")
        lay.addWidget(brand)
        lay.addWidget(label("AUTOMATED EQUITY DESK", "BrandSub"))
        lay.addSpacing(18)

        self.nav_buttons = []
        for text in ["⌂  Dashboard", "◈  Markets", "★  Watchlist", "▣  Portfolio", "↔  Orders", "⚡  AI Signals", "◉  Risk Control", "⚙  Settings"]:
            b = QPushButton(text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            if not self.nav_buttons:
                b.setChecked(True)
            b.clicked.connect(lambda checked, btn=b: self._select_nav(btn))
            self.nav_buttons.append(b)
            lay.addWidget(b)

        lay.addStretch(1)
        self.sidebar_ibkr = StatusCard("IBKR CONNECTION")
        self.sidebar_tv = StatusCard("TRADINGVIEW")
        lay.addWidget(self.sidebar_ibkr)
        lay.addWidget(self.sidebar_tv)
        lay.addSpacing(8)
        emergency = QPushButton("■  EMERGENCY STOP")
        emergency.setObjectName("Emergency")
        emergency.clicked.connect(self.stop_scanner)
        lay.addWidget(emergency)
        return sidebar

    def _select_nav(self, selected):
        for b in self.nav_buttons:
            b.setChecked(b is selected)

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 10, 14, 10)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.addWidget(label("Trading Dashboard", "PageTitle"))
        self.clock = label("", "Muted")
        title_box.addWidget(self.clock)
        lay.addLayout(title_box)
        lay.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search symbol…")
        self.search.setFixedWidth(180)
        lay.addWidget(self.search)
        self.symbol_combo = QComboBox()
        self.symbol_combo.setMinimumWidth(120)
        self.symbol_combo.addItem(settings.symbol)
        self.symbol_combo.setEditable(True)
        lay.addWidget(self.symbol_combo)
        self.connect_btn = QPushButton("Connect & Start")
        self.connect_btn.setObjectName("Primary")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("Stop")
        self.stop_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self.start_scanner)
        self.stop_btn.clicked.connect(self.stop_scanner)
        lay.addWidget(self.connect_btn)
        lay.addWidget(self.stop_btn)
        return bar

    def _build_metrics(self):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self.ibkr_metric = MetricCard("IBKR", "Disconnected", "Paper trading")
        self.positions_metric = MetricCard("POSITIONS", "—", "Fresh portfolio read")
        self.open_orders_metric = MetricCard("OPEN ORDERS", "—", "Fresh broker snapshot")
        self.executed_metric = MetricCard("EXECUTED", f"0 / {settings.max_executed_orders}", f"Scope: {settings.execution_count_scope}")
        self.gate_metric = MetricCard("EXECUTION GATE", "WAITING", "Fail-closed validation")
        self.signal_metric = MetricCard("LATEST SIGNAL", "—", "AI / chart engine")
        for i, card in enumerate([
            self.ibkr_metric,
            self.positions_metric,
            self.open_orders_metric,
            self.executed_metric,
            self.gate_metric,
            self.signal_metric,
        ]):
            grid.addWidget(card, 0, i)
        return box

    def _build_dashboard(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([930, 360])
        return splitter

    def _build_center(self):
        center = QWidget()
        lay = QVBoxLayout(center)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        chart, chart_lay = panel("MARKET VIEW")
        head = QHBoxLayout()
        self.chart_symbol = label("—", "PageTitle")
        self.chart_price = label("—", "MetricValue")
        head.addWidget(self.chart_symbol)
        head.addWidget(self.chart_price)
        head.addStretch(1)
        self.chart_state = label("Waiting for market data", "Muted")
        head.addWidget(self.chart_state)
        chart_lay.addLayout(head)

        chart_grid = QGridLayout()
        chart_grid.setSpacing(8)
        self.ctx_labels = {}
        fields = [
            ("EMA50", "ema50"),
            ("Williams %R", "williams_r"),
            ("MFI 14", "mfi14"),
            ("Volume Ratio", "volume_ratio"),
            ("Cloud Top", "cloud_top"),
            ("Cloud Bottom", "cloud_bottom"),
        ]
        for i, (title, key) in enumerate(fields):
            f = QFrame()
            f.setObjectName("MetricCard")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(8, 7, 8, 7)
            fl.addWidget(label(title, "MetricTitle"))
            v = label("—", "MetricValue")
            v.setStyleSheet("font-size:11pt;font-weight:700;color:#e2e8f0;")
            fl.addWidget(v)
            self.ctx_labels[key] = v
            chart_grid.addWidget(f, i // 3, i % 3)
        chart_lay.addLayout(chart_grid)
        self.cloud_state = label("Cloud: —", "Muted")
        chart_lay.addWidget(self.cloud_state)
        lay.addWidget(chart)

        controls, controls_lay = panel("SCANNER & RISK")
        form = QFormLayout()
        self.interval = QComboBox()
        self.interval.addItems(["30", "60", "120", "300"])
        self.interval.setCurrentText(str(settings.scan_interval_seconds))
        self.quantity = QLineEdit(str(settings.fixed_quantity))
        self.tp = QLineEdit(str(settings.take_profit_percent))
        form.addRow("Scan interval", self.interval)
        form.addRow("Order quantity", self.quantity)
        form.addRow("Take profit (%)", self.tp)
        self.limit_info = label(
            f"Watchlist: {settings.watchlist_file}   •   Symbols: {len(load_watchlist(settings.watchlist_file))}   •   Max executed: {settings.max_executed_orders}",
            "Muted",
        )
        form.addRow("Limits", self.limit_info)
        controls_lay.addLayout(form)
        lay.addWidget(controls)

        scans, scans_lay = panel("LIVE SCANNER RESULTS")
        self.scan_table = self._make_table(["Symbol", "Signal", "Score", "Entry", "Stop", "Target", "TP %"])
        scans_lay.addWidget(self.scan_table)
        lay.addWidget(scans, 1)
        return center

    def _build_right_panel(self):
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        gate, gate_lay = panel("EXECUTION GATE")
        self.gate_status = label("WAITING", "Warning")
        gate_lay.addWidget(self.gate_status)
        self.gate_progress = QProgressBar()
        self.gate_progress.setRange(0, settings.max_executed_orders)
        self.gate_progress.setValue(0)
        gate_lay.addWidget(self.gate_progress)
        self.gate_rule = label(
            "Fresh Positions + Open Orders + Risk + Max Executed",
            "Muted",
        )
        self.gate_rule.setWordWrap(True)
        gate_lay.addWidget(self.gate_rule)
        lay.addWidget(gate)

        analysis, analysis_lay = panel("LATEST AI ANALYSIS")
        self.analysis_fields = {}
        for name in ["Signal", "Score", "Entry", "Stop", "Target", "Reasons"]:
            row = QHBoxLayout()
            row.addWidget(label(name, "Muted"))
            value = label("—", "StatusValue")
            value.setWordWrap(True)
            row.addWidget(value, 1)
            analysis_lay.addLayout(row)
            self.analysis_fields[name] = value
        lay.addWidget(analysis)

        orders, orders_lay = panel("RECENT ORDERS")
        self.orders = self._make_table(["Time", "Symbol", "Action", "Qty", "Entry", "Stop", "Target", "Status", "ID"])
        self.orders.setMinimumHeight(190)
        orders_lay.addWidget(self.orders)
        lay.addWidget(orders, 1)

        activity, activity_lay = panel("LIVE ACTIVITY")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        activity_lay.addWidget(self.log)
        lay.addWidget(activity, 1)
        return right

    def _build_footer(self):
        footer = QHBoxLayout()
        self.status = label("Disconnected", "Muted")
        footer.addWidget(self.status)
        footer.addStretch(1)
        footer.addWidget(label("PAPER MODE", "Warning"))
        footer.addSpacing(12)
        footer.addWidget(label("MAX 7 ORDERS", "Muted"))
        return footer

    @staticmethod
    def _make_table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        return table

    def _update_clock(self):
        self.clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def _append_log(self, text: str):
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def start_scanner(self):
        if self.thread and self.thread.isRunning():
            return
        try:
            qty = int(self.quantity.text())
            tp = float(self.tp.text())
            interval = int(self.interval.currentText())
        except ValueError:
            self.status.setText("Invalid scanner settings")
            self._append_log("Invalid quantity / TP / interval")
            return
        if qty <= 0 or tp <= 0 or interval <= 0:
            self.status.setText("Scanner values must be positive")
            return

        settings.fixed_quantity = qty
        settings.take_profit_percent = tp
        settings.scan_interval_seconds = interval

        self.thread = QThread(self)
        self.worker = ScannerWorker(interval)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.on_status)
        self.worker.scan.connect(self.on_scan)
        self.worker.order.connect(self.on_order)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

        self.connect_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.quantity.setEnabled(False)
        self.tp.setEnabled(False)
        self.interval.setEnabled(False)
        self.ibkr_metric.value.setText("Connecting…")
        self.sidebar_ibkr.set_state("CONNECTING", "warn")
        self._append_log("Scanner started — IBKR Paper connection requested")

    def stop_scanner(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
        self.quantity.setEnabled(True)
        self.tp.setEnabled(True)
        self.interval.setEnabled(True)
        self._append_log("Scanner stop requested")

    def on_status(self, text: str):
        self.status.setText(text)
        self._append_log(text)

        if "Portfolio verified" in text:
            self.ibkr_metric.value.setText("Connected")
            self.sidebar_ibkr.set_state("CONNECTED", "good")
            m = re.search(r"positions=(\d+).*open orders=(\d+).*executed=(\d+)/(\d+)", text)
            if m:
                positions, open_orders, executed, maximum = map(int, m.groups())
                self.positions_metric.value.setText(str(positions))
                self.open_orders_metric.value.setText(str(open_orders))
                self.executed_metric.value.setText(f"{executed} / {maximum}")
                self.gate_progress.setMaximum(maximum)
                self.gate_progress.setValue(min(executed, maximum))

        if "TradingView queue" in text:
            self.sidebar_tv.set_state("QUEUE ACTIVE", "good")
        elif "ORDER SUBMITTED" in text:
            self.gate_status.setText("ORDER SUBMITTED")
            self.gate_status.setStyleSheet("color:#34d399;font-weight:700;")
            self.gate_metric.value.setText("SUBMITTED")
        elif "kept inside bot" in text:
            self.gate_status.setText("BLOCKED / QUEUED")
            self.gate_status.setStyleSheet("color:#fbbf24;font-weight:700;")
            self.gate_metric.value.setText("BLOCKED")
        elif "Portfolio verified" in text:
            self.gate_status.setText("PORTFOLIO VERIFIED")
            self.gate_status.setStyleSheet("color:#34d399;font-weight:700;")
            self.gate_metric.value.setText("VERIFIED")
        elif "Disconnected" in text:
            self.ibkr_metric.value.setText("Disconnected")
            self.sidebar_ibkr.set_state("OFFLINE", "bad")
            self.gate_status.setText("WAITING")

    def on_error(self, text: str):
        self.status.setText("Error: " + text)
        self.gate_status.setText("ERROR / FAIL-CLOSED")
        self.gate_status.setStyleSheet("color:#fb7185;font-weight:700;")
        self.gate_metric.value.setText("FAIL-CLOSED")
        self._append_log("ERROR: " + text)

    def on_scan(self, data):
        signal = data["signal"]
        symbol = data["symbol"]
        context = data.get("context") or {}
        self._last_symbol = symbol
        self.chart_symbol.setText(symbol)
        self.chart_price.setText(f"{signal.entry:.4f}")
        self.chart_state.setText(f"Signal: {signal.action}  •  Score: {signal.score}")
        self.signal_metric.value.setText(signal.action)
        self.signal_metric.subtitle.setText(f"{symbol} • score {signal.score}")

        self.analysis_fields["Signal"].setText(signal.action)
        self.analysis_fields["Score"].setText(str(signal.score))
        self.analysis_fields["Entry"].setText(f"{signal.entry:.4f}")
        self.analysis_fields["Stop"].setText(f"{signal.stop:.4f}" if signal.stop is not None else "—")
        self.analysis_fields["Target"].setText(f"{signal.target:.4f}" if signal.target is not None else "—")
        self.analysis_fields["Reasons"].setText(" • ".join(signal.reasons) if signal.reasons else "—")

        for key, widget in self.ctx_labels.items():
            value = context.get(key)
            widget.setText("—" if value is None else f"{value:.4f}")
        if context.get("above_cloud"):
            self.cloud_state.setText("Cloud: ABOVE — bullish structure")
            self.cloud_state.setStyleSheet("color:#34d399;font-weight:700;")
        elif context.get("below_cloud"):
            self.cloud_state.setText("Cloud: BELOW — bearish structure")
            self.cloud_state.setStyleSheet("color:#fb7185;font-weight:700;")
        else:
            self.cloud_state.setText("Cloud: neutral / unavailable")
            self.cloud_state.setStyleSheet("color:#94a3b8;")

        found = next(
            (r for r in range(self.scan_table.rowCount())
             if self.scan_table.item(r, 0) and self.scan_table.item(r, 0).text() == symbol),
            -1,
        )
        row = found if found >= 0 else self.scan_table.rowCount()
        if found < 0:
            self.scan_table.insertRow(row)
        values = [
            symbol,
            signal.action,
            str(signal.score),
            f"{signal.entry:.4f}",
            f"{signal.stop:.4f}" if signal.stop is not None else "—",
            f"{signal.target:.4f}" if signal.target is not None else "—",
            f"{settings.take_profit_percent:.2f}%",
        ]
        for c, value in enumerate(values):
            self.scan_table.setItem(row, c, QTableWidgetItem(value))
        self.scan_table.resizeRowsToContents()

    def on_order(self, record):
        row = self.orders.rowCount()
        self.orders.insertRow(row)
        values = [
            record.time,
            record.symbol,
            record.action,
            str(record.quantity),
            f"{record.entry_limit:.4f}",
            f"{record.stop:.4f}" if record.stop is not None else "—",
            f"{record.target:.4f}" if record.target is not None else "—",
            record.status,
            record.order_id,
        ]
        for c, value in enumerate(values):
            self.orders.setItem(row, c, QTableWidgetItem(value))
        self.orders.resizeRowsToContents()
        self._append_log(f"ORDER {record.action} {record.symbol} qty={record.quantity} id={record.order_id}")

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    run()
