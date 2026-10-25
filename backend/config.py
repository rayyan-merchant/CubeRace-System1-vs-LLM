import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    key: str = ""
    allow_live: bool = False
    mock_mode: bool = True
    budget: int = 1200
    timeout: float = 30
    retries: int = 0
    claude_reasoning_effort: str = "low"
    claude_max_tokens: int = 1024
    concurrency: int = 4
    student_name: str = ""
    student_roll: str = ""
    database: str = "data/cuberace.sqlite3"

    def __post_init__(self):
        if self.claude_reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ValueError("CLAUDE_REASONING_EFFORT must be low, medium, high, xhigh or max; reasoning stays enabled")
        if not 32 <= self.claude_max_tokens <= 128000:
            raise ValueError("CLAUDE_MAX_TOKENS must be between 32 and 128000")

    @classmethod
    def env(cls):
        return cls(
            key=os.getenv("OPENROUTER_API_KEY", ""),
            allow_live=os.getenv("ALLOW_LIVE", "false").lower() == "true",
            mock_mode=os.getenv("OPENROUTER_MOCK_MODE", "true").lower() == "true",
            budget=max(0, int(os.getenv("API_CALL_BUDGET", "1200"))),
            timeout=max(1, float(os.getenv("API_TIMEOUT_SECONDS", "30"))),
            retries=min(3, max(0, int(os.getenv("API_RETRIES", "0")))),
            claude_reasoning_effort=os.getenv("CLAUDE_REASONING_EFFORT", "low").lower(),
            claude_max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "1024")),
            concurrency=min(4, max(1, int(os.getenv("API_CONCURRENCY", "4")))),
            student_name=os.getenv("STUDENT_NAME", ""),
            student_roll=os.getenv("STUDENT_ROLL", ""),
            database=os.getenv("DATABASE_PATH", "data/cuberace.sqlite3"),
        )
