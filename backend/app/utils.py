# backend/app/utils.py
import logging
import redis
from typing import Optional
from pypdf import PdfReader
import os
from app.config import settings

# Logger setup
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

# Redis client (singleton)
_redis_client = None

def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=False)
        _redis_client.ping()  # verify connection
    return _redis_client

def parse_document(file_path: str) -> str:
    """
    Extract text from PDF or plain text file.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        if not text.strip():
            raise ValueError("PDF contains no extractable text")
        return text
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

import httpx
from app.config import settings

async def call_ollama(prompt: str, model: str = None) -> str:
    model = model or settings.ollama_model
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        return resp.json()["response"]