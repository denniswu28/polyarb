"""
Event embedding using sentence transformers.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer


class EventEmbedder:
    """
    Embeds events using sentence transformer models.
    """
    
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None
    ):
        """
        Initialize event embedder.
        
        Args:
            model_name: Sentence transformer model name
            device: Device to run on ('cuda', 'cpu', or None for auto)
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
    
    def embed_event(self, event: Dict[str, Any]) -> np.ndarray:
        """
        Embed a single event.
        
        Args:
            event: Event dictionary with 'title', 'description', etc.
            
        Returns:
            Embedding vector as numpy array
        """
        text = self._event_to_text(event)
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding
    
    def embed_events_batch(
        self, 
        events: List[Dict[str, Any]],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Embed multiple events in batches.
        
        Args:
            events: List of event dictionaries
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar
            
        Returns:
            Array of embeddings (n_events x embedding_dim)
        """
        texts = [self._event_to_text(event) for event in events]
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True
        )
        return embeddings
    
    def _event_to_text(self, event: Dict[str, Any]) -> str:
        """
        Convert event to text for embedding.
        
        Combines title, ticker, and optionally description.
        
        Args:
            event: Event dictionary
            
        Returns:
            Text representation
        """
        parts = []
        
        # Add title (most important)
        title = event.get("title", "")
        if title:
            parts.append(title)
        
        # Add ticker if different from title
        ticker = event.get("ticker", "")
        if ticker and ticker.lower() not in title.lower():
            parts.append(ticker)
        
        # Optionally add short description (first 200 chars)
        description = event.get("description", "")
        if description:
            parts.append(description[:200])
        
        return " | ".join(parts)
    
    def compute_similarity(
        self, 
        embedding1: np.ndarray, 
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity (0 to 1)
        """
        # Embeddings are already normalized, so dot product = cosine similarity
        return float(np.dot(embedding1, embedding2))
    
    def find_similar_events(
        self,
        query_embedding: np.ndarray,
        event_embeddings: np.ndarray,
        event_ids: List[str],
        top_k: int = 10,
        min_similarity: float = 0.8
    ) -> List[tuple[str, float]]:
        """
        Find most similar events to a query embedding.
        
        Args:
            query_embedding: Query embedding vector
            event_embeddings: Array of event embeddings
            event_ids: List of event IDs corresponding to embeddings
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (event_id, similarity) tuples
        """
        # Compute similarities
        similarities = np.dot(event_embeddings, query_embedding)
        
        # Filter by threshold
        valid_indices = np.where(similarities >= min_similarity)[0]
        
        if len(valid_indices) == 0:
            return []
        
        # Get top-k
        top_indices = valid_indices[np.argsort(-similarities[valid_indices])[:top_k]]
        
        results = [
            (event_ids[i], float(similarities[i]))
            for i in top_indices
        ]
        
        return results
