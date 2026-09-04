from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 101

    account: str = ""

    exchange: str = "SMART"
    currency: str = "USD"

    timeframe: str = "10 mins"
    history_duration: str = "7 D"

    # =====================================================
    # PAPER TRADING
    # =====================================================

    paper_trading: bool = True

    # =====================================================
    # WATCHLIST / SCANNER
    # =====================================================

    symbol: str = "BIAF"

    watchlist_file: str = "watchlist.txt"

    top_gainers_count: int = 10

    scan_interval_seconds: int = 60

    # =====================================================
    # STRATEGY
    # =====================================================

    min_score: int = 4

    # =====================================================
    # ORDER SETTINGS
    # =====================================================

    # Default quantity
    # Can be changed from the GUI
    fixed_quantity: int = 100

    # Take Profit
    # Default = 10%
    take_profit_percent: float = 10.0

    # =====================================================
    # MAXIMUM ACTIVE TRADES
    # =====================================================

    # Maximum number of active positions/orders
    # created/managed by the bot.
    #
    # Once 7 slots are occupied, no new broker order
    # will be sent.
    max_active_trades: int = 7

    # =====================================================
    # RISK / STOP
    # =====================================================

    risk_per_trade: float = 0.01

    paper_account_value: float = 100000.0

    atr_stop_mult: float = 1.5

    reward_risk: float = 2.0

    # =====================================================
    # ENV
    # =====================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
