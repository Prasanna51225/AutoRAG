# backend/app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Qdrant
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_cache_ttl: int = Field(default=3600, alias="REDIS_CACHE_TTL")
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2:3b", alias="OLLAMA_MODEL")
    
    # Embedding cache
    embedding_cache_ttl: int = Field(default=3600, alias="EMBEDDING_CACHE_TTL")
    
    # Reranker
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")
    reranker_cutoff: int = Field(default=50, alias="RERANKER_CUTOFF")
    
    # Reflexion loop
    max_loops: int = Field(default=3, alias="MAX_LOOPS")
    critic_threshold: float = Field(default=0.3, alias="CRITIC_THRESHOLD")
    
    # Retrieval
    hybrid_alpha: float = Field(default=0.6, alias="HYBRID_ALPHA")
    dynamic_topk: bool = Field(default=True, alias="DYNAMIC_TOPK")
    
    # Chunking
    chunk_size: int = Field(default=1024, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=256, alias="CHUNK_OVERLAP")
    
    # LangSmith
    langsmith_api_key: Optional[str] = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(default="AutoRAG", alias="LANGSMITH_PROJECT")
    
    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()