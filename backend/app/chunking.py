from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DocumentChunker:
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 256):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        chunks = self.splitter.split_text(text)
        result = []
        for idx, chunk in enumerate(chunks):
            chunk_meta = (metadata or {}).copy()
            chunk_meta["chunk_index"] = idx
            chunk_meta["chunk_total"] = len(chunks)
            chunk_meta["start_char"] = text.find(chunk)
            result.append({"text": chunk, "metadata": chunk_meta, "chunk_index": idx})
        return result

_chunker = None

def get_chunker() -> DocumentChunker:
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker