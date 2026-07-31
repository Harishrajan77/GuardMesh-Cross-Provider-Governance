from pydantic import BaseModel


class ChatRequest(BaseModel):
    provider: str          # "openai" | "groq" | "gemini"
    prompt: str
    model: str | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str | None
    response: str | None
    action_taken: str          # "allowed" | "redacted" | "blocked"
    triggered_policy: str | None
    explanation: str | None     # plain-English reason, via LangChain
    explanation_details: dict | None = None # structured explanation
    latency_ms: float
    status: str                 # "success" | "error"
