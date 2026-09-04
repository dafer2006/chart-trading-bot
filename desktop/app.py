from __future__ import annotations
import sys
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)
from app.config import settings
from app.ui_worker import ScannerWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chart Trading Bot — IBKR Paper")
        self.resize(980, 650)
        self.thread = None
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget(); layout = QVBoxLayout(root)
        top = QGroupBox("Connection / Scanner")
        form = QFormLayout(top)
        self.symbol = QLineEdit(settings.symbol)
        self.interval = QComboBox(); self.interval.addItems(["30", "60", "120", "300"]); self.interval.setCurrentText("60")
        self.connect_btn = QPushButton("Connect & Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.status = QLabel("Disconnected")
        form.addRow("Symbol", self.symbol)
        form.addRow("Scan every (sec)", self.interval)
        buttons = QHBoxLayout(); buttons.addWidget(self.connect_btn); buttons.addWidget(self.stop_btn); buttons.addWidget(self.status, 1)
        form.addRow(buttons)
        layout.addWidget(top)

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
        self.connect_btn.clicked.connect(self.start_scanner)
        self.stop_btn.clicked.connect(self.stop_scanner)
        self.setCentralWidget(root)

    def start_scanner(self):
        if self.thread and self.thread.isRunning():
            return
        symbol = self.symbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Symbol", "Enter a symbol first."); return
        self.thread = QThread(self)
        self.worker = ScannerWorker(symbol, int(self.interval.currentText()))
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
        self.connect_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.symbol.setEnabled(False)

    def stop_scanner(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)

    def on_status(self, text): self.status.setText(text)
    def on_error(self, text): self.status.setText("Error: " + text)

    def on_scan(self, data):
        s = data["signal"]
        self.action.setText(s.action); self.score.setText(str(s.score)); self.entry.setText(f"{s.entry:.4f}")
        self.stop.setText(f"{s.stop:.4f}" if s.stop else "—"); self.target.setText(f"{s.target:.4f}" if s.target else "—")
        self.reasons.setText(" • ".join(s.reasons))

    def on_order(self, record):
        row = self.orders.rowCount(); self.orders.insertRow(row)
        vals = [record.time, record.symbol, record.action, str(record.quantity), f"{record.entry:.4f}",
                f"{record.stop:.4f}" if record.stop else "—", f"{record.target:.4f}" if record.target else "—", record.status]
        for col, value in enumerate(vals): self.orders.setItem(row, col, QTableWidgetItem(value))
        self.status.setText(f"Paper order submitted: {record.action} {record.quantity} {record.symbol}")

    def closeEvent(self, event):
        if self.worker: self.worker.stop()
        if self.thread: self.thread.quit(); self.thread.wait(3000)
        event.accept()

def run():
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    return app.exec()

if __name__ == "__main__": run()
