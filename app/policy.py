"""
The Policy Engine  --  the heart of GuardMesh.

One YAML file (configs/policy.yaml) describes the rules ONCE. This
class loads it, merges each provider's optional overlay on top of the
shared "base" policy, and exposes a single method  --  evaluate()  --  that
every provider's request AND response gets run through identically.

Three checks are implemented, exactly as the spec asks for:
  1. PII        -> regex-based detection + redaction
  2. Toxicity   -> lightweight keyword/lexicon scorer (0.0-1.0 score)
  3. Blocked topics -> keyword match + a simple TF-IDF "semantic"
                       similarity check against a few seed phrases,
                       so paraphrased requests are caught too, not
                       just exact keyword matches.

BONUS  --  policy inheritance:
  Each provider can have an "overlay" that makes the base policy
  STRICTER for that provider only. An overlay can never make it
  looser. That rule is enforced in `_merge()`:
    - toxicity threshold  -> effective = min(base, overlay)   (lower = stricter)
    - pii action           -> effective = the stricter of the two (block > redact)
    - blocked_topics list  -> effective = base keywords UNION overlay keywords
    - enabled flags         -> once true in base, an overlay cannot turn it off
"""
import re
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- PII patterns (regex-based, as explicitly allowed by the spec) ---
PII_PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"\b\d{10}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}

# --- Toxicity lexicon: small, explainable, and swappable.
# In production you'd point this at a real classifier (e.g. a HuggingFace
# model)  --  the interface (`_check_toxicity`) wouldn't need to change,
# only this dictionary / the scoring function.
TOXIC_LEXICON = {
    "kill you": 0.9, "hate you": 0.6, "worthless": 0.5,
    "idiot": 0.5, "moron": 0.5, "stupid": 0.4, "dumb": 0.3,
}

# --- Seed phrases used for the "semantic" half of blocked-topic matching.
# A prompt doesn't need to contain the exact keyword  --  if it's close in
# meaning (by TF-IDF cosine similarity) to one of these seeds, it's flagged.
TOPIC_SEEDS = {
    "violence": ["how to make a bomb", "build an explosive device", "how to hurt someone badly"],
    "hacking": ["how do I hack into a system", "steal someone's password", "write a computer virus"],
}

ACTION_RANK = {"allow": 0, "redact": 1, "block": 2}


class PolicyEngine:
    def __init__(self, path: str):
        self.path = Path(path)
        self._effective_cache: dict[str, dict] = {}
        self.reload()

    def reload(self) -> dict:
        """Re-read the YAML file from disk without restarting the app."""
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.base = raw.get("base", {})
        self.overlays = raw.get("providers", {})
        self._effective_cache.clear()
        return raw

    # ------------------------------------------------------------------
    # Bonus: policy inheritance. Merges the base policy with a provider's
    # overlay, but the overlay is only ever allowed to make things stricter.
    # ------------------------------------------------------------------
    def _merge(self, provider: str) -> dict:
        if provider in self._effective_cache:
            return self._effective_cache[provider]

        overlay = self.overlays.get(provider, {}) or {}

        # PII: pick whichever action is stricter (block > redact > allow)
        base_pii, ov_pii = self.base.get("pii", {}), overlay.get("pii", {})
        pii_action = base_pii.get("action", "redact")
        if "action" in ov_pii:
            pii_action = max([pii_action, ov_pii["action"]], key=lambda a: ACTION_RANK[a])

        # Toxicity: lower threshold = stricter, so take the minimum
        base_tox, ov_tox = self.base.get("toxicity", {}), overlay.get("toxicity", {})
        threshold = base_tox.get("threshold", 0.6)
        if "threshold" in ov_tox:
            threshold = min(threshold, ov_tox["threshold"])

        # Blocked topics: overlay can only ADD keywords, never remove any
        base_topics = self.base.get("blocked_topics", {})
        ov_topics = overlay.get("blocked_topics", {})
        keywords = sorted(set(base_topics.get("keywords", [])) | set(ov_topics.get("keywords", [])))

        merged = {
            "pii": {
                "enabled": base_pii.get("enabled", True) or ov_pii.get("enabled", False),
                "action": pii_action,
            },
            "toxicity": {
                "enabled": base_tox.get("enabled", True) or ov_tox.get("enabled", False),
                "threshold": threshold,
            },
            "blocked_topics": {
                "enabled": base_topics.get("enabled", True) or ov_topics.get("enabled", False),
                "keywords": keywords,
            },
        }
        self._effective_cache[provider] = merged
        return merged

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------
    def _check_pii(self, text: str, cfg: dict):
        if not cfg["enabled"]:
            return text, None
        found, redacted = [], text
        for label, pattern in PII_PATTERNS.items():
            if pattern.search(redacted):
                found.append(label)
                redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
        if not found:
            return text, None
        action = cfg["action"]
        clean_text = redacted if action == "redact" else text
        return clean_text, {"policy": "pii", "labels": found, "action": action}

    def _check_toxicity(self, text: str, cfg: dict):
        if not cfg["enabled"]:
            return None
        lower = text.lower()
        score, hits = 0.0, []
        for phrase, weight in TOXIC_LEXICON.items():
            if phrase in lower:
                score = max(score, weight)
                hits.append(phrase)
        if score >= cfg["threshold"] and hits:
            return {"policy": "toxicity", "score": round(score, 2), "hits": hits, "action": "block"}
        return None

    def _check_topics(self, text: str, cfg: dict):
        if not cfg["enabled"]:
            return None
        lower = text.lower()

        # 1) exact keyword match
        for kw in cfg["keywords"]:
            if kw.lower() in lower:
                return {"policy": "blocked_topics", "match": kw, "method": "keyword", "action": "block"}

        # 2) semantic similarity fallback  --  catches paraphrased requests
        for topic, seeds in TOPIC_SEEDS.items():
            corpus = seeds + [text]
            try:
                vectors = TfidfVectorizer().fit_transform(corpus)
                sims = cosine_similarity(vectors[-1], vectors[:-1])[0]
            except ValueError:
                continue  # empty vocabulary (e.g. text was just punctuation)
            if sims.max() >= 0.35:
                return {
                    "policy": "blocked_topics", "match": topic, "method": "semantic",
                    "score": round(float(sims.max()), 2), "action": "block",
                }
        return None

    # ------------------------------------------------------------------
    # Public entry point  --  used for BOTH the prompt and the model's reply
    # ------------------------------------------------------------------
    def evaluate(self, text: str, provider: str) -> tuple[str, list[dict]]:
        cfg = self._merge(provider)
        violations = []
        clean = text

        topic_hit = self._check_topics(clean, cfg["blocked_topics"])
        if topic_hit:
            violations.append(topic_hit)

        tox_hit = self._check_toxicity(clean, cfg["toxicity"])
        if tox_hit:
            violations.append(tox_hit)

        clean, pii_hit = self._check_pii(clean, cfg["pii"])
        if pii_hit:
            violations.append(pii_hit)

        return clean, violations

    @staticmethod
    def summarize(violations: list[dict]) -> tuple[str, str | None]:
        """Collapse a list of violations into one overall verdict."""
        if not violations:
            return "allowed", None
        for v in violations:
            if v["action"] == "block":
                return "blocked", v["policy"]
        return "redacted", violations[0]["policy"]
