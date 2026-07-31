from pydantic import BaseModel


class ChatRequest(BaseModel):
    provider: str
    prompt: str
    model: str | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str | None
    response: str | None
    action_taken: str
    triggered_policy: str | None
    explanation: str | None
    explanation_details: dict | None = None
    latency_ms: float
    status: str
