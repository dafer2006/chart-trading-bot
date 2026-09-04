from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 101
    account: str = ""
    exchange: str = "SMART"
    currency: str = "USD"
    timeframe: str = "5 mins"
    history_duration: str = "2 D"
    paper_trading: bool = True
    symbol: str = "AAPL"
    min_score: int = 4
    risk_per_trade: float = 0.01
    atr_stop_mult: float = 1.5
    reward_risk: float = 2.0
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
