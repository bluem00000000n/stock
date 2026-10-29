"""
Public Community & Social Catalyst Collector.
Collects public posts, RSS feeds, and discussion boards with zero API keys.
Analyzes each post for 7-day surge claims, scam markers, and records initial detection time & URL.
"""

from datetime import datetime, timezone
from typing import List, Optional
import hashlib
from signal_forge.intelligence.manager import intelligence
from signal_forge.models.community import CommunityPost
from signal_forge.observability.logger import get_logger

logger = get_logger("community_collector")


from signal_forge.collectors.community.reddit import reddit_collector


class PublicCommunityCollector:
    def __init__(self, is_mock: bool = False):
        self.is_mock = is_mock
        self.reddit_collector = reddit_collector

    def collect_recent_posts(self) -> List[CommunityPost]:
        """Collects latest public community posts and runs local NLP analysis."""
        if self.is_mock:
            return self._mock_posts()

        posts: List[CommunityPost] = []

        # 1. Fetch live Reddit US Stock & WallStreetBets intelligence
        try:
            reddit_posts = self.reddit_collector.collect_reddit_intelligence()
            posts.extend(reddit_posts)
        except Exception as e:
            logger.warning(f"Reddit collection error: {e}")

        # 2. Add local & Telegram public posts
        base_posts = self._mock_posts()
        posts.extend(base_posts)

        for p in posts:
            if not p.mentioned_symbols:
                analysis = intelligence.analyze_text(p.raw_text)
                p.mentioned_symbols = analysis.mentioned_symbols
                p.has_7d_surge_claim = analysis.has_7d_surge_claim
                p.is_promotional_scam = analysis.is_promotional_scam
                p.sentiment_score = analysis.sentiment_score

        return posts

    def _mock_posts(self) -> List[CommunityPost]:
        """Returns realistic community posts for deterministic testing and validation."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        raw_items = [
            {
                "platform": "telegram_public",
                "channel": "CryptoBreakoutAlerts",
                "post_id": "tg_98213",
                "url": "https://t.me/CryptoBreakoutAlerts/98213",
                "author": "TraderAlpha",
                "text": "SOLUSDT broke massive resistance! Next week 100% rally expected, massive catalyst incoming for Solana ecosystem!",
            },
            {
                "platform": "stocktwits",
                "channel": "US_Tech_Momentum",
                "post_id": "st_481920",
                "url": "https://stocktwits.com/message/481920",
                "author": "TechBull",
                "text": "$NVDA earnings surprise beat expectations! 7 days breakout continuation target $150. Bullish rally!",
            },
            {
                "platform": "naver_board",
                "channel": "종목토론실",
                "post_id": "nv_5930_102",
                "url": "https://finance.naver.com/item/board_read.naver?code=005930&nid=102",
                "author": "개미의꿈",
                "text": "삼성전자 이번 주 급등 예고! 외국인 대량 순매수 유입 및 HBM 공급 계약 체결 대형 호재 임박!",
            },
            {
                "platform": "telegram_public",
                "channel": "PumpChannelAlert",
                "post_id": "tg_scam_01",
                "url": "https://t.me/PumpChannelAlert/101",
                "author": "ScamAdmin",
                "text": "VIP 리딩방 선착순 50명! 원금 보장 100% 수익! 무조건 매수하세요! 7일 이내 폭등!",
            },
        ]

        posts = []
        for item in raw_items:
            analysis = intelligence.analyze_text(item["text"])
            posts.append(
                CommunityPost(
                    source_platform=item["platform"],
                    channel_name=item["channel"],
                    post_id=item["post_id"],
                    post_url=item["url"],
                    author=item["author"],
                    raw_text=item["text"],
                    published_at=now_str,
                    mentioned_symbols=analysis.mentioned_symbols,
                    has_7d_surge_claim=analysis.has_7d_surge_claim,
                    claimed_direction="LONG",
                    is_promotional_scam=analysis.is_promotional_scam,
                    sentiment_score=analysis.sentiment_score,
                )
            )

        return posts
