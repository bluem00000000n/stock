"""
Intelligence Manager router.
Unified access point for text, news, and community post analysis.
Zero external paid API keys required.
"""

from typing import Optional
from signal_forge.config import config
from signal_forge.intelligence.lm_studio import LocalLMStudioClient
from signal_forge.intelligence.rule_engine import RuleBasedIntelligenceEngine, TextAnalysisResult


class IntelligenceManager:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or config.ai_provider).lower()
        self.rule_engine = RuleBasedIntelligenceEngine()
        self.lm_studio = LocalLMStudioClient()

    def analyze_text(self, text: str) -> TextAnalysisResult:
        if self.provider == "lmstudio":
            return self.lm_studio.analyze(text)
        elif self.provider == "mock":
            res = self.rule_engine.analyze(text)
            res.summary = f"[MOCK_AI] {res.summary}"
            return res
        else:
            # Default is pure rule-based high-precision regex/NLP
            return self.rule_engine.analyze(text)


# Default global instance
intelligence = IntelligenceManager()
