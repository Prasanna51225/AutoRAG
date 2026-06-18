# backend/app/qdrant_client.py
import asyncio
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class QdrantManager:
    """Singleton manager for Qdrant client and collection setup."""

    def __init__(self):
        self.client = None
        self.collection_name = "documents"
        self._init_client()

    def _init_client(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            prefer_grpc=False,
            timeout=30,
        )
        logger.info(f"Qdrant client created for {settings.qdrant_host}:{settings.qdrant_port}")

    async def ensure_collection(self, dense_dimension: int):
        """Create collection if it doesn't exist, with dense + sparse vectors."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return

        logger.info(f"Creating collection '{self.collection_name}' with dense dim={dense_dimension}")

        dense_config = models.VectorParams(
            size=dense_dimension,
            distance=models.Distance.COSINE,
        )
        sparse_config = models.SparseVectorParams(
            index=models.SparseIndexParams(on_disk=False)
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={"dense": dense_config},
            sparse_vectors_config={"sparse": sparse_config},
        )
        logger.info("Collection created successfully")

    async def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        dense_embeddings: List[List[float]],
        sparse_vectors: List[Dict[int, float]],
    ):
        if not chunks:
            return

        points = []
        for idx, (chunk, dense_vec, sparse_vec) in enumerate(zip(chunks, dense_embeddings, sparse_vectors)):
            point_id = f"{chunk['metadata'].get('source_id', 'unknown')}_{chunk['chunk_index']}"
            try:
                point_id_int = hash(point_id) & 0x7FFFFFFF
            except Exception:
                point_id_int = idx

            points.append(
                models.PointStruct(
                    id=point_id_int,
                    vector={
                        "dense": dense_vec,
                        "sparse": models.SparseVector(
                            indices=list(sparse_vec.keys()),
                            values=list(sparse_vec.values()),
                        ),
                    },
                    payload={
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                    },
                )
            )

        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )
        logger.info(f"Upserted {len(points)} chunks to Qdrant")

    def search_dense(self, query_vector: List[float], limit: int = 20):
        """
        Dense-only search using named vector.
        Used by the retriever as the primary path (hybrid not yet stable in all
        qdrant-client versions; sparse scoring is applied via the reranker).
        """
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedVector(name="dense", vector=query_vector),
            limit=limit,
            with_payload=True,
        )
        return results

    def search_hybrid(
        self,
        query_dense: List[float],
        query_sparse: Dict[int, float],
        limit: int = 20,
    ):
        """
        Hybrid search (dense + sparse) using qdrant-client ≥1.7 query API.
        FIX: The old .search() with query_sparse_vector= was removed in newer
        qdrant-client versions. Use query_points() with prefetch instead.
        Falls back to dense-only if sparse vector is empty (first ingest).
        """
        if not query_sparse:
            return self.search_dense(query_dense, limit)

        from qdrant_client.models import (
            Prefetch,
            FusionQuery,
            Fusion,
            SparseVector,
            NamedSparseVector,
            NamedVector,
        )

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    Prefetch(
                        query=NamedVector(name="dense", vector=query_dense),
                        limit=limit * 2,
                    ),
                    Prefetch(
                        query=NamedSparseVector(
                            name="sparse",
                            vector=SparseVector(
                                indices=list(query_sparse.keys()),
                                values=list(query_sparse.values()),
                            ),
                        ),
                        limit=limit * 2,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
            return results.points
        except Exception as e:
            logger.warning(f"Hybrid search failed ({e}), falling back to dense-only")
            return self.search_dense(query_dense, limit)


_qdrant_manager = None

def get_qdrant_manager() -> QdrantManager:
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager
# backend/app/qdrant_client.py
import asyncio
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class QdrantManager:
    """Singleton manager for Qdrant client and collection setup."""

    def __init__(self):
        self.client = None
        self.collection_name = "documents"
        self._init_client()

    def _init_client(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            prefer_grpc=False,
            timeout=30,
        )
        logger.info(f"Qdrant client created for {settings.qdrant_host}:{settings.qdrant_port}")

    async def ensure_collection(self, dense_dimension: int):
        """Create collection if it doesn't exist, with dense + sparse vectors."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return

        logger.info(f"Creating collection '{self.collection_name}' with dense dim={dense_dimension}")

        dense_config = models.VectorParams(
            size=dense_dimension,
            distance=models.Distance.COSINE,
        )
        sparse_config = models.SparseVectorParams(
            index=models.SparseIndexParams(on_disk=False)
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={"dense": dense_config},
            sparse_vectors_config={"sparse": sparse_config},
        )
        logger.info("Collection created successfully")

    async def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        dense_embeddings: List[List[float]],
        sparse_vectors: List[Dict[int, float]],
    ):
        if not chunks:
            return

        points = []
        for idx, (chunk, dense_vec, sparse_vec) in enumerate(zip(chunks, dense_embeddings, sparse_vectors)):
            point_id = f"{chunk['metadata'].get('source_id', 'unknown')}_{chunk['chunk_index']}"
            try:
                point_id_int = hash(point_id) & 0x7FFFFFFF
            except Exception:
                point_id_int = idx

            points.append(
                models.PointStruct(
                    id=point_id_int,
                    vector={
                        "dense": dense_vec,
                        "sparse": models.SparseVector(
                            indices=list(sparse_vec.keys()),
                            values=list(sparse_vec.values()),
                        ),
                    },
                    payload={
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                    },
                )
            )

        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )
        logger.info(f"Upserted {len(points)} chunks to Qdrant")

    def search_dense(self, query_vector: List[float], limit: int = 20):
        """
        Dense-only search using named vector.
        Used by the retriever as the primary path (hybrid not yet stable in all
        qdrant-client versions; sparse scoring is applied via the reranker).
        """
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedVector(name="dense", vector=query_vector),
            limit=limit,
            with_payload=True,
        )
        return results

    def search_hybrid(
        self,
        query_dense: List[float],
        query_sparse: Dict[int, float],
        limit: int = 20,
    ):
        """
        Hybrid search (dense + sparse) using qdrant-client ≥1.7 query API.
        FIX: The old .search() with query_sparse_vector= was removed in newer
        qdrant-client versions. Use query_points() with prefetch instead.
        Falls back to dense-only if sparse vector is empty (first ingest).
        """
        if not query_sparse:
            return self.search_dense(query_dense, limit)

        from qdrant_client.models import (
            Prefetch,
            FusionQuery,
            Fusion,
            SparseVector,
            NamedSparseVector,
            NamedVector,
        )

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    Prefetch(
                        query=NamedVector(name="dense", vector=query_dense),
                        limit=limit * 2,
                    ),
                    Prefetch(
                        query=NamedSparseVector(
                            name="sparse",
                            vector=SparseVector(
                                indices=list(query_sparse.keys()),
                                values=list(query_sparse.values()),
                            ),
                        ),
                        limit=limit * 2,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
            return results.points
        except Exception as e:
            logger.warning(f"Hybrid search failed ({e}), falling back to dense-only")
            return self.search_dense(query_dense, limit)


_qdrant_manager = None

def get_qdrant_manager() -> QdrantManager:
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager
