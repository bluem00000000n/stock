#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/stage2_revival.py
미국 중소형 성장주 2차 파동 부활 전략 (US Mid/Small Stage 2 Revival)
- 철학: "꿈으로 오른 1차 파동(내러티브)이 꺼진 후, 실적(숫자)이 뒷받침되어 2단계 상승(Stage 2)으로 전환되는 종목만 매수"
- 파이프라인:
  1) 매월 1일 (Monthly): 1차 급등 ➔ -40~-70% 가격/기간 조정 ➔ 실적 가시성(수주/흑자전환) 후보군 15선 선별
  2) 매일 장전/장중 (Daily): 50일선 안착 & VCP 매물소화 후 피벗 저항 돌파 실시간 감시 및 시그널 산출
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_us_price

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "strategies_data" / "stock-stage2-revival"

# ==============================================================================
# 🇺🇸 미국 중소형 성장주 2차 파동 유니버스 (월간 스크리닝 대상 풀)
# ==============================================================================
MONTHLY_STAGE2_UNIVERSE = [
    {
        "ticker": "ASTS",
        "name": "AST SpaceMobile",
        "sector": "우주위성 / 다이렉트 셀룰러",
        "cap_size": "중형주",
        "first_wave_peak": 39.0,
        "trough_price": 2.0,
        "pivot": 28.50,
        "stop": 26.65,
        "stage": "Stage 2 상승 가속",
        "catalyst": "AT&T 및 버라이즌 독점 상용 위성 계약 체결, 상용 위성 5기 궤도 안착, 수주 잔고 급증",
        "narrative": "1차 기대감 폭락($2) 후 상용화 실적으로 전고점 뚫고 10배 폭등한 대표적 2차 파동 모델"
    },
    {
        "ticker": "RKLB",
        "name": "Rocket Lab",
        "sector": "우주발사체 & 위성 제조",
        "cap_size": "중형주",
        "first_wave_peak": 21.0,
        "trough_price": 3.6,
        "pivot": 14.50,
        "stop": 13.50,
        "stage": "Stage 2 초입 돌파",
        "catalyst": "수주 잔고(Backlog) 10억 달러 돌파, 미 우주군 5억 달러 수주, 뉴트론 중대형 로켓 2025 상용화",
        "narrative": "1차 스팩 상장 거품 붕괴 후 흑자 전환 초입 및 일렉트론 발사 빈도 신기록으로 펀더멘털 증명"
    },
    {
        "ticker": "POWL",
        "name": "Powell Industries",
        "sector": "AI 전력망 / 변전소 인프라",
        "cap_size": "중소형주",
        "first_wave_peak": 120.0,
        "trough_price": 45.0,
        "pivot": 154.0,
        "stop": 142.0,
        "stage": "Stage 2 대세 상승",
        "catalyst": "AI 데이터센터 전력 배전 장비 수주잔고 YoY +140% 폭발, 영업이익률 20% 돌파 텐배거 달성",
        "narrative": "경기민감 전력 장비주에서 AI 데이터센터 필수 전력망 독점주로 재평가되며 2차 대세 파동 질주"
    },
    {
        "ticker": "MOD",
        "name": "Modine Manufacturing",
        "sector": "AI 데이터센터 액체냉각 열관리",
        "cap_size": "중소형주",
        "first_wave_peak": 80.0,
        "trough_price": 25.0,
        "pivot": 123.34,
        "stop": 118.0,
        "stage": "Stage 2 대세 상승",
        "catalyst": "기존 자동차 라디에이터에서 하이퍼스케일 AI 데이터센터 액체냉각(Liquid Cooling) 고성장 흑자",
        "narrative": "환멸의 골짜기를 거쳐 AI 열관리 턴어라운드 숫자로 52주 신고가를 갈아치우는 이상적 모델"
    },
    {
        "ticker": "CRDO",
        "name": "Credo Technology",
        "sector": "고속 네트워킹 AEC 케이블",
        "cap_size": "중형주",
        "first_wave_peak": 28.0,
        "trough_price": 8.0,
        "pivot": 44.50,
        "stop": 41.50,
        "stage": "Stage 2 2차 돌파",
        "catalyst": "빅테크 AI 클러스터용 800G/1.6T 광학 케이블 대체(AEC) 독점, 분기 매출 YoY +70% 폭발",
        "narrative": "고객사 주문 지연으로 $8까지 폭락했던 1차 거품 붕괴 후, 마이크로소프트/아마존 양산 채택으로 부활"
    },
    {
        "ticker": "AEHR",
        "name": "Aehr Test Systems",
        "sector": "SiC/GaN 반도체 웨이퍼 테스트",
        "cap_size": "소형주",
        "first_wave_peak": 54.0,
        "trough_price": 9.5,
        "pivot": 16.50,
        "stop": 15.00,
        "stage": "Stage 1 바닥 다지기",
        "catalyst": "전기차 캐즘으로 폭락 후 AI 데이터센터 고전압 전력 반도체 및 실리콘 포토닉스 테스트 신규 수주",
        "narrative": "글쓴이가 언급한 오리지널 모델: 1차 거품 후 폭락, 차세대 AI 광학 테스트 실적으로 바닥 탈출 모색"
    },
    {
        "ticker": "OKLO",
        "name": "Oklo",
        "sector": "소형모듈원자로 (SMR)",
        "cap_size": "중소형주",
        "first_wave_peak": 26.0,
        "trough_price": 5.3,
        "pivot": 22.00,
        "stop": 19.50,
        "stage": "1차 파동 고점 후 냉각 관망",
        "catalyst": "샘 알트만 투자, 데이터센터 전력 공급 PPA 계약 논의 중이나 NRC 인허가 및 상용화까지 시간 소요",
        "narrative": "글쓴이가 경고한 대표적 1차 내러티브 급등주: 현재는 관망, 추후 상용로 인허가 및 실적 가시화 시 재진입"
    },
    {
        "ticker": "TEM",
        "name": "Tempus AI",
        "sector": "AI 정밀의료 & 암 유전체",
        "cap_size": "중형주",
        "first_wave_peak": 75.0,
        "trough_price": 26.0,
        "pivot": 58.00,
        "stop": 53.50,
        "stage": "Stage 2 초입 형성",
        "catalyst": "소프트뱅크 파트너십 및 제약사 대상 AI 암 유전체 분석 라이선스 매출 분기별 가속화",
        "narrative": "상장 직후 급등락 1차 소화 후 대형 빅파마 계약 실적이 붙으며 바닥 컵앤핸들 완성"
    },
    {
        "ticker": "ALAB",
        "name": "Astera Labs",
        "sector": "PCIe 6.0 / CXL 반도체 연결성",
        "cap_size": "중형주",
        "first_wave_peak": 95.0,
        "trough_price": 36.0,
        "pivot": 88.50,
        "stop": 82.00,
        "stage": "Stage 2 돌파 안착",
        "catalyst": "엔비디아 블랙웰용 PCIe 6.0 리타이머 칩 독점 공급, 분기 매출 서프라이즈",
        "narrative": "공모 후 -60% 폭락으로 환멸의 골짜기 통과 후 엔비디아 실적 연동으로 52주 신고가 탈환"
    },
    {
        "ticker": "IONQ",
        "name": "IonQ",
        "sector": "이온트랩 양자컴퓨팅",
        "cap_size": "중소형주",
        "first_wave_peak": 35.0,
        "trough_price": 3.0,
        "pivot": 18.00,
        "stop": 16.20,
        "stage": "Stage 1 탈출 ➔ 2단계 타진",
        "catalyst": "미 공군 연구소(AFRL) 5,450만 달러 대형 계약 수주 및 아마존/애저 클라우드 예약 급증",
        "narrative": "스팩 상장 거품 붕괴 후 정부 기관 및 국방 실적으로 펀더멘털을 차곡차곡 쌓아가는 중"
    }
]


def update_monthly_pool() -> List[Dict[str, Any]]:
    """매월 1일 실행: 유니버스 후보군 펀더멘털 및 기술적 스크리닝 데이터 갱신"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pool_file = DATA_DIR / "monthly_pool.json"

    updated_pool = []
    for item in MONTHLY_STAGE2_UNIVERSE:
        p_info = fetch_us_price(item["ticker"])
        cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
        entry = dict(item)
        entry["current_price"] = cur_price
        entry["discount_from_peak_pct"] = round(((cur_price - item["first_wave_peak"]) / item["first_wave_peak"]) * 100, 1)
        entry["gain_from_trough_pct"] = round(((cur_price - item["trough_price"]) / item["trough_price"]) * 100, 1)
        entry["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_pool.append(entry)

    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump(updated_pool, f, indent=2, ensure_ascii=False)

    return updated_pool


def run_daily_surveillance() -> List[Dict[str, Any]]:
    """매일 장전/장중 실행: 2단계 상승 전환(Stage 2 Breakout) 타점 감시 및 시그널 산출"""
    signals = []
    pool = update_monthly_pool()

    for item in pool:
        ticker = item["ticker"]
        cur_price = float(item["current_price"])
        pivot_val = float(item["pivot"])
        stop_val = float(item["stop"])

        # 1. 1차 내러티브 급등 후 아직 냉각기/하락 채널(OKLO 등)에 있는 종목은 명확히 대기
        if "관망" in item["stage"] or "냉각" in item["stage"]:
            continue

        # 2. 피벗 돌파 임박 및 2단계 안착 조건 판별 (피벗 대비 -3% 이내 ~ +8% 이내 돌파권)
        distance_to_pivot = (cur_price - pivot_val) / pivot_val
        is_breakout_ready = -0.05 <= distance_to_pivot <= 0.12

        if is_breakout_ready and cur_price > stop_val:
            tp1 = round(pivot_val * 1.20, 2)  # 1차 +20%
            tp2 = round(pivot_val * 1.45, 2)  # 2차 +45% (텐배거 파동 초입)
            rr = round((tp1 - cur_price) / max(0.1, (cur_price - stop_val)), 2)

            score = 92.0
            if "2단계" in item["stage"] or "Stage 2" in item["stage"]:
                score += 5.0
            if distance_to_pivot >= 0:  # 이미 피벗 돌파 완료
                score += 2.0

            signals.append({
                "project_id": "stock-stage2-revival",
                "strategy_name": "미국 중소형 2차 파동 부활 (Stage 2 Revival)",
                "market": "US",
                "cap_size": item["cap_size"],
                "ticker": ticker,
                "name": item["name"],
                "signal_type": "BUY" if distance_to_pivot >= -0.01 else "WATCH",
                "price": cur_price,
                "target_price": tp1,
                "target_price_2": tp2,
                "stop_loss_price": stop_val,
                "risk_reward_ratio": rr,
                "score": score,
                "sector": item["sector"],
                "theme": f"[2차파동] {item['catalyst']}",
                "pattern": f"{item['stage']} (피벗 ${pivot_val:.2f})",
                "action_plan": f"피벗(${pivot_val:.2f}) 돌파 시 진입. 손절 ${stop_val:.2f} 엄수. {item['narrative'][:35]}...",
                "raw_data": {
                    "first_wave_peak": item["first_wave_peak"],
                    "trough_price": item["trough_price"],
                    "catalyst": item["catalyst"],
                    "stage": item["stage"]
                }
            })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals


def run_analysis() -> List[Dict[str, Any]]:
    """중앙 슈퍼바이저 파이프라인 연동 인터페이스"""
    return run_daily_surveillance()


def build_tuesday_review_block() -> str:
    """화요일 오후 정기 점검 리포트 블록 생성 (매수 종목 발생 시 상세 안내)"""
    signals = run_daily_surveillance()
    buy_signals = [s for s in signals if s.get("signal_type") == "BUY"]

    lines = []
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🚀 <b>[화요일 주간 특별 점검] 🇺🇸 미국 중소형 2차 파동 부활 (Stage 2 Revival)</b>")
    lines.append("💡 <i>원칙: 1차 거품 붕괴 후 실적(수주잔고/흑자전환)으로 2단계 상승 전환된 종목 저격</i>")

    if buy_signals:
        lines.append(f"🔥 <b>[금주 신규 매수 유효 타점: 총 {len(buy_signals)}종목 포착]</b>")
        for idx, s in enumerate(buy_signals, 1):
            cur_p = s["price"]
            tgt_1 = s["target_price"]
            tgt_2 = s["target_price_2"]
            stop_p = s["stop_loss_price"]
            pivot_base = round(tgt_1 / 1.20, 2)
            raw = s.get("raw_data", {})
            lines.append(f" {idx}. 🟢 <b>[{s['cap_size']}] {s['name']} ({s['ticker']})</b> | <b>[매수 유효 타점]</b>")
            lines.append(f"    └ 현재가: ${cur_p:.2f} (피벗: ${pivot_base:.2f}) | 🎯 1차: ${tgt_1:.2f} | 🎯 2차: ${tgt_2:.2f} | 🛑 손절: ${stop_p:.2f}")
            lines.append(f"    └ <i>실적 촉매:</i> {raw.get('catalyst', s['theme'])}")
            lines.append(f"    └ <i>국면 진단:</i> {raw.get('stage', s['pattern'])}")
    else:
        lines.append("📋 <b>[금주 점검 결과]</b> 현재 2단계 피벗 돌파 조건을 만족한 신규 매수 종목 없음")
        lines.append("• 1차 거품주(OKLO 등) 및 바닥 다지기 진행주(AEHR 등)는 계속 관망 유지 (기회비용 보존)")

    return "\n".join(lines)


def run_tuesday_weekly_review(send_telegram: bool = True) -> bool:
    """매주 화요일 오후 독립 실행 함수 (텔레그램 즉시 발송 지원)"""
    from core.telegram import send_message
    today_str = datetime.now().strftime("%Y년 %m월 %d일 (화)")
    block = build_tuesday_review_block()
    msg = f"📅 <b>[STOCK SUPERVISOR] {today_str} 오후 정기 점검</b>{block}"

    print(msg)
    if send_telegram:
        return send_message(msg)
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--tuesday":
        run_tuesday_weekly_review(send_telegram=True)
    else:
        print("=" * 80)
        print("🚀 [미국 중소형 성장주 2차 파동 부활 전략] 일간 감시 실행")
        print("=" * 80)
        res = run_daily_surveillance()
        print(f"✅ 총 {len(res)}개 2단계 전환 유효 종목 포착\n")
        for s in res:
            print(f"• [{s['signal_type']}] {s['name']} ({s['ticker']}) - 현재가: ${s['price']} | 피벗: ${s['target_price']}")
            print(f"  └ 국면: {s['pattern']} | 손익비: {s['risk_reward_ratio']}")
            print(f"  └ 실적 촉매제: {s['theme']}")
            print(f"  └ 행동 강령: {s['action_plan']}\n")
        print(build_tuesday_review_block())
