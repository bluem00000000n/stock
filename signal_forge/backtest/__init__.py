"""
Signal Forge Backtest Package.
Provides historical compounding simulation and quant backtesting engines.
"""

from signal_forge.backtest.simulator import CompoundingSimulator, TradeRecord, SimulationResult

__all__ = ["CompoundingSimulator", "TradeRecord", "SimulationResult"]
