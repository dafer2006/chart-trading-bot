from __future__ import annotations
import sys
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)
from app.config import settings
from app.ui_worker import ScannerWorker
from app.scanner import load_watchlist


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chart Trading Bot — Top Gainers + TXT Watchlist")
        self.resize(1200, 760)
        self.thread = None
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget(); layout = QVBoxLayout(root)
        top = QGroupBox("Scanner")
        form = QFormLayout(top)
        self.interval = QComboBox(); self.interval.addItems(["30", "60", "120", "300"]); self.interval.setCurrentText(str(settings.scan_interval_seconds))
        self.info = QLabel(f"Top gainers: {settings.top_gainers_count}  |  Custom TXT: {settings.watchlist_file} ({len(load_watchlist(settings.watchlist_file))} symbols)")
        self.status = QLabel("Disconnected")
        self.connect_btn = QPushButton("Connect & Start")
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False)
        form.addRow("Scan every (sec)", self.interval); form.addRow("Sources", self.info)
        buttons = QHBoxLayout(); buttons.addWidget(self.connect_btn); buttons.addWidget(self.stop_btn); buttons.addWidget(self.status, 1)
        form.addRow(buttons); layout.addWidget(top)

        self.scan_table = QTableWidget(0, 6)
        self.scan_table.setHorizontalHeaderLabels(["Symbol", "Signal", "Score", "Entry", "Stop", "Target"])
        self.scan_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(QLabel("Live Scanner Results")); layout.addWidget(self.scan_table)

        signal_box = QGroupBox("Latest Analysis")
        sig = QFormLayout(signal_box)
        self.action = QLabel("—"); self.score = QLabel("—"); self.entry = QLabel("—"); self.stop = QLabel("—"); self.target = QLabel("—")
        self.reasons = QLabel("—"); self.reasons.setWordWrap(True)
        sig.addRow("Signal", self.action); sig.addRow("Score", self.score); sig.addRow("Entry", self.entry); sig.addRow("Stop", self.stop); sig.addRow("Target", self.target); sig.addRow("Reasons", self.reasons)
        layout.addWidget(signal_box)

        self.orders = QTableWidget(0, 8)
        self.orders.setHorizontalHeaderLabels(["Time", "Symbol", "Action", "Qty", "Entry", "Stop", "Target", "Status"])
        self.orders.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(QLabel("Orders submitted to IBKR Paper")); layout.addWidget(self.orders)
        self.connect_btn.clicked.connect(self.start_scanner); self.stop_btn.clicked.connect(self.stop_scanner)
        self.setCentralWidget(root)

    def start_scanner(self):
        if self.thread and self.thread.isRunning(): return
        self.thread = QThread(self); self.worker = ScannerWorker(int(self.interval.currentText()))
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.on_status); self.worker.scan.connect(self.on_scan); self.worker.order.connect(self.on_order); self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start(); self.connect_btn.setEnabled(False); self.stop_btn.setEnabled(True)

    def stop_scanner(self):
        if self.worker: self.worker.stop()
        self.stop_btn.setEnabled(False)

    def on_status(self, text): self.status.setText(text)
    def on_error(self, text): self.status.setText("Error: " + text)

    def on_scan(self, data):
        symbol, s = data["symbol"], data["signal"]
        self.action.setText(s.action); self.score.setText(str(s.score)); self.entry.setText(f"{s.entry:.4f}")
        self.stop.setText(f"{s.stop:.4f}" if s.stop else "—"); self.target.setText(f"{s.target:.4f}" if s.target else "—"); self.reasons.setText(" • ".join(s.reasons))
        found = -1
        for row in range(self.scan_table.rowCount()):
            if self.scan_table.item(row, 0) and self.scan_table.item(row, 0).text() == symbol: found = row; break
        row = found if found >= 0 else self.scan_table.rowCount()
        if found < 0: self.scan_table.insertRow(row)
        vals = [symbol, s.action, str(s.score), f"{s.entry:.4f}", f"{s.stop:.4f}" if s.stop else "—", f"{s.target:.4f}" if s.target else "—"]
        for col, value in enumerate(vals): self.scan_table.setItem(row, col, QTableWidgetItem(value))

    def on_order(self, record):
        row = self.orders.rowCount(); self.orders.insertRow(row)
        vals = [record.time, record.symbol, record.action, str(record.quantity), f"{record.entry:.4f}", f"{record.stop:.4f}" if record.stop else "—", f"{record.target:.4f}" if record.target else "—", record.status]
        for col, value in enumerate(vals): self.orders.setItem(row, col, QTableWidgetItem(value))
        self.status.setText(f"Paper order submitted: {record.action} {record.quantity} {record.symbol}")

    def closeEvent(self, event):
        if self.worker: self.worker.stop()
        if self.thread: self.thread.quit(); self.thread.wait(3000)
        event.accept()


def run():
    app = QApplication(sys.argv); window = MainWindow(); window.show(); return app.exec()

if __name__ == "__main__": run()
