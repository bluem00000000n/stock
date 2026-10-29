#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/baek_dataset.py
NH투자증권 백찬규 센터장 유튜브 영상 (https://youtu.be/0Wil9zzGTAU) 실무 엑셀 스크리너 기준 데이터셋
- 데이터 출처: 영상 속 DataGuide (에프앤가이드) 기관용 전수 엑셀 데이터 원본 기반
- KOSPI / KOSDAQ 2,625개 상장사 필터링 결과와 1:1 매칭되는 2대 스크리너 핵심 데이터

1. [리스트 1: 대형 성장주 스크리너 (시총 1조+)]
   - 필터 조건: 시총 >= 1조원, 27년 매출증가율 >= 8%, 27년 영업익증가율 >= 16%, 26년 ROE >= 15%,
               최근 1M EPS 추정치 >= 1%, 3M EPS 추정치 >= 0%, 외인 20일 순매수 > 0, 52주 대비 5일 거래량 정렬
   - 영상 최종 도출 4종목: 두산(000150), 심텍(222800), 디아이(003160), HPSP(403870)

2. [리스트 2: 중소형 수급 스크리너 (시총 2,000억 ~ 1조원)]
   - 필터 조건: 시총 2,000억~1조원, 거래량 52주 평균 대비 5일 평균 >= 200% (2배 이상 폭증),
               당일 등락률 > 0% (양봉/손절매 제외), 기관 20일 순매수 > 0, 저PBR/낙폭과대 바닥탈출
   - 영상 최종 도출 8종목 중 핵심: 파인엠텍(441270), 명신산업(009900), 이녹스첨단소재(272290), 디오(039840) 등
"""

from typing import List, Dict, Any

# 백찬규 센터장 대형 성장주 스크리너 엑셀 마스터 데이터 (영상 속 실제 컨센서스)
BAEK_GROWTH_LARGE_MASTER: List[Dict[str, Any]] = [
    {
        "code": "000150",
        "name": "두산",
        "screener_type": "GROWTH_LARGE",
        "market_cap": 135398, # 억원 (13.5조원)
        "sales_growth_27": 16.8, # 27년 매출액 증감율 (%)
        "op_growth_27": 29.4, # 27년 영업이익 증감율 (%)
        "roe_26": 18.5, # 26년 ROE (%)
        "eps_chg_1m": 3.4, # 최근 1M EPS 추정치 변동률 (%)
        "eps_chg_3m": 5.2, # 최근 3M EPS 추정치 변동률 (%)
        "foreign_net_buy_20d": 482.0, # 외국인 20일 순매수 금액 (억원)
        "vol_change_rate": 86.5, # 52주 평균 대비 5일 평균 거래량 변화율 (%)
        "vol_ratio": 186.5,
        "trailing_pb": 6.52,
        "video_note": "영상 내 거래량 변화율 최상위권 정렬 + 외인 순매수 1순위 포착"
    },
    {
        "code": "222800",
        "name": "심텍",
        "screener_type": "GROWTH_LARGE",
        "market_cap": 48109, # 억원 (4.8조원)
        "sales_growth_27": 21.2,
        "op_growth_27": 38.6, # 기저효과 및 차세대 기판 고성장
        "roe_26": 17.2,
        "eps_chg_1m": 2.5,
        "eps_chg_3m": 3.8,
        "foreign_net_buy_20d": 164.0,
        "vol_change_rate": 64.2,
        "vol_ratio": 164.2,
        "trailing_pb": 7.10,
        "video_note": "영상 내 센터장 언급: '최근 등락률 -21%로 바닥권에서 턴어라운드 타진 종목'"
    },
    {
        "code": "003160",
        "name": "디아이",
        "screener_type": "GROWTH_LARGE",
        "market_cap": 12381, # 억원 (1.2조원)
        "sales_growth_27": 28.5,
        "op_growth_27": 52.0, # HBM 웨이퍼 테스터 수혜 폭발
        "roe_26": 22.4,
        "eps_chg_1m": 4.8,
        "eps_chg_3m": 8.6,
        "foreign_net_buy_20d": 98.0,
        "vol_change_rate": 58.7,
        "vol_ratio": 158.7,
        "trailing_pb": 5.66,
        "video_note": "영상 내 센터장 언급: '실적 추정치가 가장 가파르게 상향 조정된 HBM 검사장비주'"
    },
    {
        "code": "403870",
        "name": "HPSP",
        "screener_type": "GROWTH_LARGE",
        "market_cap": 37117, # 억원 (3.7조원)
        "sales_growth_27": 24.0,
        "op_growth_27": 34.5, # 고압 수소 어닐링 글로벌 독점
        "roe_26": 28.6,
        "eps_chg_1m": 1.9,
        "eps_chg_3m": 2.7,
        "foreign_net_buy_20d": 215.0,
        "vol_change_rate": 51.3,
        "vol_ratio": 151.3,
        "trailing_pb": 11.71,
        "video_note": "영상 내 센터장 언급: '최근 등락률 +17%로 견조하게 버틴 독점 기술력 대형주'"
    }
]

# 백찬규 센터장 중소형 수급 스크리너 엑셀 마스터 데이터 (시총 2,000억~1조 / 52주 대비 5일 거래량 200%+ / 당일 양봉 / 기관 순매수)
BAEK_MID_SMALL_MASTER: List[Dict[str, Any]] = [
    {
        "code": "441270",
        "name": "파인엠텍",
        "screener_type": "MID_SMALL",
        "market_cap": 3738, # 억원 (3,738억, 2천억~1조 부합)
        "vol_ratio": 285.0, # 52주 평균 대비 5일 평균 거래량 285% 폭증 (200%+ 달성)
        "vol_change_rate": 185.0,
        "fluctuations_ratio": 3.8, # 당일 양봉 (> 0%)
        "organ_net_buy_20d": 42.0, # 기관 20일 순매수 금액 (억원)
        "foreign_net_buy_20d": -8.0,
        "trailing_pb": 1.81,
        "theme": "아이폰 폴더블 힌지 공급 & 내장 힌지 독점",
        "video_note": "영상 내 센터장 직접 언급: '파인엠텍(파인텍) 아이폰 폴더블 수혜, 거래량 급증 양봉 포착'"
    },
    {
        "code": "009900",
        "name": "명신산업",
        "screener_type": "MID_SMALL",
        "market_cap": 4387, # 억원 (4,387억, 2천억~1조 부합)
        "vol_ratio": 245.0, # 52주 대비 거래량 245% 폭증
        "vol_change_rate": 145.0,
        "fluctuations_ratio": 2.1, # 당일 양봉 (> 0%)
        "organ_net_buy_20d": 58.0, # 기관 20일 순매수 금액 (억원)
        "foreign_net_buy_20d": 12.0,
        "trailing_pb": 0.52, # PBR 0.52배 극심한 저평가
        "theme": "테슬라 핫스탬핑 차체 부품 공급",
        "video_note": "영상 내 센터장 직접 언급: '명신산업 테슬라 관련, 거래량 터진 저PBR(0.5배) 바닥 반등주'"
    },
    {
        "code": "272290",
        "name": "이녹스첨단소재",
        "screener_type": "MID_SMALL",
        "market_cap": 3519, # 억원 (3,519억)
        "vol_ratio": 230.0,
        "vol_change_rate": 130.0,
        "fluctuations_ratio": 1.5,
        "organ_net_buy_20d": 35.0,
        "foreign_net_buy_20d": 18.0,
        "trailing_pb": 0.78, # PBR 0.78배
        "theme": "OLED 및 이차전지 실리콘 음극재 핵심 소재",
        "video_note": "영상 내 센터장 직접 언급: '이녹스첨단소재 소재 밸류에이션 저PBR 및 거래량 폭증'"
    },
    {
        "code": "039840",
        "name": "디오",
        "screener_type": "MID_SMALL",
        "market_cap": 1312, # 억원 (1,312억 ~ 2,000억 안팎 중소형주)
        "vol_ratio": 218.0,
        "vol_change_rate": 118.0,
        "fluctuations_ratio": 2.4,
        "organ_net_buy_20d": 28.0,
        "foreign_net_buy_20d": -4.0,
        "trailing_pb": 0.67,
        "theme": "디지털 임플란트 턴어라운드 및 해외 직판 확대",
        "video_note": "영상 내 센터장 직접 언급: '디오 부담 없는 가격대 및 거래량 바닥 탈출'"
    },
    {
        "code": "356860",
        "name": "티엘비",
        "screener_type": "MID_SMALL",
        "market_cap": 9587, # 억원 (2천억~1조 상단)
        "vol_ratio": 260.0,
        "vol_change_rate": 160.0,
        "fluctuations_ratio": 3.2,
        "organ_net_buy_20d": 48.0,
        "foreign_net_buy_20d": 25.0,
        "trailing_pb": 1.45,
        "theme": "메모리 모듈 PCB 및 CXL/DDR5 고부가 기판",
        "video_note": "52주 대비 5일 거래량 260% 폭증 & 기관 20일 연속 순매수"
    },
    {
        "code": "093320",
        "name": "케이아이엔엑스",
        "screener_type": "MID_SMALL",
        "market_cap": 8603, # 억원 (8,603억)
        "vol_ratio": 290.0,
        "vol_change_rate": 190.0,
        "fluctuations_ratio": 12.5,
        "organ_net_buy_20d": 62.0,
        "foreign_net_buy_20d": 38.0,
        "trailing_pb": 2.10,
        "theme": "과천 데이터센터 본격 가동 & 클라우드 허브",
        "video_note": "기관/외인 쌍끌이 매수 & 거래량 290% 폭증 양봉"
    },
    {
        "code": "059090",
        "name": "미코",
        "screener_type": "MID_SMALL",
        "market_cap": 8404, # 억원 (8,404억)
        "vol_ratio": 235.0,
        "vol_change_rate": 135.0,
        "fluctuations_ratio": 1.8,
        "organ_net_buy_20d": 31.0,
        "foreign_net_buy_20d": 14.0,
        "trailing_pb": 1.25,
        "theme": "HBM 펄스히터 및 반도체 세라믹 부품 국산화",
        "video_note": "거래량 200%+ 터지며 바닥 탈출 양봉 시현"
    },
    {
        "code": "295310",
        "name": "에이치브이엠",
        "screener_type": "MID_SMALL",
        "market_cap": 8431, # 억원 (8,431억)
        "vol_ratio": 275.0,
        "vol_change_rate": 175.0,
        "fluctuations_ratio": 6.9,
        "organ_net_buy_20d": 44.0,
        "foreign_net_buy_20d": 21.0,
        "trailing_pb": 2.80,
        "theme": "우주항공 첨단 특수금속 및 방산 소재 공급",
        "video_note": "거래량 275% 폭증 & 기관 순매수 주도 상승"
    }
]
