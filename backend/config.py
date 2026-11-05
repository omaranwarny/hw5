"""Shared settings for the Campus Customs agent team."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent          # hw5/
BACKEND = ROOT / "backend"
PROMPTS = BACKEND / "prompts"
MCP_SERVER = ROOT / "mcp_server" / "server.py"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
PYTHON = sys.executable

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")   # fallback: AI Class/.env

# Assignment rule: every agent uses ONLY this model, through Portkey. Not configurable on purpose.
MODEL_NAME = "gpt-6-luna"

# Token / loop budget for ONE ticket (shared by the Boss and every agent it delegates to).
MAX_REQUESTS_PER_TICKET = 30        # model calls across the whole team
MAX_TOOL_CALLS_PER_TICKET = 50
MAX_TOKENS_PER_TICKET = 200_000
MAX_DELEGATION_DEPTH = 2            # boss -> specialist -> specialist, no deeper
MAX_DELEGATIONS_PER_TICKET = 6


# gpt-6-luna on Portkey/Azure rejects function tools + reasoning on /v1/chat/completions, so the team uses the
# Responses API (/v1/responses), which supports both. Escape hatch: CC_OPENAI_API=chat -> chat with reasoning off.
OPENAI_API = os.getenv("CC_OPENAI_API", "responses").strip().lower()
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


@lru_cache(maxsize=1)
def make_model():
    from openai import AsyncOpenAI
    from pydantic_ai.providers.openai import OpenAIProvider

    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing (hw5/.env or AI Class/.env).")
    client = AsyncOpenAI(
        api_key="unused",
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
    )
    provider = OpenAIProvider(openai_client=client)
    if OPENAI_API == "chat":
        from pydantic_ai.models.openai import OpenAIChatModel
        return OpenAIChatModel(MODEL_NAME, provider=provider,
                               settings={"openai_reasoning_effort": "none"})  # type: ignore[typeddict-item]
    from pydantic_ai.models.openai import OpenAIResponsesModel
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)
