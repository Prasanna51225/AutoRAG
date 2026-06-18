from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DocumentChunker:
    def __init__(self, child_size: int = 400, parent_size: int = 1200, overlap: int = 100):
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_size, chunk_overlap=overlap,
            length_function=len, separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_size, chunk_overlap=overlap,
            length_function=len, separators=["\n\n", "\n", ". ", " ", ""]
        )

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # First split into parents
        parents = self.parent_splitter.split_text(text)
        all_children = []
        child_idx = 0
        for p_idx, parent in enumerate(parents):
            children = self.child_splitter.split_text(parent)
            for child in children:
                chunk_meta = (metadata or {}).copy()
                chunk_meta.update({
                    "chunk_index": child_idx,
                    "parent_index": p_idx,
                    "parent_text": parent,
                    "start_char": text.find(child),
                })
                all_children.append({"text": child, "metadata": chunk_meta, "chunk_index": child_idx})
                child_idx += 1
        return all_children

_chunker = None
def get_chunker():
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker