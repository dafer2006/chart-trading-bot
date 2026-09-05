from PySide6.QtWidgets import QApplication

from desktop.tradingview_window import TradingViewConnectionWindow


if __name__ == "__main__":
    app = QApplication([])
    window = TradingViewConnectionWindow()
    window.show()
    raise SystemExit(app.exec())
