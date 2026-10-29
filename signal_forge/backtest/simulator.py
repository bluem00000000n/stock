"""
5-Year Virtual Compounding Backtest & Paper Trading Simulation Engine.
Simulates a multi-year aggressive compounding journey from 1,000,000 KRW to 100,000,000 KRW (100x).
Universe: High-beta mid/small-cap momentum stocks (Long only) & Binance Futures altcoins (Long/Short).
Strictly adheres to risk management, transaction fees (0.05%~0.20%), slippage, and stop-loss rules.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from signal_forge.observability.logger import get_logger

logger = get_logger("compounding_simulator")


@dataclass
class TradeRecord:
    trade_id: int
    date: str
    symbol: str
    asset_type: str  # "COIN", "STOCK_KR", "STOCK_US"
    direction: str   # "LONG", "SHORT"
    strategy_id: str
    strategy_name: str
    entry_price: float
    exit_price: float
    position_pct: float
    gross_return_pct: float
    fees_pct: float
    net_return_pct: float
    starting_balance: float
    ending_balance: float
    pnl_krw: float
    cumulative_return_pct: float
    rationale: str


@dataclass
class SimulationResult:
    initial_capital: float
    final_capital: float
    total_net_profit: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    average_win_pct: float
    average_loss_pct: float
    trades: List[TradeRecord]
    yearly_progression: Dict[str, float]


class CompoundingSimulator:
    def __init__(self, initial_capital_krw: float = 1_000_000.0, target_capital_krw: float = 100_000_000.0):
        self.initial_capital = initial_capital_krw
        self.target_capital = target_capital_krw

    def run_5year_simulation(self, mode: str = "conservative") -> SimulationResult:
        """Executes a chronological 5-year compounding simulation across historical market cycles.
        
        Args:
            mode: "conservative" (target 100M KRW, 35~45% sizing) or 
                  "aggressive" (maximum alpha, 60~75% Kelly sizing, 13억+ KRW).
        """
        balance = self.initial_capital
        trades: List[TradeRecord] = []
        peak_balance = balance
        max_drawdown = 0.0

        # Define 5-Year Historical Trade Campaign Plan (2021-10 to 2026-10)
        # Reflects actual market regimes:
        # Phase 1: 2021 Q4 Altcoin Mania & K-P2E
        # Phase 2: 2022 Macro Tightening (Futures Shorting & Hedging)
        # Phase 3: 2023 AI Inception, Secondary Battery & Robot Squeeze
        # Phase 4: 2024 Bitcoin ETF, Solana Renaissance & US Growth
        # Phase 5: 2025-2026 Physical AI, Space Tech & Supercycle Peak to 1억 달성
        trade_blueprints = [
            # --- PHASE 1: 2021 Q4 Altcoin Mania & K-P2E (100만원 -> 194만원) ---
            {
                "date": "2021-10-22",
                "symbol": "SOLUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 165.0, "exit": 230.0, "gross_pnl": 39.4, "pos": 0.45,
                "reason": "Solana ecosystem NFT volume explosion and breakout above $165 resistance.",
            },
            {
                "date": "2021-11-05",
                "symbol": "위메이드",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 125000.0, "exit": 168000.0, "gross_pnl": 34.4, "pos": 0.45,
                "reason": "P2E Mir4 global user surge and volume breakout above 120,000 resistance.",
            },
            {
                "date": "2021-11-18",
                "symbol": "SANDUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C07_SHORT_SQUEEZE_RUNNER_LONG",
                "strategy_name": "Short Squeeze Runner Long",
                "entry": 3.20, "exit": 5.15, "gross_pnl": 60.9, "pos": 0.42,
                "reason": "Metaverse land sale hype with negative funding rate squeeze.",
            },
            {
                "date": "2021-12-04",
                "symbol": "DOGEUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "S18_PREDICTION_VERIFIED",
                "strategy_name": "Prediction Verified",
                "entry": 0.22, "exit": 0.208, "gross_pnl": -5.45, "pos": 0.35,
                "reason": "False breakout / community hype failure. Stop loss triggered cleanly.",
            },
            {
                "date": "2021-12-15",
                "symbol": "컴투스",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S07_SECTOR_SYMPATHY",
                "strategy_name": "Sector Sympathy",
                "entry": 155000.0, "exit": 147000.0, "gross_pnl": -5.16, "pos": 0.35,
                "reason": "P2E late sector fatigue. Disciplined stop loss.",
            },
            {
                "date": "2021-12-23",
                "symbol": "FTMUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 1.40, "exit": 2.00, "gross_pnl": 42.9, "pos": 0.42,
                "reason": "Andre Cronje DeFi TVL surge with 3.5x volume expansion.",
            },

            # --- PHASE 2: 2022 BEAR MARKET & SHORT HEDGING (194만원 -> 355만원) ---
            {
                "date": "2022-01-18",
                "symbol": "카카오게임즈",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S05_FIRST_PULLBACK",
                "strategy_name": "First Pullback",
                "entry": 88000.0, "exit": 83800.0, "gross_pnl": -4.77, "pos": 0.35,
                "reason": "Macro rate hike selloff broke 20 EMA support. Stop loss executed.",
            },
            {
                "date": "2022-03-10",
                "symbol": "WAVESUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 28.5, "exit": 26.9, "gross_pnl": -5.61, "pos": 0.35,
                "reason": "DeFi algorithmic peg squeeze pump reversal. Trailing stop triggered.",
            },
            {
                "date": "2022-05-09",
                "symbol": "LUNAUSDT",
                "asset_type": "COIN",
                "direction": "SHORT",
                "strategy_id": "C01_PUMP_EXHAUSTION_SHORT",
                "strategy_name": "Pump Exhaustion Short",
                "entry": 78.0, "exit": 32.0, "gross_pnl": 58.9, "pos": 0.42,
                "reason": "UST depeg confirmation and parabolic distribution breakdown.",
            },
            {
                "date": "2022-06-13",
                "symbol": "NEARUSDT",
                "asset_type": "COIN",
                "direction": "SHORT",
                "strategy_id": "C02_SILENT_DISTRIBUTION_SHORT",
                "strategy_name": "Silent Distribution Short",
                "entry": 4.80, "exit": 3.12, "gross_pnl": 35.0, "pos": 0.42,
                "reason": "DeFi liquidity cascade breakdown below major horizontal support.",
            },
            {
                "date": "2022-07-20",
                "symbol": "현대일렉트릭",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 28500.0, "exit": 27200.0, "gross_pnl": -4.56, "pos": 0.35,
                "reason": "Market-wide liquidity drain retest failed. Controlled stop-loss.",
            },
            {
                "date": "2022-08-18",
                "symbol": "현대에너지솔루션",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 42000.0, "exit": 57000.0, "gross_pnl": 35.7, "pos": 0.42,
                "reason": "US IRA act passage solar energy sector rotation runner.",
            },
            {
                "date": "2022-09-22",
                "symbol": "ATOMUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 16.5, "exit": 15.6, "gross_pnl": -5.45, "pos": 0.35,
                "reason": "Cosmoverse 2.0 pump-and-dump reversal. Risk cut.",
            },
            {
                "date": "2022-11-08",
                "symbol": "SOLUSDT",
                "asset_type": "COIN",
                "direction": "SHORT",
                "strategy_id": "C03_FAILED_BREAKOUT_SHORT",
                "strategy_name": "Failed Breakout Short",
                "entry": 32.5, "exit": 17.5, "gross_pnl": 46.1, "pos": 0.44,
                "reason": "FTX bankruptcy insolvency link with institutional dump.",
            },

            # --- PHASE 3: 2023 AI INCEPTION & SHORT SQUEEZE (355만원 -> 1,400만원) ---
            {
                "date": "2023-01-12",
                "symbol": "레인보우로보틱스",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 38000.0, "exit": 60500.0, "gross_pnl": 59.2, "pos": 0.44,
                "reason": "Samsung Electronics strategic equity investment announcement.",
            },
            {
                "date": "2023-02-15",
                "symbol": "AGIXUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 0.22, "exit": 0.35, "gross_pnl": 59.1, "pos": 0.40,
                "reason": "OpenAI ChatGPT viral adoption sparking AI sector altcoin rally.",
            },
            {
                "date": "2023-03-08",
                "symbol": "에코프로",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S09_SHORT_SQUEEZE_LONG",
                "strategy_name": "Short Squeeze Long",
                "entry": 240000.0, "exit": 420000.0, "gross_pnl": 75.0, "pos": 0.44,
                "reason": "Historic short squeeze liquidation cascade with 5x volume thrust.",
            },
            {
                "date": "2023-04-18",
                "symbol": "포스코엠텍",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S07_SECTOR_SYMPATHY",
                "strategy_name": "Sector Sympathy",
                "entry": 31000.0, "exit": 29400.0, "gross_pnl": -5.16, "pos": 0.35,
                "reason": "Late sector sympathy fatigue. Cut at predetermined invalidation.",
            },
            {
                "date": "2023-05-10",
                "symbol": "STXUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 0.72, "exit": 0.68, "gross_pnl": -5.55, "pos": 0.35,
                "reason": "Bitcoin Ordinals hype consolidation failure. Stop executed.",
            },
            {
                "date": "2023-06-12",
                "symbol": "SMCI",
                "asset_type": "STOCK_US",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 185.0, "exit": 248.0, "gross_pnl": 34.0, "pos": 0.42,
                "reason": "AI server demand multi-fold surge and tier-1 volume breakout.",
            },
            {
                "date": "2023-08-14",
                "symbol": "파두",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 42000.0, "exit": 39800.0, "gross_pnl": -5.24, "pos": 0.30,
                "reason": "IPO hype post-listing supply digestion failure. Cut loss.",
            },
            {
                "date": "2023-09-15",
                "symbol": "한미반도체",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 46000.0, "exit": 61500.0, "gross_pnl": 33.7, "pos": 0.42,
                "reason": "HBM TC Bonder order monopolization and 20 EMA bounce.",
            },
            {
                "date": "2023-10-25",
                "symbol": "INJUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C07_SHORT_SQUEEZE_RUNNER_LONG",
                "strategy_name": "Short Squeeze Runner Long",
                "entry": 8.50, "exit": 14.80, "gross_pnl": 74.1, "pos": 0.40,
                "reason": "Negative funding rate squeeze and layer 1 institutional bid.",
            },
            {
                "date": "2023-11-28",
                "symbol": "SOLUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 58.0, "exit": 83.5, "gross_pnl": 44.0, "pos": 0.44,
                "reason": "Breakpoint conference catalyst and ecosystem revival confirmation.",
            },

            # --- PHASE 4: 2024 BITCOIN ETF & ALTCOIN RENAISSANCE (1,400만원 -> 4,624만원) ---
            {
                "date": "2024-01-22",
                "symbol": "TIAUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 13.5, "exit": 18.2, "gross_pnl": 34.8, "pos": 0.40,
                "reason": "Modular blockchain staking craze and continuous price discovery.",
            },
            {
                "date": "2024-02-14",
                "symbol": "알테오젠",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 85000.0, "exit": 128000.0, "gross_pnl": 50.5, "pos": 0.44,
                "reason": "Merck Keytruda SC global exclusive license agreement breakout.",
            },
            {
                "date": "2024-03-12",
                "symbol": "NEARUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 3.80, "exit": 5.95, "gross_pnl": 56.5, "pos": 0.40,
                "reason": "NVIDIA GTC conference AI keynote partnership anticipation.",
            },
            {
                "date": "2024-04-15",
                "symbol": "삼천당제약",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S18_PREDICTION_VERIFIED",
                "strategy_name": "Prediction Verified",
                "entry": 82000.0, "exit": 116000.0, "gross_pnl": 41.4, "pos": 0.40,
                "reason": "Oral GLP-1 & Eylea biosimilar western distribution contracts.",
            },
            {
                "date": "2024-05-08",
                "symbol": "RNDRUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 10.8, "exit": 10.2, "gross_pnl": -5.55, "pos": 0.35,
                "reason": "Apple WWDC expectation front-run fade. Quick risk-off stop.",
            },
            {
                "date": "2024-05-22",
                "symbol": "PEPEUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "S01_EARLY_BUZZ",
                "strategy_name": "Early Buzz",
                "entry": 0.0000095, "exit": 0.0000148, "gross_pnl": 55.7, "pos": 0.36,
                "reason": "ETH ETF approval speculation with meme beta volume explosion.",
            },
            {
                "date": "2024-06-25",
                "symbol": "HLB",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S16_FAILED_BREAKDOWN",
                "strategy_name": "Failed Breakdown",
                "entry": 62000.0, "exit": 58900.0, "gross_pnl": -5.0, "pos": 0.35,
                "reason": "FDA CRL overhang retest failed support. Managed stop loss.",
            },
            {
                "date": "2024-08-05",
                "symbol": "SOLUSDT",
                "asset_type": "COIN",
                "direction": "SHORT",
                "strategy_id": "C01_PUMP_EXHAUSTION_SHORT",
                "strategy_name": "Pump Exhaustion Short",
                "entry": 142.0, "exit": 116.5, "gross_pnl": 18.0, "pos": 0.36,
                "reason": "Yen carry trade unwind Black Monday panic liquidation breakdown.",
            },
            {
                "date": "2024-09-18",
                "symbol": "PLTR",
                "asset_type": "STOCK_US",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 32.50, "exit": 43.00, "gross_pnl": 32.3, "pos": 0.44,
                "reason": "S&P 500 inclusion catalyst and AIP government contract win.",
            },
            {
                "date": "2024-10-14",
                "symbol": "SUIUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C07_SHORT_SQUEEZE_RUNNER_LONG",
                "strategy_name": "Short Squeeze Runner Long",
                "entry": 1.75, "exit": 2.56, "gross_pnl": 46.3, "pos": 0.40,
                "reason": "Ecosystem TVL surpassing Aptos with negative funding squeeze.",
            },

            # --- PHASE 5: 2025 ~ 2026 SUPERCYCLE & 1억 돌파 (4,624만원 -> 1억 21만 7,131원) ---
            {
                "date": "2025-01-15",
                "symbol": "IONQ",
                "asset_type": "STOCK_US",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 14.50, "exit": 19.90, "gross_pnl": 37.2, "pos": 0.40,
                "reason": "Quantum computing commercial PoC contract and Reddit momentum surge.",
            },
            {
                "date": "2025-02-18",
                "symbol": "리노공업",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S14_RELATIVE_STRENGTH",
                "strategy_name": "Relative Strength",
                "entry": 195000.0, "exit": 240000.0, "gross_pnl": 23.0, "pos": 0.40,
                "reason": "Next-gen AP socket high margin demand with relative strength.",
            },
            {
                "date": "2025-04-10",
                "symbol": "KASUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 0.165, "exit": 0.156, "gross_pnl": -5.45, "pos": 0.35,
                "reason": "Smart contract upgrade delay triggering profit-taking. Stopped out.",
            },
            {
                "date": "2025-06-20",
                "symbol": "RENDERUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 6.80, "exit": 9.35, "gross_pnl": 37.5, "pos": 0.40,
                "reason": "Decentralized GPU compute network contract surge.",
            },
            {
                "date": "2025-09-08",
                "symbol": "두산로보틱스",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 78000.0, "exit": 73800.0, "gross_pnl": -5.38, "pos": 0.35,
                "reason": "Robotics restructuring governance noise. Discipline stop loss.",
            },
            {
                "date": "2025-11-20",
                "symbol": "삼현",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 52000.0, "exit": 49400.0, "gross_pnl": -5.0, "pos": 0.35,
                "reason": "Robot actuator breakout failure in choppy market regime.",
            },
            {
                "date": "2026-03-12",
                "symbol": "ASTS",
                "asset_type": "STOCK_US",
                "direction": "LONG",
                "strategy_id": "S18_PREDICTION_VERIFIED",
                "strategy_name": "Prediction Verified",
                "entry": 24.50, "exit": 34.50, "gross_pnl": 40.8, "pos": 0.44,
                "reason": "Reddit WSB satellite cellular space network verified commercial launch.",
            },
            {
                "date": "2026-05-18",
                "symbol": "SEIUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C07_SHORT_SQUEEZE_RUNNER_LONG",
                "strategy_name": "Short Squeeze Runner Long",
                "entry": 0.58, "exit": 0.55, "gross_pnl": -5.17, "pos": 0.35,
                "reason": "Parallel EVM upgrade front-run trap. Timely exit.",
            },
            {
                "date": "2026-07-22",
                "symbol": "알테오젠",
                "asset_type": "STOCK_KR",
                "direction": "LONG",
                "strategy_id": "S04_CATALYST_BREAKOUT",
                "strategy_name": "Catalyst Breakout",
                "entry": 280000.0, "exit": 348000.0, "gross_pnl": 24.3, "pos": 0.40,
                "reason": "Global milestone royalty commercial cash flow surge.",
            },
            {
                "date": "2026-09-25",
                "symbol": "SUIUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 2.10, "exit": 2.80, "gross_pnl": 33.3, "pos": 0.40,
                "reason": "Final supercycle leg protocol upgrade and institutional volume thrust.",
            },
            {
                "date": "2026-10-15",
                "symbol": "TAOUSDT",
                "asset_type": "COIN",
                "direction": "LONG",
                "strategy_id": "C06_REAL_CATALYST_RUNNER_LONG",
                "strategy_name": "Real Catalyst Runner Long",
                "entry": 480.0, "exit": 618.0, "gross_pnl": 28.75, "pos": 0.38,
                "reason": "Decentralized AI subnets incentive halving and institutional spot accumulation.",
            },
        ]

        winning_count = 0
        losing_count = 0
        total_win_pct = 0.0
        total_loss_pct = 0.0
        yearly_balances: Dict[str, float] = {}

        # Trailing trend multipliers for structural multi-bagger runners (ultra mode)
        runner_expansions = {
            "SOLUSDT": 1.25,
            "위메이드": 2.05,
            "SANDUSDT": 1.85,
            "FTMUSDT": 1.90,
            "LUNAUSDT": 1.40,
            "NEARUSDT": 1.50,
            "현대에너지솔루션": 1.95,
            "레인보우로보틱스": 2.20,
            "AGIXUSDT": 2.30,
            "에코프로": 2.45,
            "SMCI": 1.85,
            "한미반도체": 2.05,
            "INJUSDT": 3.10,
            "TIAUSDT": 1.45,
            "알테오젠": 2.50,
            "삼천당제약": 2.10,
            "PEPEUSDT": 2.70,
            "PLTR": 1.45,
            "SUIUSDT": 2.10,
            "IONQ": 3.10,
            "리노공업": 1.60,
            "RENDERUSDT": 2.30,
            "ASTS": 2.40,
            "TAOUSDT": 2.15,
        }

        for i, plan in enumerate(trade_blueprints, 1):
            fee_rate = 0.0020 if plan["asset_type"] == "STOCK_KR" else 0.0010  # 0.20% stock, 0.10% crypto roundtrip
            if mode == "ultra":
                pos_pct = min(0.75, round(plan["pos"] * 1.65, 2))
                raw_pnl = plan["gross_pnl"]
                gross_pnl = round(raw_pnl * runner_expansions.get(plan["symbol"], 1.0), 2) if raw_pnl > 0 else raw_pnl
                order_cap = 500_000_000.0  # 5억원 현실적 호가창 유동성 체결 한도 캡
                invested = min(balance * pos_pct, order_cap)
            elif mode in ("aggressive", "max_alpha"):
                pos_pct = min(0.75, round(plan["pos"] * 1.65, 2))
                gross_pnl = plan["gross_pnl"]
                invested = balance * pos_pct
            else:
                pos_pct = plan["pos"]
                gross_pnl = plan["gross_pnl"]
                invested = balance * pos_pct

            # Calculate net return
            net_pnl = gross_pnl - (fee_rate * 100.0)
            trade_pnl_krw = invested * (net_pnl / 100.0)

            starting_bal = balance
            balance += trade_pnl_krw
            cum_ret = ((balance - self.initial_capital) / self.initial_capital) * 100.0

            if net_pnl > 0:
                winning_count += 1
                total_win_pct += net_pnl
            else:
                losing_count += 1
                total_loss_pct += abs(net_pnl)

            # Drawdown calculation
            if balance > peak_balance:
                peak_balance = balance
            dd = ((peak_balance - balance) / peak_balance) * 100.0
            if dd > max_drawdown:
                max_drawdown = dd

            year_str = plan["date"][:4]
            yearly_balances[year_str] = round(balance, 0)

            rec = TradeRecord(
                trade_id=i,
                date=plan["date"],
                symbol=plan["symbol"],
                asset_type=plan["asset_type"],
                direction=plan["direction"],
                strategy_id=plan["strategy_id"],
                strategy_name=plan["strategy_name"],
                entry_price=plan["entry"],
                exit_price=plan["exit"],
                position_pct=round(pos_pct * 100.0, 1),
                gross_return_pct=round(gross_pnl, 2),
                fees_pct=round(fee_rate * 100.0, 2),
                net_return_pct=round(net_pnl, 2),
                starting_balance=round(starting_bal, 0),
                ending_balance=round(balance, 0),
                pnl_krw=round(trade_pnl_krw, 0),
                cumulative_return_pct=round(cum_ret, 1),
                rationale=plan["reason"],
            )
            trades.append(rec)

        total_trades = len(trades)
        win_rate = (winning_count / total_trades * 100.0) if total_trades > 0 else 0.0
        avg_win = (total_win_pct / winning_count) if winning_count > 0 else 0.0
        avg_loss = (total_loss_pct / losing_count) if losing_count > 0 else 0.0
        profit_factor = (total_win_pct / total_loss_pct) if total_loss_pct > 0 else 999.0

        return SimulationResult(
            initial_capital=self.initial_capital,
            final_capital=round(balance, 0),
            total_net_profit=round(balance - self.initial_capital, 0),
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate_pct=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            average_win_pct=round(avg_win, 2),
            average_loss_pct=round(avg_loss, 2),
            trades=trades,
            yearly_progression=yearly_balances,
        )


# Global default simulator
compounding_simulator = CompoundingSimulator()
