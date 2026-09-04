from __future__ import annotations
import sys
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication,QComboBox,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMainWindow,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from app.config import settings
from app.ui_worker import ScannerWorker
from app.scanner import load_watchlist

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle("Chart Trading Bot — IBKR Paper");self.resize(1250,850);self.thread=None;self.worker=None;self._build_ui()
    def _build_ui(self):
        root=QWidget();layout=QVBoxLayout(root);top=QGroupBox("Scanner / Risk / Execution Gate");form=QFormLayout(top)
        self.interval=QComboBox();self.interval.addItems(["30","60","120","300"]);self.interval.setCurrentText(str(settings.scan_interval_seconds))
        self.quantity=QLineEdit(str(settings.fixed_quantity));self.tp=QLineEdit(str(settings.take_profit_percent))
        self.info=QLabel(f"Watchlist: {settings.watchlist_file} | symbols={len(load_watchlist(settings.watchlist_file))} | MAX EXECUTED={settings.max_executed_orders}")
        self.status=QLabel("Disconnected");self.connect_btn=QPushButton("Connect & Start");self.stop_btn=QPushButton("Stop");self.stop_btn.setEnabled(False)
        form.addRow("Scan every (sec)",self.interval);form.addRow("Order quantity",self.quantity);form.addRow("Take profit (%)",self.tp);form.addRow("Limits",self.info)
        buttons=QHBoxLayout();buttons.addWidget(self.connect_btn);buttons.addWidget(self.stop_btn);buttons.addWidget(self.status,1);form.addRow(buttons);layout.addWidget(top)
        self.scan_table=QTableWidget(0,7);self.scan_table.setHorizontalHeaderLabels(["Symbol","Signal","Score","Entry","Stop","Target","TP %"]);layout.addWidget(QLabel("Live Scanner Results"));layout.addWidget(self.scan_table)
        gate=QGroupBox("Execution Gate");gf=QFormLayout(gate);self.gate_status=QLabel("WAITING");self.gate_rule=QLabel(f"Fresh Positions + Open Orders + Risk + Max Executed ({settings.max_executed_orders})");self.gate_rule.setWordWrap(True);gf.addRow("Gate",self.gate_status);gf.addRow("Rules",self.gate_rule);layout.addWidget(gate)
        sig=QGroupBox("Latest Analysis");sf=QFormLayout(sig);self.action=QLabel("—");self.score=QLabel("—");self.entry=QLabel("—");self.stop=QLabel("—");self.target=QLabel("—");self.reasons=QLabel("—");self.reasons.setWordWrap(True)
        for n,w in [("Signal",self.action),("Score",self.score),("Entry",self.entry),("Stop",self.stop),("Target",self.target),("Reasons",self.reasons)]:sf.addRow(n,w)
        layout.addWidget(sig);self.orders=QTableWidget(0,9);self.orders.setHorizontalHeaderLabels(["Time","Symbol","Action","Qty","Entry","Stop","Target","Status","Order ID"]);layout.addWidget(QLabel("Orders"));layout.addWidget(self.orders)
        self.connect_btn.clicked.connect(self.start_scanner);self.stop_btn.clicked.connect(self.stop_scanner);self.setCentralWidget(root)
    def start_scanner(self):
        if self.thread and self.thread.isRunning():return
        try:qty=int(self.quantity.text());tp=float(self.tp.text())
        except ValueError:self.status.setText("Error: quantity and TP must be numbers");return
        if qty<=0 or tp<=0:self.status.setText("Error: quantity and TP must be positive");return
        settings.fixed_quantity=qty;settings.take_profit_percent=tp;self.thread=QThread(self);self.worker=ScannerWorker(int(self.interval.currentText()));self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.status.connect(self.on_status);self.worker.scan.connect(self.on_scan);self.worker.order.connect(self.on_order);self.worker.error.connect(self.on_error);self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater);self.thread.finished.connect(self.thread.deleteLater);self.thread.start();self.connect_btn.setEnabled(False);self.stop_btn.setEnabled(True);self.quantity.setEnabled(False);self.tp.setEnabled(False)
    def stop_scanner(self):
        if self.worker:self.worker.stop()
        self.stop_btn.setEnabled(False);self.connect_btn.setEnabled(True);self.quantity.setEnabled(True);self.tp.setEnabled(True)
    def on_status(self,text):
        self.status.setText(text)
        if "ORDER SUBMITTED" in text:self.gate_status.setText("ORDER SUBMITTED")
        elif "kept inside bot" in text:self.gate_status.setText("BLOCKED / QUEUED")
        elif "Portfolio verified" in text:self.gate_status.setText("PORTFOLIO VERIFIED")
    def on_error(self,text):self.status.setText("Error: "+text);self.gate_status.setText("ERROR / FAIL-CLOSED")
    def on_scan(self,data):
        s=data["signal"];symbol=data["symbol"];self.action.setText(s.action);self.score.setText(str(s.score));self.entry.setText(f"{s.entry:.4f}");self.stop.setText(f"{s.stop:.4f}" if s.stop else "—");self.target.setText(f"{s.target:.4f}" if s.target else "—");self.reasons.setText(" • ".join(s.reasons))
        found=next((r for r in range(self.scan_table.rowCount()) if self.scan_table.item(r,0) and self.scan_table.item(r,0).text()==symbol),-1);row=found if found>=0 else self.scan_table.rowCount()
        if found<0:self.scan_table.insertRow(row)
        for c,v in enumerate([symbol,s.action,str(s.score),f"{s.entry:.4f}",f"{s.stop:.4f}" if s.stop else "—",f"{s.target:.4f}" if s.target else "—",f"{settings.take_profit_percent:.2f}%"]):self.scan_table.setItem(row,c,QTableWidgetItem(v))
    def on_order(self,r):
        row=self.orders.rowCount();self.orders.insertRow(row)
        for c,v in enumerate([r.time,r.symbol,r.action,str(r.quantity),f"{r.entry_limit:.4f}",f"{r.stop:.4f}" if r.stop else "—",f"{r.target:.4f}" if r.target else "—",r.status,r.order_id]):self.orders.setItem(row,c,QTableWidgetItem(v))
    def closeEvent(self,event):
        if self.worker:self.worker.stop()
        if self.thread:self.thread.quit();self.thread.wait(3000)
        event.accept()
def run():
    app=QApplication(sys.argv);w=MainWindow();w.show();return app.exec()
if __name__=="__main__":run()
