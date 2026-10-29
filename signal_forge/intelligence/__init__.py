"""Intelligence and NLP analysis layer."""

from .rule_engine import RuleBasedIntelligenceEngine, TextAnalysisResult
from .lm_studio import LocalLMStudioClient
from .manager import IntelligenceManager, intelligence

__all__ = [
    "RuleBasedIntelligenceEngine",
    "TextAnalysisResult",
    "LocalLMStudioClient",
    "IntelligenceManager",
    "intelligence",
]
