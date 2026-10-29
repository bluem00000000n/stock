"""
Community and sentiment domain models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
import hashlib


@dataclass
class CommunityPost:
    source_platform: str  # e.g. "telegram_public", "reddit", "stocktwits", "naver_board"
    channel_name: str
    post_id: str
    post_url: str
    author: str
    raw_text: str
    published_at: str
    mentioned_symbols: List[str] = field(default_factory=list)
    has_7d_surge_claim: bool = False
    claimed_direction: str = "LONG"
    claimed_target_price: Optional[float] = None
    claimed_return_pct: Optional[float] = None
    is_promotional_scam: bool = False
    sentiment_score: float = 0.0  # -1.0 to 1.0
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()
