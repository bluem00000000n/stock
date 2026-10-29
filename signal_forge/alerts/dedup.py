"""
Signal Deduplication Engine.
Suppresses repeated alerts within configurable cooldown windows and tracks first detection times.
"""

from typing import Tuple
from signal_forge.config import config
from signal_forge.database.db import DatabaseManager, db
from signal_forge.models.signal import SignalCandidate, SignalStatus
from signal_forge.observability.logger import get_logger

logger = get_logger("dedup")


class DeduplicationEngine:
    def __init__(self, database: DatabaseManager = db):
        self.db = database
        self.default_cooldown = config.dedup_cooldown_minutes
        self.overrides = (
            config.alert_rules_cfg.get("deduplication", {}).get("strategy_cooldown_overrides", {})
        )

    def get_cooldown_minutes(self, strategy_id: str) -> int:
        return self.overrides.get(strategy_id, self.default_cooldown)

    def check_and_filter(self, candidate: SignalCandidate) -> Tuple[bool, str]:
        """
        Determines whether the candidate is a duplicate or should be alerted.
        Returns: (should_alert: bool, reason: str)
        """
        cooldown = self.get_cooldown_minutes(candidate.strategy_id)
        is_dup = self.db.is_duplicate_signal(
            symbol=candidate.symbol,
            strategy_id=candidate.strategy_id,
            direction=candidate.direction,
            cooldown_minutes=cooldown,
        )

        if is_dup:
            logger.info(
                f"[DEDUP] Suppressed duplicate signal for {candidate.symbol} "
                f"({candidate.strategy_id} {candidate.direction.value}) within {cooldown}m window."
            )
            return False, f"Duplicate signal within {cooldown}m cooldown window"

        return True, "Unique signal verified"


# Default global instance
dedup_engine = DeduplicationEngine()
