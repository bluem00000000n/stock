"""
Configuration loader and runtime environment manager for Signal Forge Alert.
Loads YAML configurations and environment variables with zero external API key requirements.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

# Project Root Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _str_to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "y", "on")


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    def __init__(self):
        # 1. Base Paths
        self.project_root = PROJECT_ROOT
        self.config_dir = PROJECT_ROOT / "config"
        
        # 2. Load YAML files
        self.app_cfg = _load_yaml(self.config_dir / "app.yaml")
        self.markets_cfg = _load_yaml(self.config_dir / "markets.yaml")
        self.strategies_cfg = _load_yaml(self.config_dir / "strategies.yaml")
        self.alert_rules_cfg = _load_yaml(self.config_dir / "alert_rules.yaml")
        self.schedules_cfg = _load_yaml(self.config_dir / "schedules.yaml")

        # 3. Runtime Directories
        runtime_data_rel = os.getenv("RUNTIME_DATA_DIR", "runtime/data")
        runtime_logs_rel = os.getenv("RUNTIME_LOGS_DIR", "runtime/logs")
        
        self.data_dir = self.project_root / runtime_data_rel if not os.path.isabs(runtime_data_rel) else Path(runtime_data_rel)
        self.logs_dir = self.project_root / runtime_logs_rel if not os.path.isabs(runtime_logs_rel) else Path(runtime_logs_rel)
        self.cache_dir = self.project_root / "runtime/cache"
        
        # Ensure runtime directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        db_rel = os.getenv("DATABASE_PATH", "runtime/data/signal_forge.db")
        self.database_path = self.project_root / db_rel if not os.path.isabs(db_rel) else Path(db_rel)

        log_rel = os.getenv("LOG_FILE", "runtime/logs/signal_forge.log")
        self.log_file = self.project_root / log_rel if not os.path.isabs(log_rel) else Path(log_rel)
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # 4. Operational Flags
        self.app_env = os.getenv("APP_ENV", "development")
        self.use_mock = _str_to_bool(os.getenv("USE_MOCK"), default=False)
        self.dry_run = _str_to_bool(os.getenv("DRY_RUN"), default=False)

        # 5. Binance Public Market Data (Unauthenticated)
        self.binance_base_url = os.getenv("BINANCE_FUTURES_BASE_URL", "https://fapi.binance.com").rstrip("/")
        self.binance_timeout_sec = int(os.getenv("BINANCE_REQUEST_TIMEOUT_SEC", "10"))
        self.binance_max_retries = int(os.getenv("BINANCE_MAX_RETRIES", "3"))

        # 6. Web Scrapers (Zero API Key)
        self.user_agent = os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self.scraper_timeout_sec = int(os.getenv("SCRAPER_REQUEST_TIMEOUT_SEC", "10"))

        # 7. Telegram Bot Alerts
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.mock_telegram = _str_to_bool(os.getenv("MOCK_TELEGRAM"), default=False)
        self.send_raw_alerts = _str_to_bool(os.getenv("SEND_RAW_ALERTS"), default=False)

        # 8. Deduplication
        self.dedup_cooldown_minutes = int(os.getenv("DEDUP_COOLDOWN_MINUTES", "60"))

        # 9. Local AI & Heuristic Rules
        self.ai_provider = os.getenv("AI_PROVIDER", "rules").lower()
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1").rstrip("/")
        self.lm_studio_model = os.getenv("LM_STUDIO_MODEL", "local-model")

    @property
    def telegram_configured(self) -> bool:
        """Returns True only when both bot token and chat ID are present."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def is_telegram_live(self) -> bool:
        """Determines if actual Telegram network API calls should be dispatched."""
        if self.mock_telegram or self.dry_run or not self.telegram_configured:
            return False
        return True

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides a complete status summary for diagnostics and CLI doctor."""
        return {
            "app_version": "0.2.0",
            "environment": self.app_env,
            "zero_api_key_architecture": True,
            "market_data_mode": "MOCK" if self.use_mock else "REAL (Unauthenticated Public Endpoints & Scrapers)",
            "telegram_mode": "LIVE" if self.is_telegram_live else ("DRY-RUN" if self.dry_run else "MOCK (File Log / No Token)"),
            "intelligence_provider": self.ai_provider.upper(),
            "database_path": str(self.database_path),
            "log_file": str(self.log_file),
            "dedup_cooldown_min": self.dedup_cooldown_minutes,
        }


# Global singleton configuration
config = Config()
