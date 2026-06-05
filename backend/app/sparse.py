# backend/app/sparse.py
import math
from collections import Counter
from typing import List, Dict, Optional
import re
from app.utils import get_logger

logger = get_logger(__name__)

class BM25SparseVectorizer:
    """
    Generate sparse vectors (BM25) for hybrid search.
    Handles empty corpus gracefully – returns empty vector when no docs exist.
    """
    
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.idf = {}
        self.doc_count = 0
        self.avg_doc_len = 0.0
        self.doc_lens = []
        logger.info("BM25SparseVectorizer initialized (empty corpus)")
    
    def _tokenize(self, text: str) -> List[str]:
        """Basic tokenizer: lowercase, split on non-alphanumeric."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        return tokens
    
    def update_idf(self, texts: List[str]):
        """Update IDF statistics with new documents."""
        if not texts:
            return
        
        doc_freq = {}
        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1
            self.doc_count += 1
            length = len(self._tokenize(text))
            self.doc_lens.append(length)
        
        for token, df in doc_freq.items():
            self.idf[token] = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
        
        if self.doc_lens:
            self.avg_doc_len = sum(self.doc_lens) / len(self.doc_lens)
        else:
            self.avg_doc_len = 0.0
        
        logger.info(f"BM25 updated: doc_count={self.doc_count}, avg_doc_len={self.avg_doc_len:.2f}")
    
    def vectorize(self, text: str) -> Dict[int, float]:
        """
        Convert text to sparse vector.
        Returns empty dict if no documents have been indexed yet.
        """
        # CRITICAL FIX: Guard against division by zero
        if self.doc_count == 0 or self.avg_doc_len == 0:
            logger.debug("No documents ingested yet – returning empty sparse vector")
            return {}
        
        tokens = self._tokenize(text)
        term_freq = Counter(tokens)
        doc_len = len(tokens)
        
        sparse_vec = {}
        for token, freq in term_freq.items():
            idf = self.idf.get(token, math.log((self.doc_count + 0.5) / 0.5 + 1))
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
            weight = idf * (numerator / denominator)
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