import hashlib
import time
import uuid
import json
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    timestamp = Column(Float, nullable=False, default=time.time)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    prompt_hash = Column(String(64), nullable=False)
    response_hash = Column(String(64), nullable=True)
    triggered_policy = Column(String(100), nullable=True)
    triggered_policies = Column(Text, nullable=True)
    detected_violations = Column(Text, nullable=True)
    action_taken = Column(String(50), nullable=False)
    explanation = Column(Text, nullable=True)
    provider_latency = Column(Float, nullable=True)
    policy_evaluation_time = Column(Float, nullable=True)
    total_request_latency = Column(Float, nullable=False)
    policy_version = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False)
    latency_ms = Column(Float, nullable=False)


db_url = settings.get_db_url()

if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def record(
    provider: str,
    model: str | None,
    prompt: str,
    response: str | None,
    triggered_policy: str | None,
    action_taken: str,
    status: str,
    latency_ms: float,
    explanation: str | None = None,
    request_id: str | None = None,
    prompt_hash: str | None = None,
    response_hash: str | None = None,
    triggered_policies: str | None = None,
    detected_violations: str | None = None,
    provider_latency: float | None = None,
    policy_evaluation_time: float | None = None,
    total_request_latency: float | None = None,
    policy_version: str | None = None,
) -> None:
    if not prompt_hash and prompt:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if not response_hash and response:
        response_hash = hashlib.sha256(response.encode("utf-8")).hexdigest()
    if not request_id:
        request_id = str(uuid.uuid4())
    if total_request_latency is None:
        total_request_latency = latency_ms

    with get_session() as session:
        log_entry = AuditLog(
            request_id=request_id,
            timestamp=time.time(),
            provider=provider,
            model=model,
            prompt=prompt,
            response=response,
            prompt_hash=prompt_hash or "",
            response_hash=response_hash,
            triggered_policy=triggered_policy,
            triggered_policies=triggered_policies,
            detected_violations=detected_violations,
            action_taken=action_taken,
            explanation=explanation,
            provider_latency=provider_latency,
            policy_evaluation_time=policy_evaluation_time,
            total_request_latency=total_request_latency,
            policy_version=policy_version or "1.0.0",
            status=status,
            latency_ms=latency_ms,
        )
        session.add(log_entry)


def list_logs(limit: int = 50) -> list[dict]:
    with get_session() as session:
        rows = session.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "request_id": r.request_id,
                "timestamp": r.timestamp,
                "provider": r.provider,
                "model": r.model,
                "prompt": r.prompt,
                "response": r.response,
                "prompt_hash": r.prompt_hash,
                "response_hash": r.response_hash,
                "triggered_policy": r.triggered_policy,
                "triggered_policies": r.triggered_policies,
                "detected_violations": r.detected_violations,
                "action_taken": r.action_taken,
                "explanation": r.explanation,
                "provider_latency": r.provider_latency,
                "policy_evaluation_time": r.policy_evaluation_time,
                "total_request_latency": r.total_request_latency,
                "latency_ms": r.latency_ms,
                "policy_version": r.policy_version,
                "status": r.status,
            })
        return result


def summary() -> dict:
    with get_session() as session:
        total = session.query(AuditLog).count()

        by_provider_action = {}
        rows = session.query(
            AuditLog.provider, AuditLog.action_taken, func.count(AuditLog.id)
        ).group_by(AuditLog.provider, AuditLog.action_taken).all()
        for prov, action, count in rows:
            by_provider_action.setdefault(prov, {})[action] = count

        by_action = {}
        action_rows = session.query(
            AuditLog.action_taken, func.count(AuditLog.id)
        ).group_by(AuditLog.action_taken).all()
        for action, count in action_rows:
            by_action[action] = count

        avg_latency = session.query(func.avg(AuditLog.total_request_latency)).scalar() or 0.0

        by_provider = {}
        prov_rows = session.query(
            AuditLog.provider, func.count(AuditLog.id)
        ).group_by(AuditLog.provider).all()
        for prov, count in prov_rows:
            by_provider[prov] = count

        by_policy = {}
        policy_rows = session.query(
            AuditLog.triggered_policy, func.count(AuditLog.id)
        ).filter(AuditLog.triggered_policy.isnot(None)).group_by(AuditLog.triggered_policy).all()
        for pol, count in policy_rows:
            by_policy[pol] = count

        pii_count = session.query(AuditLog).filter(AuditLog.triggered_policy == "pii").count()

        blocked_topics = {}
        blocked_rows = session.query(
            AuditLog.triggered_policy, func.count(AuditLog.id)
        ).filter(AuditLog.action_taken == "blocked", AuditLog.triggered_policy.isnot(None)).group_by(AuditLog.triggered_policy).all()
        for pol, count in blocked_rows:
            blocked_topics[pol] = count

        return {
            "total_requests": total,
            "by_provider": by_provider_action,
            "by_action": by_action,
            "average_latency": round(float(avg_latency), 2),
            "provider_usage": by_provider,
            "policy_violations": by_policy,
            "pii_count": pii_count,
            "top_blocked_topics": blocked_topics,
        }
