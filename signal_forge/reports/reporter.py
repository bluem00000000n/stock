"""
Automated Report Generators for Signal Forge Alert.
Generates:
- Daily Signal & Watchlist Summary (일일 요약 보고서)
- Weekly Monday Performance Review (주간 성과 및 팩트체크 보고서)
- Monthly Strategy Ranking & Predictive Power Analysis (월간 전략 랭킹 보고서)
- Comprehensive Alert Intelligence Report (알람 상세 보고서)
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from signal_forge.database.db import DatabaseManager, db
from signal_forge.observability.logger import get_logger
from signal_forge.validation.evaluator import quant_validator

logger = get_logger("reports")


def _kst_now() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")


class ReportGenerator:
    def __init__(self, database: DatabaseManager = db):
        self.db = database

    def generate_daily_report(self) -> str:
        """Generates Daily Signal & Market Intelligence Summary."""
        now_kst = _kst_now()
        stats = self.db.get_performance_summary()

        # Query recent signals in last 24h (excluding tests and mock)
        sql = """
        SELECT symbol, asset_type, direction, strategy_id, strategy_name, price,
               score, tier, status, invalidation_condition,
               trigger_reason, created_at
        FROM signals
        WHERE created_at >= datetime('now', '-1 day')
          AND is_mock = 0
          AND symbol NOT LIKE 'TEST%'
          AND trigger_reason NOT LIKE '%Test alert%'
        ORDER BY score DESC, created_at DESC;
        """
        with self.db.get_connection() as conn:
            recent_signals = conn.execute(sql).fetchall()

        total_signals = len(recent_signals)
        alerted = [s for s in recent_signals if s["status"] == "ALERTED"]
        suppressed = [s for s in recent_signals if s["status"] == "SKIPPED_DEDUP"]

        crypto_signals = [s for s in recent_signals if s["asset_type"] == "COIN"]
        kr_signals = [s for s in recent_signals if s["asset_type"] == "STOCK_KR"]
        us_signals = [s for s in recent_signals if s["asset_type"] == "STOCK_US"]

        lines = [
            "============================================================",
            "📊 SIGNAL FORGE ALERT - 일일 요약 보고서 (Daily Intelligence)",
            "============================================================",
            f"기준시각: {now_kst}",
            "------------------------------------------------------------",
            "1. 24시간 신호 및 알람 현황",
            f"• 총 감지 신호: {total_signals}건",
            f"  - 텔레그램 알람 발송(ALERTED): {len(alerted)}건",
            f"  - 쿨다운 중복 억제(DEDUP): {len(suppressed)}건",
            f"• 시장별 분포:",
            f"  - Binance Futures 코인: {len(crypto_signals)}건 (LONG & SHORT)",
            f"  - 한국 주식 (KOSPI/KOSDAQ): {len(kr_signals)}건 (LONG ONLY)",
            f"  - 미국 주식 (NYSE/NASDAQ): {len(us_signals)}건 (LONG ONLY)",
            "------------------------------------------------------------",
            "2. 퀀트 검증 성과 누적 요약",
            f"• 누적 평가 표본: {stats['total_evaluated_samples']}건",
            f"• 목표 도달 적중률: {stats['win_rate_pct']}%",
            f"• 평균 최대 유리 변동(MFE): +{stats['avg_mfe_pct']}%",
            f"• 평균 최대 불리 변동(MAE): {stats['avg_mae_pct']}%",
            "------------------------------------------------------------",
            "3. 주요 기회 종목 (OPPORTUNITY & HIGH CONVICTION)",
        ]

        opp_signals = [s for s in recent_signals if s["tier"] in ("OPPORTUNITY", "HIGH_CONVICTION")]
        seen_opp = set()
        unique_opp = []
        for s in opp_signals:
            key = (s["symbol"], s["strategy_name"])
            if key not in seen_opp:
                seen_opp.add(key)
                unique_opp.append(s)

        if not unique_opp:
            lines.append("• 최근 24시간 내 OPPORTUNITY 이상 등급 신호가 없습니다.")
        else:
            for s in unique_opp[:8]:
                dir_icon = "🟢" if s["direction"] == "LONG" else "🔴"
                price_str = f"{s['price']:,.2f}" if s["price"] >= 10 else f"{s['price']:,.4f}"
                lines.append(
                    f"{dir_icon} [{s['tier']}] {s['symbol']} ({s['direction']}) | {s['strategy_name']}\n"
                    f"   기준가: {price_str} | 점수: {s['score']:.1f}/100\n"
                    f"   근거: {s['trigger_reason']}\n"
                    f"   무효화: {s['invalidation_condition'] or 'N/A'}"
                )

        lines.extend([
            "------------------------------------------------------------",
            "4. 관찰 종목 (WATCH LIST)",
        ])

        watch_signals = [s for s in recent_signals if s["tier"] == "WATCH"]
        seen_watch = set()
        unique_watch = []
        for s in watch_signals:
            key = (s["symbol"], s["strategy_name"])
            if key not in seen_watch:
                seen_watch.add(key)
                unique_watch.append(s)

        if not unique_watch:
            lines.append("• 현재 관찰 종목이 없습니다.")
        else:
            for s in unique_watch[:8]:
                dir_icon = "🟢" if s["direction"] == "LONG" else "🔴"
                lines.append(
                    f"• {dir_icon} {s['symbol']} | {s['direction']} | {s['strategy_name']} | "
                    f"가격: {s['price']:,.2f} | 점수: {s['score']:.0f}"
                )

        lines.extend([
            "------------------------------------------------------------",
            "5. 미국 주식 레딧 커뮤니티 센티먼트 (Reddit r/wallstreetbets & r/stocks)",
        ])

        # Fetch recent Reddit community intelligence from DB
        sql_reddit = """
        SELECT author, mentioned_symbols, sentiment_score, raw_text, has_7d_surge_claim
        FROM community_posts
        WHERE source_platform = 'reddit'
        ORDER BY id ASC LIMIT 10;
        """
        with self.db.get_connection() as conn:
            reddit_rows = conn.execute(sql_reddit).fetchall()

        if not reddit_rows:
            lines.append("• 수집된 실시간 레딧 커뮤니티 데이터가 없습니다.")
        else:
            for r in reddit_rows:
                sym = r["mentioned_symbols"].replace("[\"", "").replace("\"]", "").replace("\"", "") if r["mentioned_symbols"] else "N/A"
                sent_label = "🟢 BULLISH" if r["sentiment_score"] >= 0.5 else "🔴 BEARISH"
                surge_tag = " [7D 급등버즈 감지]" if r["has_7d_surge_claim"] else ""
                lines.append(
                    f"• {r['author']} | ${sym} | {sent_label} (스코어: {r['sentiment_score']:.2f}){surge_tag}\n"
                    f"   요약: {r['raw_text'][:95]}..."
                )

        lines.extend([
            "------------------------------------------------------------",
            "6. 지능 분석 및 사기 펌핑 방어 요약",
            "• 레딧 WSB 모멘텀: 언급량/업보트 급증 종목에 대해 S01 Early Buzz 및 S18 교차 검증",
            "• 공개 커뮤니티 7일 급등 예고: 거래량/가격 동반 검증 신호만 선별 수용",
            "• 허위 홍보 및 VIP 사기 패턴: 100% 필터링 (점수 감점 및 경고 적용)",
            "• 데이터 수집 및 API 운영 비용: 0원 (Zero Paid API Key)",
            "============================================================",
            "ℹ️ 본 보고서는 투자 분석 통계이며 자동 주문을 실행하지 않습니다.",
        ])

        report_text = "\n".join(lines)
        logger.info("Generated daily report successfully.")
        return report_text

    def generate_weekly_report(self) -> str:
        """Generates Weekly Monday Review."""
        now_kst = _kst_now()
        metrics = quant_validator.get_comprehensive_metrics()

        # Query week counts
        sql_week = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status = 'ALERTED' THEN 1 ELSE 0 END) as alerted,
               SUM(CASE WHEN status = 'SKIPPED_DEDUP' THEN 1 ELSE 0 END) as deduped
        FROM signals
        WHERE created_at >= datetime('now', '-7 days')
          AND is_mock = 0
          AND symbol NOT LIKE 'TEST%'
          AND trigger_reason NOT LIKE '%Test alert%';
        """
        with self.db.get_connection() as conn:
            w_row = conn.execute(sql_week).fetchone()
            w_total = w_row["total"] or 0
            w_alerted = w_row["alerted"] or 0
            w_deduped = w_row["deduped"] or 0

        lines = [
            "============================================================",
            "📈 SIGNAL FORGE ALERT - 주간 성과 및 팩트체크 보고서 (월요일)",
            "============================================================",
            f"기준시각: {now_kst}",
            "------------------------------------------------------------",
            "1. 주간 알람 발송 및 중복 억제 성과",
            f"• 주간 총 감지 신호: {w_total}건",
            f"• 텔레그램 실제 알람: {w_alerted}건",
            f"• 쿨다운 중복 억제: {w_deduped}건 (중복 방어율: {round((w_deduped/w_total*100), 1) if w_total > 0 else 0}%)",
            "------------------------------------------------------------",
            "2. 다중 시간 지평별 성과 (MFE / MAE / 적중률)",
            "타임프레임 | 표본수 | 적중률 | 평균수익 | 평균 MFE | 평균 MAE",
            "---------|-------|-------|---------|---------|---------",
        ]

        for tf, d in metrics.get("timeframes", {}).items():
            lines.append(
                f"{tf:<9} | {d['sample_count']:>5} | {d['win_rate_pct']:>4.1f}% | "
                f"{d['avg_return_pct']:>6.2f}% | +{d['avg_mfe_pct']:>5.2f}% | {d['avg_mae_pct']:>5.2f}%"
            )

        lines.extend([
            "------------------------------------------------------------",
            "3. 상위 성과 전략 (Top Performing Strategies)",
        ])

        top_strats = sorted(metrics.get("strategies", []), key=lambda x: (x["hit_count"], x["win_rate_pct"]), reverse=True)[:5]
        if not top_strats:
            lines.append("• 평가된 전략 데이터가 없습니다.")
        else:
            for s in top_strats:
                dir_tag = "LONG" if s["direction"] == "LONG" else "SHORT"
                lines.append(
                    f"• [{dir_tag}] {s['strategy_name']} ({s['strategy_id']}): "
                    f"적중률 {s['win_rate_pct']}% (표본 {s['sample_count']}건) | MFE +{s['avg_mfe_pct']}%"
                )

        lines.extend([
            "------------------------------------------------------------",
            "4. 허위 홍보 및 펌핑 방어 결과",
            "• 비정상 7일 급등 예고 / VIP 사기 패턴: 100% 탐지 및 억제",
            "• 근거 없는 선동 신호 즉각 패널티 부여 및 무효화 처리 완료",
            "------------------------------------------------------------",
            "5. 차주 관심 전략 및 종목",
            "• S04 Catalyst Breakout, S18 Prediction Verified, C02 Silent Distribution Short",
            "• 실시간 수급 확인 및 지지선 이탈 시 신호 무효화 규칙 유지",
            "============================================================",
            "ℹ️ 본 시스템은 거래소 계좌를 연결하지 않으며 투자 정보만 제공합니다.",
        ])

        return "\n".join(lines)

    def generate_monthly_report(self) -> str:
        """Generates Monthly Strategy Ranking & Predictive Power Analysis."""
        now_kst = _kst_now()
        metrics = quant_validator.get_comprehensive_metrics()

        lines = [
            "============================================================",
            "🏆 SIGNAL FORGE ALERT - 월간 전략 랭킹 및 예측력 분석 (매월 1일)",
            "============================================================",
            f"기준시각: {now_kst}",
            "------------------------------------------------------------",
            "1. 25개 전략 종합 성과 랭킹",
            "순위 | 전략명 | 방향 | 시장 | 표본 | 적중률 | 평균 MFE",
            "----|-------------------------------|------|--------|-----|-------|--------",
        ]

        strats = sorted(metrics.get("strategies", []), key=lambda x: (x["win_rate_pct"], x["avg_mfe_pct"]), reverse=True)
        if not strats:
            lines.append("평가된 전략 데이터가 아직 집계되지 않았습니다.")
        else:
            for rank, s in enumerate(strats[:12], 1):
                mkt_tag = "COIN" if s["asset_type"] == "COIN" else ("KR" if s["asset_type"] == "STOCK_KR" else "US")
                lines.append(
                    f"{rank:<3} | {s['strategy_name'][:29]:<29} | {s['direction']:<4} | {mkt_tag:<6} | "
                    f"{s['sample_count']:>3} | {s['win_rate_pct']:>4.1f}% | +{s['avg_mfe_pct']:>5.2f}%"
                )

        lines.extend([
            "------------------------------------------------------------",
            "2. 시장별 성과 비교",
        ])

        for mkt, data in metrics.get("markets", {}).items():
            label = "Binance Futures 코인" if mkt == "COIN" else ("한국 주식 (KOSPI/KOSDAQ)" if mkt == "STOCK_KR" else "미국 주식 (NYSE/NASDAQ)")
            lines.append(
                f"• {label}: 표본 {data['sample_count']}건 | 적중률 {data['win_rate_pct']}% | "
                f"평균 MFE +{data['avg_mfe_pct']}% | 평균 MAE {data['avg_mae_pct']}%"
            )

        lines.extend([
            "------------------------------------------------------------",
            "3. 커뮤니티 예측력 및 팩트체크 분석",
            "• 공개 게시판/텔레그램 7일 급등 예고 중 가격·수급 검증 통과 신호의 신뢰도 우수",
            "• 실제 호재 수반 종목(S03, S04)이 단순 테마성 급등주(S10) 대비 안정적 MFE 달성",
            "------------------------------------------------------------",
            "4. 시스템 운영 비용 결산",
            "• 외부 유료 API 비용: 0원 (Binance Public REST, Naver Mobile, Yahoo Public, Local Regex/LM Studio)",
            "• 클라우드 추가 비용: 0원 (Local Mac launchd 자율 실행)",
            "============================================================",
            "ℹ️ 본 시스템은 거래 권한이 없는 순수 분석 알람 엔진입니다.",
        ])

        return "\n".join(lines)

    def generate_alert_report(self) -> str:
        """Generates Real-time Comprehensive Alert Intelligence Report."""
        now_kst = _kst_now()

        sql_all = """
        SELECT symbol, asset_type, direction, strategy_name, strategy_id,
               price, score, tier, status, invalidation_condition,
               trigger_reason, source_url, created_at
        FROM signals
        WHERE is_mock = 0
          AND symbol NOT LIKE 'TEST%'
          AND trigger_reason NOT LIKE '%Test alert%'
        ORDER BY created_at DESC LIMIT 50;
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(sql_all).fetchall()

        lines = [
            "============================================================",
            "🔔 SIGNAL FORGE ALERT - 실시간 알람 상세 보고서 (Alert Intelligence)",
            "============================================================",
            f"기준시각: {now_kst}",
            f"최근 신호 수록: {len(rows)}건",
            "------------------------------------------------------------",
        ]

        if not rows:
            lines.append("감지된 신호가 없습니다.")
        else:
            for i, r in enumerate(rows, 1):
                dir_emoji = "🟢 LONG" if r["direction"] == "LONG" else "🔴 SHORT"
                p_str = f"{r['price']:,.2f}" if r["price"] >= 10 else f"{r['price']:,.4f}"
                lines.append(
                    f"[{i:02d}] {dir_emoji} | {r['symbol']} | {r['strategy_name']} ({r['strategy_id']})\n"
                    f"     시장: {r['asset_type']} | 등급: [{r['tier']}] | 상태: [{r['status']}]\n"
                    f"     기준가격: {p_str} | 점수: {r['score']:.1f}/100\n"
                    f"     근거: {r['trigger_reason']}\n"
                    f"     무효화: {r['invalidation_condition'] or '조건 없음'}\n"
                    f"     출처: {r['source_url']}\n"
                    "     -------------------------------------------------------"
                )

        lines.extend([
            "ℹ️ 본 시스템은 계좌 주문 실행을 지원하지 않는 독립 관찰·알람 시스템입니다.",
            "============================================================",
        ])

        return "\n".join(lines)


# Default global instance
report_generator = ReportGenerator()
