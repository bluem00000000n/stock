"""
Local LM Studio Integration Client.
Connects to local inference server (http://localhost:1234/v1) with zero external API keys.
Gracefully falls back to RuleBasedIntelligenceEngine if local server is unreachable.
"""

from typing import Optional
import requests
from signal_forge.config import config
from signal_forge.intelligence.rule_engine import RuleBasedIntelligenceEngine, TextAnalysisResult
from signal_forge.observability.logger import get_logger

logger = get_logger("lm_studio")


class LocalLMStudioClient:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: int = 5,
    ):
        self.endpoint = endpoint or config.lm_studio_url
        self.model = model or config.lm_studio_model
        self.timeout_sec = timeout_sec
        self.fallback_engine = RuleBasedIntelligenceEngine()

    def is_available(self) -> bool:
        """Checks if local LM Studio HTTP server is responsive."""
        try:
            r = requests.get(f"{self.endpoint}/models", timeout=self.timeout_sec)
            return r.status_code == 200
        except Exception:
            return False

    def analyze(self, text: str) -> TextAnalysisResult:
        """Analyzes text using local LLM, falling back to rule engine if unavailable."""
        if not self.is_available():
            logger.debug("LM Studio not running locally. Using pure rule-based intelligence engine.")
            return self.fallback_engine.analyze(text)

        prompt = f"""You are a financial intelligence analyst. Analyze this community post or news snippet.
Answer strictly in JSON with fields:
- mentioned_symbols (array of strings)
- has_7d_surge_claim (boolean)
- is_promotional_scam (boolean)
- sentiment_score (float between -1.0 and 1.0)
- summary (one short sentence)

Text: {text}
"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a quantitative market intelligence agent."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 150,
        }

        try:
            resp = requests.post(
                f"{self.endpoint}/chat/completions",
                json=payload,
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Fallback to rule engine to guarantee schema and deterministic values
                base_res = self.fallback_engine.analyze(text)
                base_res.summary = f"[LOCAL_LLM] {content.strip()[:100]}"
                return base_res
        except Exception as e:
            logger.warning(f"Local LLM call failed ({e}). Falling back to rule engine.")

        return self.fallback_engine.analyze(text)
