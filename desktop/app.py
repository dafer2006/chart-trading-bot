from __future__ import annotations

import sys
from datetime import datetime
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from app.config import settings
from app.scanner import load_watchlist
from app.ui_worker import ScannerWorker

STYLE = '''
QMainWindow,QWidget{background:#080f1c;color:#e5e7eb;font-family:Segoe UI;font-size:10pt}
QFrame#Side{background:#0b1424;border-right:1px solid #1c2a40} QFrame#Panel,QFrame#Top,QFrame#Metric,QFrame#Status{background:#0e192b;border:1px solid #1c2b43;border-radius:10px}
QLabel#Brand{font-size:20pt;font-weight:800;color:#f8fafc} QLabel#Sub{color:#64748b;font-size:8pt} QLabel#Title{font-size:17pt;font-weight:800;color:#f8fafc}
QLabel#MT{color:#7f91aa;font-size:8pt;font-weight:700} QLabel#MV{font-size:15pt;font-weight:800;color:#f8fafc} QLabel#Muted{color:#94a3b8} QLabel#Warn{color:#fbbf24;font-weight:800} QLabel#Good{color:#34d399;font-weight:800} QLabel#Bad{color:#fb7185;font-weight:800}
QPushButton{background:#152238;color:#dbeafe;border:1px solid #293a57;border-radius:7px;padding:8px 12px} QPushButton:hover{background:#1d2d47} QPushButton#Primary{background:#2563eb;color:white;font-weight:800} QPushButton#Stop{background:#431827;color:#fecaca;font-weight:800} QPushButton#Emergency{background:#450a0a;color:#fecaca;font-weight:800}
QPushButton#Nav{text-align:left;background:transparent;border:0;color:#94a3b8;padding:10px 12px} QPushButton#Nav:hover,QPushButton#Nav:checked{background:#172238;color:#f8fafc}
QLineEdit,QComboBox{background:#0a1322;border:1px solid #293a57;border-radius:6px;padding:7px;color:#e5e7eb} QTableWidget{background:#0a1424;alternate-background-color:#0e1a2d;gridline-color:#1d2a40;border:0;selection-background-color:#1d4ed8} QHeaderView::section{background:#0e192b;color:#8fa1ba;border:0;padding:8px;font-weight:700} QPlainTextEdit{background:#070d17;color:#94a3b8;border:0;font-family:Consolas;font-size:9pt} QProgressBar{background:#0a1322;border:1px solid #293a57;border-radius:5px;text-align:center;color:#cbd5e1} QProgressBar::chunk{background:#2563eb;border-radius:4px}
'''

def lab(text,name='Muted'):
    x=QLabel(str(text)); x.setObjectName(name); return x

def make_panel(title):
    f=QFrame(); f.setObjectName('Panel'); l=QVBoxLayout(f); l.setContentsMargins(14,12,14,12); l.setSpacing(8); l.addWidget(lab(title,'Title')); return f,l

class Metric(QFrame):
    def __init__(self,title,value='—',sub=''):
        super().__init__(); self.setObjectName('Metric'); l=QVBoxLayout(self); l.setContentsMargins(12,9,12,9); l.setSpacing(2); l.addWidget(lab(title,'MT')); self.value=lab(value,'MV'); l.addWidget(self.value); self.sub=lab(sub,'Muted'); l.addWidget(self.sub)

class Chart(QWidget):
    def __init__(self): super().__init__(); self.data=[]; self.setMinimumHeight(230)
    def set_data(self,data): self.data=list(data or []); self.update()
    def paintEvent(self,e):
        p=QPainter(self); r=self.rect().adjusted(12,10,-12,-10); p.setPen(QPen('#1b2a40',1))
        for i in range(1,5): p.drawLine(r.left(),int(r.top()+r.height()*i/5),r.right(),int(r.top()+r.height()*i/5))
        if len(self.data)<2: p.setPen(QPen('#64748b')); p.drawText(r,Qt.AlignCenter,'Waiting for historical market data'); return
        lo,hi=min(self.data),max(self.data); span=hi-lo or 1; pts=[]
        for i,v in enumerate(self.data): pts.append((int(r.left()+r.width()*i/(len(self.data)-1)),int(r.bottom()-r.height()*.8*(v-lo)/span)))
        p.setPen(QPen('#60a5fa',2));
        for a,b in zip(pts,pts[1:]): p.drawLine(a[0],a[1],b[0],b[1])
        p.setPen(QPen('#94a3b8')); p.drawText(r.left(),r.top()+14,f'HIGH {hi:.4f}'); p.drawText(r.left(),r.bottom(),f'LOW {lo:.4f}'); p.drawText(r.right()-120,r.top()+14,f'LAST {self.data[-1]:.4f}')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('AI Trader — IBKR Paper'); self.resize(1440,900); self.setMinimumSize(1180,760); self.thread=None; self.worker=None; self.build(); self.timer=QTimer(self); self.timer.timeout.connect(self.clock); self.timer.start(1000); self.clock()
    def build(self):
        root=QWidget(); rl=QHBoxLayout(root); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0); rl.addWidget(self.sidebar())
        c=QWidget(); l=QVBoxLayout(c); l.setContentsMargins(16,14,16,12); l.setSpacing(10); l.addWidget(self.top()); l.addWidget(self.metrics())
        self.pages=QStackedWidget(); self.pages.addWidget(self.dashboard()); self.pages.addWidget(self.portfolio_page()); self.pages.addWidget(self.orders_page()); self.pages.addWidget(self.ai_page()); self.pages.addWidget(self.risk_page()); self.pages.addWidget(self.settings_page()); l.addWidget(self.pages,1); l.addLayout(self.footer()); rl.addWidget(c,1); self.setCentralWidget(root)
    def sidebar(self):
        s=QFrame(); s.setObjectName('Side'); s.setFixedWidth(190); l=QVBoxLayout(s); l.setContentsMargins(14,20,14,16); l.setSpacing(4); l.addWidget(lab('AI TRADER','Brand')); l.addWidget(lab('AUTOMATED EQUITY DESK','Sub')); l.addSpacing(18); self.nav=[]; names=['Dashboard','Markets','Watchlist','Portfolio','Orders','AI Signals','Risk Control','Settings']; mp={0:0,1:0,2:0,3:1,4:2,5:3,6:4,7:5}
        for i,n in enumerate(names):
            b=QPushButton(n); b.setObjectName('Nav'); b.setCheckable(True); b.setChecked(i==0); b.clicked.connect(lambda _,x=b,j=i:self.nav_click(x,j)); self.nav.append(b); l.addWidget(b)
        l.addStretch(1); self.side_ibkr=lab('IBKR  OFFLINE','Bad'); self.side_tv=lab('TRADINGVIEW  OFFLINE','Muted'); l.addWidget(self.side_ibkr); l.addWidget(self.side_tv); l.addSpacing(8); e=QPushButton('■  EMERGENCY STOP'); e.setObjectName('Emergency'); e.clicked.connect(self.stop); l.addWidget(e); return s
    def nav_click(self,b,i):
        for x in self.nav: x.setChecked(x is b)
        self.pages.setCurrentIndex({0:0,1:0,2:0,3:1,4:2,5:3,6:4,7:5}[i]); self.page_title.setText(b.text())
    def top(self):
        f=QFrame(); f.setObjectName('Top'); l=QHBoxLayout(f); box=QVBoxLayout(); self.page_title=lab('Dashboard','Title'); box.addWidget(self.page_title); self.clock_label=lab('','Muted'); box.addWidget(self.clock_label); l.addLayout(box); l.addStretch(1); self.search=QLineEdit(); self.search.setPlaceholderText('Search symbol…'); self.search.setFixedWidth(180); l.addWidget(self.search); self.symbol=QComboBox(); self.symbol.setEditable(True); self.symbol.addItem(settings.symbol); l.addWidget(self.symbol); self.connect=QPushButton('Connect & Start'); self.connect.setObjectName('Primary'); self.stop_btn=QPushButton('Stop'); self.stop_btn.setObjectName('Stop'); self.stop_btn.setEnabled(False); self.connect.clicked.connect(self.start); self.stop_btn.clicked.connect(self.stop); l.addWidget(self.connect); l.addWidget(self.stop_btn); return f
    def metrics(self):
        w=QWidget(); g=QGridLayout(w); g.setContentsMargins(0,0,0,0); g.setSpacing(9); self.m_ibkr=Metric('IBKR','DISCONNECTED','No live broker data'); self.m_pos=Metric('POSITIONS','—','Broker snapshot'); self.m_open=Metric('OPEN ORDERS','—','Broker snapshot'); self.m_exec=Metric('EXECUTED',f'0 / {settings.max_executed_orders}',f'Scope: {settings.execution_count_scope}'); self.m_gate=Metric('EXECUTION GATE','WAITING','Fail-closed'); self.m_sig=Metric('LATEST SIGNAL','—','AI / chart engine')
        for i,x in enumerate([self.m_ibkr,self.m_pos,self.m_open,self.m_exec,self.m_gate,self.m_sig]): g.addWidget(x,0,i)
        return w
    def dashboard(self):
        sp=QSplitter(Qt.Horizontal); sp.addWidget(self.center()); sp.addWidget(self.right()); sp.setSizes([930,370]); return sp
    def center(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(10); p,pl=make_panel('MARKET VIEW'); h=QHBoxLayout(); self.chart_symbol=lab('—','Title'); self.chart_price=lab('—','MV'); h.addWidget(self.chart_symbol); h.addWidget(self.chart_price); h.addStretch(1); self.chart_state=lab('Waiting for market data','Muted'); h.addWidget(self.chart_state); pl.addLayout(h); self.chart=Chart(); pl.addWidget(self.chart); grid=QGridLayout(); self.ctx={}
        for i,(t,k) in enumerate([('EMA50','ema50'),('Williams %R','williams_r'),('MFI 14','mfi14'),('Volume Ratio','volume_ratio'),('Cloud Top','cloud_top'),('Cloud Bottom','cloud_bottom')]): x=Metric(t); self.ctx[k]=x.value; grid.addWidget(x,i//3,i%3)
        pl.addLayout(grid); self.cloud=lab('Cloud: —','Muted'); pl.addWidget(self.cloud); l.addWidget(p); q,ql=make_panel('SCANNER & RISK'); form=QFormLayout(); self.interval=QComboBox(); self.interval.addItems(['30','60','120','300']); self.interval.setCurrentText(str(settings.scan_interval_seconds)); self.qty=QLineEdit(str(settings.fixed_quantity)); self.tp=QLineEdit(str(settings.take_profit_percent)); form.addRow('Scan interval',self.interval); form.addRow('Order quantity',self.qty); form.addRow('Take profit (%)',self.tp); form.addRow('Limits',lab(f'Max executed {settings.max_executed_orders} • Max positions {settings.max_active_positions}','Muted')); ql.addLayout(form); l.addWidget(q); r,rl=make_panel('LIVE SCANNER RESULTS'); self.scan_table=self.table(['Symbol','Signal','Score','Entry','Stop','Target','TP %']); rl.addWidget(self.scan_table); l.addWidget(r,1); return w
    def right(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(10); p,pl=make_panel('EXECUTION GATE'); self.gate=lab('WAITING','Warn'); pl.addWidget(self.gate); self.bar=QProgressBar(); self.bar.setRange(0,settings.max_executed_orders); pl.addWidget(self.bar); self.gate_detail=lab('Fresh Positions + Open Orders + Risk + Max Executed','Muted'); self.gate_detail.setWordWrap(True); pl.addWidget(self.gate_detail); l.addWidget(p); a,al=make_panel('LATEST AI ANALYSIS'); self.analysis={}
        for n in ['Signal','Score','Entry','Stop','Target','Reasons']:
            r=QHBoxLayout(); r.addWidget(lab(n,'Muted')); v=lab('—','StatusValue'); v.setWordWrap(True); r.addWidget(v,1); al.addLayout(r); self.analysis[n]=v
        l.addWidget(a); o,ol=make_panel('RECENT ORDERS'); self.orders=self.table(['Time','Symbol','Action','Qty','Entry','Stop','Target','Status','ID']); ol.addWidget(self.orders); l.addWidget(o,1); x,xl=make_panel('LIVE ACTIVITY'); self.log=QPlainTextEdit(); self.log.setReadOnly(True); xl.addWidget(self.log); l.addWidget(x,1); return w
    def portfolio_page(self):
        w=QWidget(); l=QVBoxLayout(w); p,pl=make_panel('PORTFOLIO'); g=QGridLayout(); self.account=Metric('NET LIQUIDATION','—','IBKR account'); self.pc=Metric('ACTIVE POSITIONS','—',f'Max {settings.max_active_positions}'); self.po=Metric('OPEN ORDERS','—',f'Max {settings.max_open_orders}'); g.addWidget(self.account,0,0); g.addWidget(self.pc,0,1); g.addWidget(self.po,0,2); pl.addLayout(g); l.addWidget(p); q,ql=make_panel('LIVE POSITIONS'); self.positions=self.table(['Symbol','Quantity','Source']); ql.addWidget(self.positions); l.addWidget(q,1); return w
    def orders_page(self):
        w=QWidget(); l=QVBoxLayout(w); p,pl=make_panel('ORDER MONITOR'); self.all_orders=self.table(['Time','Symbol','Action','Qty','Entry','Stop','Target','Status','Filled','ID']); pl.addWidget(self.all_orders); l.addWidget(p,1); return w
    def ai_page(self):
        w=QWidget(); l=QVBoxLayout(w); p,pl=make_panel('AI SIGNAL CENTER'); self.ai_title=lab('No signal received','Title'); self.ai_state=lab('WAITING','Warn'); self.ai_reason=lab('Latest scanner/TradingView decision appears here.','Muted'); self.ai_reason.setWordWrap(True); pl.addWidget(self.ai_title); pl.addWidget(self.ai_state); pl.addWidget(self.ai_reason); l.addWidget(p); q,ql=make_panel('SIGNAL CONTEXT'); self.ai_table=self.table(['Indicator','Value']); ql.addWidget(self.ai_table); l.addWidget(q,1); return w
    def risk_page(self):
        w=QWidget(); l=QVBoxLayout(w); p,pl=make_panel('RISK CONTROL'); f=QFormLayout(); vals=[('Max executed',settings.max_executed_orders),('Max positions',settings.max_active_positions),('Max open orders',settings.max_open_orders),('Risk / trade',f'{settings.risk_per_trade*100:.2f}%'),('Reward / Risk',settings.reward_risk),('ATR stop',settings.atr_stop_mult),('Scope',settings.execution_count_scope)]; [f.addRow(k,lab(v,'StatusValue')) for k,v in vals]; pl.addLayout(f); l.addWidget(p); q,ql=make_panel('EXECUTION POLICY'); self.risk_state=lab('WAITING','Warn'); ql.addWidget(lab('Every order must pass fresh broker Positions + Open Orders + Risk + Max Executed checks.','Muted')); ql.addWidget(self.risk_state); l.addWidget(q); l.addStretch(1); return w
    def settings_page(self):
        w=QWidget(); l=QVBoxLayout(w); p,pl=make_panel('SYSTEM SETTINGS'); f=QFormLayout(); rows=[('IBKR Host',settings.ib_host),('IBKR Port',settings.ib_port),('Client ID',settings.ib_client_id),('Exchange',settings.exchange),('Currency',settings.currency),('Timeframe',settings.timeframe),('Mode','PAPER ONLY'),('TradingView',f'{settings.tradingview_webhook_host}:{settings.tradingview_webhook_port}'),('Webhook Token','••••••••')]; [f.addRow(k,lab(v,'StatusValue')) for k,v in rows]; pl.addLayout(f); pl.addWidget(lab('Live trading is disabled by design.','Warn')); l.addWidget(p); l.addStretch(1); return w
    def footer(self): l=QHBoxLayout(); self.status=lab('Disconnected','Muted'); l.addWidget(self.status); l.addStretch(1); l.addWidget(lab('PAPER MODE','Warn')); l.addSpacing(12); l.addWidget(lab(f'MAX {settings.max_executed_orders} ORDERS','Muted')); return l
    @staticmethod
    def table(headers):
        t=QTableWidget(0,len(headers)); t.setHorizontalHeaderLabels(headers); t.setAlternatingRowColors(True); t.setSelectionBehavior(QTableWidget.SelectRows); t.setEditTriggers(QTableWidget.NoEditTriggers); t.verticalHeader().setVisible(False); t.horizontalHeader().setStretchLastSection(True); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); return t
    def clock(self): self.clock_label.setText(datetime.now().strftime('%Y-%m-%d  %H:%M:%S'))
    def log_line(self,text): self.log.appendPlainText(f'[{datetime.now().strftime("%H:%M:%S")}] {text}')
    def start(self):
        if self.thread and self.thread.isRunning(): return
        try: qty=int(self.qty.text()); tp=float(self.tp.text()); interval=int(self.interval.currentText())
        except ValueError: self.status.setText('Invalid scanner settings'); return
        if qty<=0 or tp<=0 or interval<=0: self.status.setText('Values must be positive'); return
        settings.fixed_quantity=qty; settings.take_profit_percent=tp; settings.scan_interval_seconds=interval; self.thread=QThread(self); self.worker=ScannerWorker(interval); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.status.connect(self.on_status); self.worker.scan.connect(self.on_scan); self.worker.order.connect(self.on_order); self.worker.snapshot.connect(self.on_snapshot); self.worker.error.connect(self.on_error); self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.start(); self.connect.setEnabled(False); self.stop_btn.setEnabled(True); self.qty.setEnabled(False); self.tp.setEnabled(False); self.interval.setEnabled(False); self.side_ibkr.setText('IBKR  CONNECTING'); self.side_ibkr.setObjectName('Warn'); self.side_ibkr.style().unpolish(self.side_ibkr); self.side_ibkr.style().polish(self.side_ibkr); self.log_line('Scanner started — waiting for fresh IBKR verification')
    def stop(self):
        if self.worker: self.worker.stop()
        self.stop_btn.setEnabled(False); self.connect.setEnabled(True); self.qty.setEnabled(True); self.tp.setEnabled(True); self.interval.setEnabled(True); self.log_line('Scanner stop requested')
    def on_snapshot(self,d):
        pos=d.get('positions') or []; opens=d.get('open_orders') or []; executed=int(d.get('executed') or 0); maximum=int(d.get('maximum') or settings.max_executed_orders); account=d.get('account_value'); self.m_ibkr.value.setText('CONNECTED'); self.m_ibkr.sub.setText('Fresh broker snapshot'); self.side_ibkr.setText('IBKR  CONNECTED'); self.side_ibkr.setObjectName('Good'); self.positions_metric_update(pos,opens,executed,maximum); self.account.value.setText(f'${account:,.2f}' if account is not None else '—'); self.pc.value.setText(len(pos)); self.po.value.setText(len(opens)); self.positions.setRowCount(0); [self.add_pos(x) for x in pos]; self.all_orders.setRowCount(0); [self.add_trade(self.all_orders,x) for x in opens]; self.gate_detail.setText(f'Positions {len(pos)}/{settings.max_active_positions} • Open orders {len(opens)}/{settings.max_open_orders} • Executed {executed}/{maximum}'); self.risk_state.setText('BROKER VERIFIED'); self.risk_state.setObjectName('Good')
    def positions_metric_update(self,pos,opens,executed,maximum): self.m_pos.value.setText(len(pos)); self.m_open.value.setText(len(opens)); self.m_exec.value.setText(f'{executed} / {maximum}'); self.bar.setMaximum(maximum); self.bar.setValue(min(executed,maximum))
    def add_pos(self,p): r=self.positions.rowCount(); self.positions.insertRow(r); self.positions.setItem(r,0,QTableWidgetItem(str(p.get('symbol','')))); self.positions.setItem(r,1,QTableWidgetItem(str(p.get('quantity','')))); self.positions.setItem(r,2,QTableWidgetItem('IBKR LIVE'))
    def add_trade(self,t,tr):
        o=getattr(tr,'order',None); st=getattr(getattr(tr,'orderStatus',None),'status','') or ''; fill=getattr(getattr(tr,'orderStatus',None),'filled',0) or 0; c=getattr(tr,'contract',None); vals=['LIVE',getattr(c,'symbol','') if c else '',getattr(o,'action','') if o else '',getattr(o,'totalQuantity','') if o else '',getattr(o,'lmtPrice','') or '—','—','—',st,fill,getattr(o,'orderId','') if o else '']; r=t.rowCount(); t.insertRow(r); [t.setItem(r,i,QTableWidgetItem(str(v))) for i,v in enumerate(vals[:t.columnCount()])]
    def on_status(self,text):
        self.status.setText(text); self.log_line(text)
        if 'TradingView queue' in text: self.side_tv.setText('TRADINGVIEW  ACTIVE')
        if 'ORDER SUBMITTED' in text: self.gate.setText('ORDER SUBMITTED'); self.m_gate.value.setText('SUBMITTED')
        elif 'kept inside bot' in text: self.gate.setText('BLOCKED / QUEUED'); self.m_gate.value.setText('BLOCKED'); self.gate_detail.setText(text)
        elif 'Portfolio verified' in text: self.gate.setText('VERIFIED'); self.m_gate.value.setText('VERIFIED')
        elif 'Disconnected' in text: self.disconnected()
    def disconnected(self):
        self.m_ibkr.value.setText('DISCONNECTED'); self.m_ibkr.sub.setText('No live broker data'); self.side_ibkr.setText('IBKR  OFFLINE'); self.m_pos.value.setText('—'); self.m_open.value.setText('—'); self.gate.setText('WAITING'); self.m_gate.value.setText('WAITING'); self.gate_detail.setText('Broker disconnected — execution is fail-closed.'); self.positions.setRowCount(0); self.all_orders.setRowCount(0)
    def on_error(self,text): self.status.setText('Error: '+text); self.gate.setText('FAIL-CLOSED'); self.m_gate.value.setText('FAIL-CLOSED'); self.gate_detail.setText(text); self.log_line('ERROR: '+text)
    def on_scan(self,d):
        s=d['signal']; symbol=d['symbol']; ctx=d.get('context') or {}; chart=d.get('chart') or {}; self.chart_symbol.setText(symbol); self.chart_price.setText(f'{s.entry:.4f}'); self.chart_state.setText(f'Signal: {s.action} • Score: {s.score}'); self.chart.set_data(chart.get('close')); self.m_sig.value.setText(s.action); self.m_sig.sub.setText(f'{symbol} • score {s.score}')
        for n,v in [('Signal',s.action),('Score',s.score),('Entry',f'{s.entry:.4f}'),('Stop',f'{s.stop:.4f}' if s.stop is not None else '—'),('Target',f'{s.target:.4f}' if s.target is not None else '—'),('Reasons',' • '.join(s.reasons) if s.reasons else '—')]: self.analysis[n].setText(str(v))
        self.ai_title.setText(f'{symbol} — {s.action} — Score {s.score}'); self.ai_state.setText('BUY CANDIDATE' if s.action=='BUY' else ('SELL SIGNAL — HELD' if s.action=='SELL' else 'HOLD')); self.ai_reason.setText(' • '.join(s.reasons) if s.reasons else 'No additional reasons.'); self.ai_table.setRowCount(0)
        for k,v in ctx.items(): r=self.ai_table.rowCount(); self.ai_table.insertRow(r); self.ai_table.setItem(r,0,QTableWidgetItem(str(k))); self.ai_table.setItem(r,1,QTableWidgetItem(str(v)))
        for k,w in self.ctx.items(): v=ctx.get(k); w.setText('—' if v is None else f'{v:.4f}' if isinstance(v,(int,float)) else str(v))
        if ctx.get('above_cloud'): self.cloud.setText('Cloud: ABOVE — bullish structure')
        elif ctx.get('below_cloud'): self.cloud.setText('Cloud: BELOW — bearish structure')
        r=next((x for x in range(self.scan_table.rowCount()) if self.scan_table.item(x,0) and self.scan_table.item(x,0).text()==symbol),-1); r=self.scan_table.rowCount() if r<0 else r
        if r==self.scan_table.rowCount(): self.scan_table.insertRow(r)
        vals=[symbol,s.action,s.score,f'{s.entry:.4f}',f'{s.stop:.4f}' if s.stop is not None else '—',f'{s.target:.4f}' if s.target is not None else '—',f'{settings.take_profit_percent:.2f}%']; [self.scan_table.setItem(r,i,QTableWidgetItem(str(v))) for i,v in enumerate(vals)]
    def on_order(self,record):
        for t in [self.orders,self.all_orders]: r=t.rowCount(); t.insertRow(r); vals=[record.time,record.symbol,record.action,record.quantity,f'{record.entry_limit:.4f}',f'{record.stop:.4f}' if record.stop is not None else '—',f'{record.target:.4f}' if record.target is not None else '—',record.status,getattr(record,'filled_quantity',0),record.order_id]; [t.setItem(r,i,QTableWidgetItem(str(v))) for i,v in enumerate(vals[:t.columnCount()])]
        self.log_line(f'ORDER {record.action} {record.symbol} qty={record.quantity} id={record.order_id}')
    def closeEvent(self,e):
        if self.worker: self.worker.stop()
        if self.thread: self.thread.quit(); self.thread.wait(3000)
        e.accept()

def run():
    app=QApplication(sys.argv); app.setStyleSheet(STYLE); app.setFont(QFont('Segoe UI',10)); w=MainWindow(); w.show(); return app.exec()

if __name__=='__main__': run()
