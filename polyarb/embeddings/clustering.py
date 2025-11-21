"""
Event clustering for grouping related events.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict


class EventClusterer:
    """
    Clusters events based on embedding similarity.
    """
    
    def __init__(
        self,
        min_similarity: float = 0.8,
        min_cluster_size: int = 2
    ):
        """
        Initialize event clusterer.
        
        Args:
            min_similarity: Minimum similarity for two events to be in same cluster
            min_cluster_size: Minimum number of events in a cluster
        """
        self.min_similarity = min_similarity
        self.min_cluster_size = min_cluster_size
    
    def cluster_events(
        self,
        event_ids: List[str],
        embeddings: np.ndarray,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[int, List[str]]:
        """
        Cluster events using DBSCAN.
        
        Args:
            event_ids: List of event IDs
            embeddings: Array of embeddings (n_events x embedding_dim)
            metadatas: Optional list of metadata dictionaries
            
        Returns:
            Dictionary mapping cluster_id to list of event_ids
            (cluster_id=-1 for noise/outliers)
        """
        if len(event_ids) == 0:
            return {}
        
        # DBSCAN uses epsilon (distance threshold)
        # For cosine similarity, distance = 1 - similarity
        eps = 1 - self.min_similarity
        
        # Run DBSCAN clustering
        clusterer = DBSCAN(
            eps=eps,
            min_samples=self.min_cluster_size,
            metric="cosine"
        )
        labels = clusterer.fit_predict(embeddings)
        
        # Group events by cluster
        clusters = defaultdict(list)
        for event_id, label in zip(event_ids, labels):
            clusters[int(label)].append(event_id)
        
        return dict(clusters)
    
    def find_event_neighbors(
        self,
        event_idx: int,
        embeddings: np.ndarray,
        event_ids: List[str],
        min_similarity: Optional[float] = None
    ) -> List[Tuple[str, float]]:
        """
        Find neighboring events for a given event.
        
        Args:
            event_idx: Index of the query event
            embeddings: Array of embeddings
            event_ids: List of event IDs
            min_similarity: Minimum similarity threshold (uses default if None)
            
        Returns:
            List of (event_id, similarity) tuples for neighbors
        """
        if min_similarity is None:
            min_similarity = self.min_similarity
        
        query_embedding = embeddings[event_idx]
        
        # Compute similarities to all other events
        similarities = np.dot(embeddings, query_embedding)
        
        # Filter by threshold and exclude self
        neighbors = []
        for i, sim in enumerate(similarities):
            if i != event_idx and sim >= min_similarity:
                neighbors.append((event_ids[i], float(sim)))
        
        # Sort by similarity (descending)
        neighbors.sort(key=lambda x: x[1], reverse=True)
        
        return neighbors
    
    def create_similarity_graph(
        self,
        event_ids: List[str],
        embeddings: np.ndarray
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Create a similarity graph where edges connect similar events.
        
        Args:
            event_ids: List of event IDs
            embeddings: Array of embeddings
            
        Returns:
            Dictionary mapping event_id to list of (neighbor_id, similarity) tuples
        """
        graph = {}
        
        for i, event_id in enumerate(event_ids):
            neighbors = self.find_event_neighbors(i, embeddings, event_ids)
            graph[event_id] = neighbors
        
        return graph
    
    def get_cluster_summary(
        self,
        cluster_id: int,
        event_ids: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get summary statistics for a cluster.
        
        Args:
            cluster_id: Cluster ID
            event_ids: List of event IDs in the cluster
            metadatas: List of metadata dictionaries
            
        Returns:
            Summary dictionary
        """
        # Extract metadata for cluster events
        cluster_metadatas = [
            meta for eid, meta in zip(event_ids, metadatas)
        ]
        
        # Compute statistics
        topics = [m.get("topic") for m in cluster_metadatas if m.get("topic")]
        volumes = [float(m.get("volume", 0)) for m in cluster_metadatas]
        
        summary = {
            "cluster_id": cluster_id,
            "size": len(event_ids),
            "event_ids": event_ids,
            "total_volume": sum(volumes),
            "avg_volume": sum(volumes) / len(volumes) if volumes else 0,
            "topics": list(set(topics)),
            "titles": [m.get("title", "") for m in cluster_metadatas],
        }
        
        return summary
    
    def filter_clusters_by_metadata(
        self,
        clusters: Dict[int, List[str]],
        metadatas: Dict[str, Dict[str, Any]],
        filter_fn: callable
    ) -> Dict[int, List[str]]:
        """
        Filter clusters based on metadata criteria.
        
        Args:
            clusters: Dictionary mapping cluster_id to event_ids
            metadatas: Dictionary mapping event_id to metadata
            filter_fn: Function that takes metadata dict and returns True/False
            
        Returns:
            Filtered clusters dictionary
        """
        filtered_clusters = {}
        
        for cluster_id, event_ids in clusters.items():
            # Check if any event in cluster matches filter
            matching_events = [
                eid for eid in event_ids
                if eid in metadatas and filter_fn(metadatas[eid])
            ]
            
            if len(matching_events) >= self.min_cluster_size:
                filtered_clusters[cluster_id] = matching_events
        
        return filtered_clusters
