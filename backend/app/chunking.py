# backend/app/chunking.py
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

class DocumentChunker:
    """Split documents into overlapping chunks for RAG."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks and attach metadata.
        
        Args:
            text: Raw document text.
            metadata: Original document metadata (filename, page, etc.)
            
        Returns:
            List of dicts: {"text": str, "metadata": dict, "chunk_index": int}
        """
        chunks = self.splitter.split_text(text)
        result = []
        for idx, chunk in enumerate(chunks):
            chunk_meta = (metadata or {}).copy()
            chunk_meta["chunk_index"] = idx
            chunk_meta["chunk_total"] = len(chunks)
            result.append({
                "text": chunk,
                "metadata": chunk_meta,
                "chunk_index": idx,
            })
        return result

# Singleton for reuse
_chunker = None

def get_chunker() -> DocumentChunker:
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker