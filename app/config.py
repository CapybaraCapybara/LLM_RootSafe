import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Determine project base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# OpenAI Client configured for class proxy
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://llm.nat-d.uk/v1")
MODEL = os.getenv("MODEL", "gemma-4-E4B-it")

# RAG & Storage Settings
CHROMA_PERSIST_DIR = str(BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", ".chroma"))
DATA_PATH = BASE_DIR / "data" / "trees.json"
DEFAULT_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.35"))

# Initialize OpenAI client with fallback-safe parameters
client = OpenAI(
    api_key=OPENAI_API_KEY if OPENAI_API_KEY else "dummy-key",
    base_url=OPENAI_BASE_URL,
)
