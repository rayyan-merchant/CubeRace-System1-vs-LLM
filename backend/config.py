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
    retries: int = 1
    concurrency: int = 4
    student_name: str = ""
    student_roll: str = ""
    database: str = "data/cuberace.sqlite3"

    @classmethod
    def env(cls):
        return cls(
            key=os.getenv("OPENROUTER_API_KEY", ""),
            allow_live=os.getenv("ALLOW_LIVE", "false").lower() == "true",
            mock_mode=os.getenv("OPENROUTER_MOCK_MODE", "true").lower() == "true",
            budget=max(0, int(os.getenv("API_CALL_BUDGET", "1200"))),
            timeout=max(1, float(os.getenv("API_TIMEOUT_SECONDS", "30"))),
            retries=min(3, max(0, int(os.getenv("API_RETRIES", "1")))),
            concurrency=min(4, max(1, int(os.getenv("API_CONCURRENCY", "4")))),
            student_name=os.getenv("STUDENT_NAME", ""),
            student_roll=os.getenv("STUDENT_ROLL", ""),
            database=os.getenv("DATABASE_PATH", "data/cuberace.sqlite3"),
        )
