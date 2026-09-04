from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime

class TradingViewSignalStore:
    def __init__(self,path="data/tradingview.sqlite3"):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def _db(self):return sqlite3.connect(self.path)
    def _init(self):
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT,action TEXT,price REAL,stop REAL,target REAL,score INTEGER,message TEXT,created_at TEXT,processed INTEGER DEFAULT 0)")
            db.commit()
    def add(self,signal):
        with self._db() as db:
            cur=db.execute("INSERT INTO signals(symbol,action,price,stop,target,score,message,created_at) VALUES(?,?,?,?,?,?,?,?)",(signal.symbol.upper(),signal.action.upper(),signal.price,signal.stop,signal.target,signal.score,signal.message,datetime.now().isoformat(timespec="seconds")))
            db.commit();return cur.lastrowid
    def pending(self,limit=50):
        with self._db() as db:
            return db.execute("SELECT id,symbol,action,price,stop,target,score,message FROM signals WHERE processed=0 ORDER BY id LIMIT ?",(limit,)).fetchall()
    def mark_processed(self,signal_id):
        with self._db() as db:
            db.execute("UPDATE signals SET processed=1 WHERE id=?",(signal_id,));db.commit()
