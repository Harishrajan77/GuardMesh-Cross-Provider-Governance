import asyncio
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

_PROMPT = ChatPromptTemplate.from_template(
    "A user's AI request was {action} by an automated governance policy.\n"
    "Triggered policy: {policy}\n\n"
    "In exactly one short, plain-English sentence, explain to a "
    "non-technical person why this happened. Do not repeat or guess "
    "at the original request content. Do not mention 'AI model' or "
    "technical implementation details  --  just explain the policy reason."
)


async def explain(llm, action: str, policy: str) -> str:
    try:
        chain = _PROMPT | llm | StrOutputParser()
        return await asyncio.wait_for(
            asyncio.to_thread(chain.invoke, {"action": action, "policy": policy}),
            timeout=4.0
        )
    except Exception:
        return f"This request was {action} because it triggered the {policy} governance policy."
