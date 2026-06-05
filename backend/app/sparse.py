# backend/app/sparse.py
import math
from collections import Counter
from typing import List, Dict, Tuple
import re

class BM25SparseVectorizer:
    """
    Generate sparse vectors (BM25) for hybrid search.
    Uses simple tokenisation and IDF computed on the fly.
    For production, you would precompute IDF from corpus.
    """
    
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.idf = {}  # token -> idf (will be updated as documents are indexed)
        self.doc_count = 0
        self.avg_doc_len = 0
        self.doc_lens = []
    
    def _tokenize(self, text: str) -> List[str]:
        """Basic tokenizer: lowercase, split on non-alphanumeric."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        return tokens
    
    def update_idf(self, texts: List[str]):
        """Update IDF statistics with new documents."""
        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                self.idf[token] = self.idf.get(token, 0) + 1
            self.doc_count += 1
            length = len(self._tokenize(text))
            self.doc_lens.append(length)
        
        self.avg_doc_len = sum(self.doc_lens) / max(self.doc_count, 1)
        # Convert frequencies to idf: log((N - df + 0.5)/(df + 0.5) + 1)
        for token, df in self.idf.items():
            self.idf[token] = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
    
    def vectorize(self, text: str) -> Dict[int, float]:
        """
        Convert text to sparse vector representation.
        Returns dict of token_index -> weight (simulated indices).
        Qdrant expects sparse vectors as dict of index -> value.
        We use a simple hash of token to integer index.
        """
        tokens = self._tokenize(text)
        term_freq = Counter(tokens)
        doc_len = len(tokens)
        
        sparse_vec = {}
        for token, freq in term_freq.items():
            # Compute BM25 weight
            idf = self.idf.get(token, math.log((self.doc_count + 0.5) / 0.5 + 1))
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
            weight = idf * (numerator / denominator)
            
            # Use a simple hash as index (0..2^31-1)
            idx = hash(token) & 0x7FFFFFFF
            sparse_vec[idx] = weight
        
        return sparse_vec

# Singleton
_sparse_vectorizer = None

def get_sparse_vectorizer() -> BM25SparseVectorizer:
    global _sparse_vectorizer
    if _sparse_vectorizer is None:
        _sparse_vectorizer = BM25SparseVectorizer()
    return _sparse_vectorizer