"""
Embedding & Dependency Detection Module.

This module provides event embedding, clustering, similarity search,
and LLM-based dependency detection for combinatorial arbitrage discovery.
"""

from polyarb.embeddings.event_embedder import EventEmbedder
from polyarb.embeddings.vector_store import VectorStore
from polyarb.embeddings.clustering import EventClusterer
from polyarb.embeddings.dependency_detector import DependencyDetector

__all__ = [
    "EventEmbedder",
    "VectorStore",
    "EventClusterer",
    "DependencyDetector",
]
