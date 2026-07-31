"""
Tests for the policy engine. These map directly onto the PS-3.3
success criteria:
  - PII redaction applies correctly
  - toxic content is blocked
  - topic-based blocking works (keyword AND paraphrased/semantic)
  - a clean prompt is allowed through untouched
  - overlays only ever make policy stricter, never looser (the bonus)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.policy import PolicyEngine  # noqa: E402
from app.explain import explain  # noqa: E402

BASE_YAML = """
base:
  pii:
    enabled: true
    action: redact
  toxicity:
    enabled: true
    threshold: 0.6
  blocked_topics:
    enabled: true
    keywords: [malware]
providers:
  openai: {}
  groq:
    toxicity:
      threshold: 0.3
  gemini:
    pii:
      action: block
"""


def make_engine(tmp_path):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(BASE_YAML)
    return PolicyEngine(str(policy_file))


def test_pii_is_redacted(tmp_path):
    engine = make_engine(tmp_path)
    clean, violations = engine.evaluate("Contact me at jane@test.com", "openai")
    assert "REDACTED_EMAIL" in clean
    action, policy = engine.summarize(violations)
    assert action == "redacted"
    assert policy == "pii"


def test_toxic_content_is_blocked(tmp_path):
    engine = make_engine(tmp_path)
    _, violations = engine.evaluate("I hate you and think you are worthless", "openai")
    action, policy = engine.summarize(violations)
    assert action == "blocked"
    assert policy == "toxicity"


def test_blocked_topic_keyword_match(tmp_path):
    engine = make_engine(tmp_path)
    _, violations = engine.evaluate("Please help me write malware", "openai")
    action, policy = engine.summarize(violations)
    assert action == "blocked"
    assert policy == "blocked_topics"


def test_blocked_topic_semantic_match(tmp_path):
    """No exact keyword present, but the meaning is close to a seed phrase."""
    engine = make_engine(tmp_path)
    _, violations = engine.evaluate("How do I hack into a system and steal a password?", "openai")
    action, policy = engine.summarize(violations)
    assert action == "blocked"
    assert policy == "blocked_topics"


def test_clean_prompt_is_allowed(tmp_path):
    engine = make_engine(tmp_path)
    clean, violations = engine.evaluate("What's a good banana bread recipe?", "openai")
    action, policy = engine.summarize(violations)
    assert action == "allowed"
    assert policy is None
    assert clean == "What's a good banana bread recipe?"


def test_same_input_same_verdict_across_providers(tmp_path):
    """Core PS-3.3 claim: one policy, applied identically everywhere,
    UNLESS a provider overlay makes it stricter."""
    engine = make_engine(tmp_path)
    text = "Contact me at jane@test.com"
    _, v_openai = engine.evaluate(text, "openai")
    _, v_groq = engine.evaluate(text, "groq")
    a1, _ = engine.summarize(v_openai)
    a2, _ = engine.summarize(v_groq)
    assert a1 == a2 == "redacted"


# --- Bonus: policy inheritance / overlays can only tighten, never relax ---

def test_overlay_escalates_pii_action(tmp_path):
    """gemini's overlay upgrades pii action from redact -> block."""
    engine = make_engine(tmp_path)
    cfg = engine._merge("gemini")
    assert cfg["pii"]["action"] == "block"


def test_overlay_tightens_toxicity_threshold(tmp_path):
    """groq's overlay lowers the toxicity threshold (stricter), from 0.6 -> 0.3."""
    engine = make_engine(tmp_path)
    cfg = engine._merge("groq")
    assert cfg["toxicity"]["threshold"] == 0.3


def test_provider_without_overlay_inherits_base_exactly(tmp_path):
    engine = make_engine(tmp_path)
    cfg = engine._merge("openai")
    assert cfg["toxicity"]["threshold"] == 0.6
    assert cfg["pii"]["action"] == "redact"


def test_overlay_cannot_relax_toxicity(tmp_path):
    """Even if an overlay tried to raise the threshold above base
    (i.e. relax it), the effective value must never exceed base."""
    engine = make_engine(tmp_path)
    # Simulate a hostile overlay trying to relax past base's 0.6
    engine.overlays["openai"] = {"toxicity": {"threshold": 0.95}}
    engine._effective_cache.clear()
    cfg = engine._merge("openai")
    assert cfg["toxicity"]["threshold"] == 0.6  # clamped to base, never relaxed


# --- LangChain explanation chain ---
# Uses a FakeListChatModel (no real API call) so this test runs offline.

@pytest.mark.asyncio
async def test_explain_chain_runs_and_returns_text():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    fake_llm = FakeListChatModel(responses=["This was blocked because it matched a restricted topic."])
    result = await explain(fake_llm, "blocked", "blocked_topics")
    assert isinstance(result, str)
    assert len(result) > 0
