"""
Vector store using ChromaDB for event similarity search.
"""

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
import numpy as np


class VectorStore:
    """
    Vector store for event embeddings using ChromaDB.
    """
    
    def __init__(
        self,
        collection_name: str = "events",
        persist_directory: Optional[str] = None,
        distance_metric: str = "cosine"
    ):
        """
        Initialize vector store.
        
        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist data (None for in-memory)
            distance_metric: Distance metric ('cosine', 'l2', 'ip')
        """
        self.collection_name = collection_name
        
        if persist_directory:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        else:
            self.client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False)
            )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": distance_metric}
        )
    
    def add_events(
        self,
        event_ids: List[str],
        embeddings: List[np.ndarray],
        metadatas: List[Dict[str, Any]],
        documents: Optional[List[str]] = None
    ) -> None:
        """
        Add events to the vector store.
        
        Args:
            event_ids: List of event IDs
            embeddings: List of embedding vectors
            metadatas: List of metadata dictionaries
            documents: Optional list of text documents
        """
        # Convert numpy arrays to lists for ChromaDB
        embeddings_list = [emb.tolist() if isinstance(emb, np.ndarray) else emb 
                          for emb in embeddings]
        
        if documents is None:
            documents = [meta.get("title", "") for meta in metadatas]
        
        self.collection.add(
            ids=event_ids,
            embeddings=embeddings_list,
            metadatas=metadatas,
            documents=documents
        )
    
    def add_event(
        self,
        event_id: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any],
        document: Optional[str] = None
    ) -> None:
        """
        Add a single event to the vector store.
        
        Args:
            event_id: Event ID
            embedding: Embedding vector
            metadata: Metadata dictionary
            document: Optional text document
        """
        self.add_events(
            event_ids=[event_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document] if document else None
        )
    
    def query_similar(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_similarity: Optional[float] = None,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List]:
        """
        Query for similar events.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (for cosine distance)
            where_filter: Optional metadata filter
            
        Returns:
            Dictionary with 'ids', 'distances', 'metadatas', 'documents'
        """
        query_list = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
        
        results = self.collection.query(
            query_embeddings=[query_list],
            n_results=top_k,
            where=where_filter
        )
        
        # Filter by similarity if specified (for cosine distance)
        if min_similarity is not None:
            filtered_results = {
                "ids": [],
                "distances": [],
                "metadatas": [],
                "documents": []
            }
            
            for i, distance in enumerate(results["distances"][0]):
                # Convert distance to similarity (ChromaDB returns distances)
                # For cosine: distance = 1 - similarity, so similarity = 1 - distance
                similarity = 1 - distance
                
                if similarity >= min_similarity:
                    filtered_results["ids"].append(results["ids"][0][i])
                    filtered_results["distances"].append(distance)
                    filtered_results["metadatas"].append(results["metadatas"][0][i])
                    if results.get("documents"):
                        filtered_results["documents"].append(results["documents"][0][i])
            
            return filtered_results
        
        # Return first query results (ChromaDB returns list of results for batch queries)
        return {
            "ids": results["ids"][0],
            "distances": results["distances"][0],
            "metadatas": results["metadatas"][0],
            "documents": results.get("documents", [[]])[0]
        }
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get event by ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            Event data or None if not found
        """
        results = self.collection.get(ids=[event_id])
        
        if results["ids"]:
            return {
                "id": results["ids"][0],
                "metadata": results["metadatas"][0],
                "document": results.get("documents", [None])[0]
            }
        
        return None
    
    def delete_event(self, event_id: str) -> None:
        """
        Delete event by ID.
        
        Args:
            event_id: Event ID
        """
        self.collection.delete(ids=[event_id])
    
    def count(self) -> int:
        """
        Get number of events in the store.
        
        Returns:
            Number of events
        """
        return self.collection.count()
    
    def clear(self) -> None:
        """Clear all events from the store."""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def exists(self, event_id: str) -> bool:
        """
        Check if event exists in the store.
        
        Args:
            event_id: Event ID
            
        Returns:
            True if event exists
        """
        results = self.collection.get(ids=[event_id])
        return len(results["ids"]) > 0
