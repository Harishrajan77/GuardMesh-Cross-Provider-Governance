from __future__ import annotations

import time
import uuid
import json
import hashlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.database import init_db, list_logs, record, summary
from app.explain import explain
from app.policy import PolicyEngine
from app.providers import available_providers, get_provider
from app.schemas import ChatRequest, ChatResponse

START_TIME = time.time()
policy_engine = PolicyEngine(settings.POLICY_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GuardMesh",
    description="One policy. Every model. Unified AI governance across LLM providers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")


def require_api_key(x_api_key: str | None = Header(default=None)):
    if settings.GUARDMESH_API_KEY and x_api_key != settings.GUARDMESH_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")
    return True


@app.get("/")
def root():
    return RedirectResponse(url="/ui/")


def get_hash(text: str | None) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_remediation(policy: str | None) -> str:
    if not policy:
        return "Please adjust your request to comply with safety policies."
    suggestions = {
        "pii": "Please remove sensitive personal data (e.g., email addresses, phone numbers, or credit card details) from your request.",
        "toxicity": "Please rephrase your request using respectful, non-harmful language.",
        "blocked_topics": "Please modify your request to avoid topics related to restricted domains (e.g., hacking, malware, weapons)."
    }
    return suggestions.get(policy.lower(), "Please adjust your request to comply with safety policies.")


def get_providers_status() -> dict[str, str]:
    out = {}
    for name in available_providers():
        try:
            get_provider(name)
            out[name] = "healthy"
        except Exception:
            out[name] = "unhealthy"
    return out


@app.get("/health")
def health():
    db_status = "connected"
    from sqlalchemy.sql import text
    from app.database import get_session
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
        
    prov_health = get_providers_status()
    uptime_sec = int(time.time() - START_TIME)
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "policy_version": "1.0.0",
        "providers": prov_health,
        "uptime": f"{uptime_sec}s",
        "version": "1.0.0"
    }


@app.get("/providers")
def providers():
    return get_providers_status()


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    t_eval_start = time.perf_counter()
    clean_prompt, prompt_violations = policy_engine.evaluate(req.prompt, req.provider)
    action, policy_name = policy_engine.summarize(prompt_violations)
    t_eval_prompt_ms = (time.perf_counter() - t_eval_start) * 1000

    if action == "blocked":
        explanation_text = f"This request was {action} because it triggered the {policy_name} governance policy."
        try:
            provider = get_provider(req.provider)
            explanation_text = await explain(provider.get_llm(), action, policy_name)
        except Exception:
            pass
            
        latency = (time.perf_counter() - start) * 1000
        
        explanation_details = {
            "reason": explanation_text,
            "violated_policy": policy_name,
            "action_taken": action,
            "remediation_suggestion": get_remediation(policy_name)
        }
        
        record(
            provider=req.provider, model=req.model, prompt=req.prompt, response=None,
            triggered_policy=policy_name, action_taken=action, status="success",
            latency_ms=latency, explanation=explanation_text,
            request_id=request_id, prompt_hash=get_hash(req.prompt), response_hash=None,
            triggered_policies=json.dumps([v["policy"] for v in prompt_violations]),
            detected_violations=json.dumps(prompt_violations),
            provider_latency=0.0, policy_evaluation_time=t_eval_prompt_ms,
            total_request_latency=latency, policy_version="1.0.0"
        )
        return ChatResponse(
            provider=req.provider, model=req.model, response=None,
            action_taken=action, triggered_policy=policy_name,
            explanation=explanation_text, explanation_details=explanation_details,
            latency_ms=round(latency, 2), status="success",
        )

    actual_provider = req.provider
    call_status = "success"
    provider_latency_ms = 0.0
    raw_reply = ""
    
    attempts = 2
    for attempt in range(attempts):
        try:
            provider = get_provider(req.provider)
            t_call_start = time.perf_counter()
            raw_reply = await provider.chat(clean_prompt, req.model)
            provider_latency_ms = (time.perf_counter() - t_call_start) * 1000
            break
        except Exception as exc:
            if attempt == 0:
                continue
            else:
                failover_success = False
                for backup_name in available_providers():
                    if backup_name == req.provider:
                        continue
                    try:
                        backup_prov = get_provider(backup_name)
                        t_call_start = time.perf_counter()
                        raw_reply = await backup_prov.chat(clean_prompt, req.model)
                        provider_latency_ms = (time.perf_counter() - t_call_start) * 1000
                        actual_provider = backup_name
                        failover_success = True
                        call_status = f"failover_to_{backup_name}"
                        break
                    except Exception:
                        continue
                if not failover_success:
                    raw_reply = f"Provider error after failover: {exc}"
                    call_status = "error"

    t_eval_resp_start = time.perf_counter()
    raw_reply = raw_reply or ""
    clean_reply, reply_violations = policy_engine.evaluate(raw_reply, actual_provider)
    resp_action, resp_policy = policy_engine.summarize(reply_violations)
    t_eval_resp_ms = (time.perf_counter() - t_eval_resp_start) * 1000

    final_action = resp_action if resp_action != "allowed" else action
    final_policy = resp_policy or policy_name
    final_reply = None if final_action == "blocked" else clean_reply

    explanation_text = None
    explanation_details = None
    if final_action != "allowed":
        explanation_text = f"This request was {final_action} because it triggered the {final_policy} governance policy."
        try:
            provider_inst = get_provider(actual_provider)
            explanation_text = await explain(provider_inst.get_llm(), final_action, final_policy)
        except Exception:
            pass
            
        explanation_details = {
            "reason": explanation_text,
            "violated_policy": final_policy,
            "action_taken": final_action,
            "remediation_suggestion": get_remediation(final_policy)
        }

    latency = (time.perf_counter() - start) * 1000
    all_violations = prompt_violations + reply_violations
    record(
        provider=actual_provider, model=req.model, prompt=req.prompt, response=final_reply,
        triggered_policy=final_policy, action_taken=final_action, status=call_status,
        latency_ms=latency, explanation=explanation_text,
        request_id=request_id, prompt_hash=get_hash(req.prompt), response_hash=get_hash(final_reply),
        triggered_policies=json.dumps([v["policy"] for v in all_violations]),
        detected_violations=json.dumps(all_violations),
        provider_latency=provider_latency_ms,
        policy_evaluation_time=t_eval_prompt_ms + t_eval_resp_ms,
        total_request_latency=latency, policy_version="1.0.0"
    )

    return ChatResponse(
        provider=actual_provider, model=req.model, response=final_reply,
        action_taken=final_action, triggered_policy=final_policy,
        explanation=explanation_text, explanation_details=explanation_details,
        latency_ms=round(latency, 2), status=call_status,
    )


@app.get("/audit", dependencies=[Depends(require_api_key)])
def audit(limit: int = 50):
    return list_logs(limit)


@app.get("/audit/summary", dependencies=[Depends(require_api_key)])
def audit_summary():
    return summary()


class PolicyUpdateRequest(BaseModel):
    yaml_content: str


@app.post("/reload-policy", dependencies=[Depends(require_api_key)])
def reload_policy():
    raw = policy_engine.reload()
    return {"status": "reloaded", "base_checks": list(raw.get("base", {}).keys())}


@app.post("/update-policy", dependencies=[Depends(require_api_key)])
def update_policy(req: PolicyUpdateRequest):
    with open(settings.POLICY_PATH, "w", encoding="utf-8") as f:
        f.write(req.yaml_content)
    raw = policy_engine.reload()
    return {"status": "updated", "base_checks": list(raw.get("base", {}).keys())}


@app.get("/policy/effective/{provider}", dependencies=[Depends(require_api_key)])
def effective_policy(provider: str):
    return policy_engine._merge(provider.lower())
