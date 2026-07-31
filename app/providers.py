from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def get_llm(self, model: str | None = None) -> BaseChatModel:
        ...

    async def chat(self, prompt: str, model: str | None = None) -> str:
        import asyncio
        llm = self.get_llm(model)
        response = await asyncio.wait_for(
            asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt)]),
            timeout=20.0
        )
        return response.content

    async def check_health(self) -> str:
        try:
            llm = self.get_llm()
            await llm.ainvoke([HumanMessage(content="ok")], config={"timeout": 3.0})
            return "healthy"
        except Exception:
            return "unhealthy"


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.default_model = settings.OPENAI_MODEL
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self._llm = self._build(self.default_model)

    def _build(self, model: str) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=self.api_key, max_tokens=1000)

    def get_llm(self, model: str | None = None) -> BaseChatModel:
        if model and model != self.default_model:
            return self._build(model)
        return self._llm


class GroqProvider(BaseProvider):
    name = "groq"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.default_model = settings.GROQ_MODEL
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        self._llm = self._build(self.default_model)

    def _build(self, model: str) -> BaseChatModel:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, api_key=self.api_key, max_tokens=1000)

    def get_llm(self, model: str | None = None) -> BaseChatModel:
        if model and model != self.default_model:
            return self._build(model)
        return self._llm


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.default_model = settings.GEMINI_MODEL
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._llm = self._build(self.default_model)

    def _build(self, model: str) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.api_key,
            max_output_tokens=1000
        )

    def get_llm(self, model: str | None = None) -> BaseChatModel:
        if model and model != self.default_model:
            return self._build(model)
        return self._llm


_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}
_INSTANCES: dict[str, BaseProvider] = {}


def get_provider(name: str) -> BaseProvider:
    key = name.lower().strip()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Available: {list(_REGISTRY)}")
    if key not in _INSTANCES:
        _INSTANCES[key] = _REGISTRY[key]()
    return _INSTANCES[key]


def available_providers() -> list[str]:
    return list(_REGISTRY)
