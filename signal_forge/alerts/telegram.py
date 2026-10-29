"""
Telegram Alert Dispatcher.
Formats professional alert messages, respects rate limits, and provides safe mock fallback.
Strictly non-trading informational alerts.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import hashlib
import time
import requests
from signal_forge.config import config
from signal_forge.database.db import DatabaseManager, db
from signal_forge.models.signal import AlertRecord, Direction, SignalCandidate
from signal_forge.observability.logger import get_logger
from signal_forge.observability.retry import retry_with_backoff

logger = get_logger("telegram_alert")


def _to_kst_str(iso_utc: str) -> str:
    """Converts ISO UTC string to Asia/Seoul formatted string."""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        kst = dt.astimezone(timezone(timedelta(hours=9)))
        return kst.strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        return iso_utc


class TelegramAlertDispatcher:
    def __init__(self, database: DatabaseManager = db):
        self.db = database
        self.token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.is_live = config.is_telegram_live
        self._dispatched_hashes: set = set()

    def format_alert(self, signal: SignalCandidate) -> str:
        """Formats signal into clean, structured Telegram message."""
        dir_emoji = "🟢 LONG" if signal.direction == Direction.LONG else "🔴 SHORT"
        detected_kst = _to_kst_str(signal.first_detected_at)

        # Market label
        if signal.symbol.startswith("KRW-"):
            market_label = "업비트 (Upbit KRW 마켓)"
            chart_link = f"https://upbit.com/exchange?code=CRIX.UPBIT.{signal.symbol}"
        elif signal.asset_type.value == "COIN":
            market_label = "Binance Futures USDⓈ-M"
            chart_link = f"https://www.binance.com/en/futures/{signal.symbol}"
        elif signal.asset_type.value == "STOCK_KR":
            market_label = "한국 주식 (KOSPI/KOSDAQ)"
            chart_link = f"https://finance.naver.com/item/main.naver?code={signal.symbol}"
        else:
            market_label = "미국 주식 (NYSE/NASDAQ)"
            chart_link = f"https://finance.yahoo.com/quote/{signal.symbol}"

        rvol_val = signal.indicators.get("rvol", 1.0)
        rvol_str = f"{rvol_val:.2f}x" if isinstance(rvol_val, (int, float)) else str(rvol_val)

        lines = [
            "🔔 SIGNAL FORGE ALERT",
            f"시장: {market_label}",
            f"종목: {signal.symbol}",
            f"방향: {dir_emoji} [{signal.tier.value}]",
            f"전략: {signal.strategy_name} ({signal.strategy_id})",
            "",
            f"발견시각: {detected_kst}",
            f"기준가격: {signal.price:,.4f}" if signal.price < 10 else f"기준가격: {signal.price:,.2f}",
            f"거래량 구조: RVOL {rvol_str}",
            f"점수: {signal.score:.1f}/100",
            "",
            "[발견 근거]",
            f"• {signal.trigger_reason}",
        ]

        if signal.catalyst_summary:
            lines.extend([
                "",
                "[공시·뉴스·커뮤니티 검증]",
                f"• {signal.catalyst_summary}",
            ])

        if signal.invalidation_condition:
            lines.extend([
                "",
                "[신호 무효화 조건]",
                f"• {signal.invalidation_condition}",
            ])

        if signal.risk_notes:
            lines.extend(["", "[위험 요소]"] + [f"• {r}" for r in signal.risk_notes])

        lines.extend([
            "",
            f"출처 / 원문: {signal.source_url or '공개 시장 데이터'}",
            f"차트 링크: {chart_link}",
            "",
            "ℹ️ 본 알람은 투자 분석 정보이며 자동 주문을 실행하지 않습니다.",
        ])

        return "\n".join(lines)

    def send_alert(self, signal: SignalCandidate) -> bool:
        """Sends alert message or logs to file if in mock/dry-run mode."""
        msg = self.format_alert(signal)

        if not self.is_live or signal.is_mock:
            # Safe local mock mode
            logger.info(
                f"[MOCK_TELEGRAM_ALERT] Successfully formatted alert for {signal.symbol}:\n{msg}"
            )
            self.db.save_alert_record(
                AlertRecord(
                    signal_id=signal.signal_id,
                    channel="TELEGRAM",
                    status="MOCK",
                    response_msg="Mock alert logged to file (Telegram not live)",
                )
            )
            return True

        # Live dispatch
        return self._dispatch_telegram(signal.signal_id, msg)

    def is_already_dispatched(self, signal_id: str, text: str) -> bool:
        """Strict Deduplication: Once an alert has been sent, it is NEVER sent again.
        Checks both SQLite alert_history for signal_id and in-memory content hash.
        """
        # 1. Check signal_id in alert_history (excluding batch_aggregate which aggregates multiple trades)
        if signal_id and signal_id != "batch_aggregate":
            try:
                with self.db.get_connection() as conn:
                    cnt = conn.execute(
                        "SELECT COUNT(*) FROM alert_history WHERE signal_id = ? AND status = 'SUCCESS';",
                        (signal_id,),
                    ).fetchone()[0]
                    if cnt > 0:
                        return True
            except Exception as e:
                logger.warning(f"Error checking alert_history for {signal_id}: {e}")

        # 2. Check message content hash
        text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        if text_hash in self._dispatched_hashes:
            return True

        return False

    def _dispatch_telegram(self, signal_id: str, text: str) -> bool:
        # Strict Rule: An alert that has been sent once must never be sent again.
        if self.is_already_dispatched(signal_id, text):
            logger.info(
                f"[TELEGRAM DEDUP] Alert for signal '{signal_id}' already sent previously. "
                f"Strictly suppressed (한번 보낸 알람 재전송 영구 방지)."
            )
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                    self._dispatched_hashes.add(text_hash)
                    self.db.save_alert_record(
                        AlertRecord(
                            signal_id=signal_id,
                            channel="TELEGRAM",
                            status="SUCCESS",
                            response_msg="HTTP 200 OK",
                        )
                    )
                    logger.info(f"[TELEGRAM] Alert sent successfully for signal {signal_id}")
                    time.sleep(1.0)  # Safe 1-sec cooldown between telegram messages
                    return True
                elif resp.status_code == 429:
                    try:
                        data = resp.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 3)
                    except Exception:
                        retry_after = 3
                    logger.warning(f"[TELEGRAM] 429 Rate limited. Waiting {retry_after}s before retry...")
                    time.sleep(retry_after + 0.5)
                    continue
                else:
                    err_text = resp.text
                    logger.error(f"[TELEGRAM] Failed with HTTP {resp.status_code}: {err_text}")
                    self.db.save_alert_record(
                        AlertRecord(
                            signal_id=signal_id,
                            channel="TELEGRAM",
                            status="FAILED",
                            response_msg=f"HTTP {resp.status_code}: {err_text[:200]}",
                        )
                    )
                    return False
            except Exception as e:
                logger.error(f"[TELEGRAM] Connection error on attempt {attempt+1}: {e}")
                if attempt == 2:
                    self.db.save_alert_record(
                        AlertRecord(
                            signal_id=signal_id,
                            channel="TELEGRAM",
                            status="FAILED",
                            response_msg=str(e)[:200],
                        )
                    )
                    raise
                time.sleep(1.5)
        return False


# Default global instance
telegram_dispatcher = TelegramAlertDispatcher()
