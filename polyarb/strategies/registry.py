"""
Strategy registry for managing and storing strategies.
"""

from typing import List, Optional, Dict, Any
from polyarb.strategies.base import Strategy, StrategyMethod, StrategyType


class StrategyRegistry:
    """
    Registry for managing arbitrage and hedge strategies.
    """
    
    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, Strategy] = {}
    
    def add(self, strategy: Strategy) -> None:
        """
        Add a strategy to the registry.
        
        Args:
            strategy: Strategy to add
        """
        self._strategies[strategy.id] = strategy
    
    def remove(self, strategy_id: str) -> None:
        """
        Remove a strategy from the registry.
        
        Args:
            strategy_id: ID of strategy to remove
        """
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
    
    def get(self, strategy_id: str) -> Optional[Strategy]:
        """
        Get a strategy by ID.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            Strategy or None if not found
        """
        return self._strategies.get(strategy_id)
    
    def get_all(self) -> List[Strategy]:
        """
        Get all strategies in the registry.
        
        Returns:
            List of all strategies
        """
        return list(self._strategies.values())
    
    def filter_by_method(self, method: StrategyMethod) -> List[Strategy]:
        """
        Filter strategies by method.
        
        Args:
            method: Strategy method to filter by
            
        Returns:
            List of strategies with matching method
        """
        return [s for s in self._strategies.values() if s.method == method]
    
    def filter_by_type(self, strategy_type: StrategyType) -> List[Strategy]:
        """
        Filter strategies by type.
        
        Args:
            strategy_type: Strategy type to filter by
            
        Returns:
            List of strategies with matching type
        """
        return [s for s in self._strategies.values() if s.strategy_type == strategy_type]
    
    def filter_by_topic(self, topic: str) -> List[Strategy]:
        """
        Filter strategies by topic.
        
        Args:
            topic: Topic to filter by
            
        Returns:
            List of strategies with matching topic
        """
        return [s for s in self._strategies.values() if s.topic == topic]
    
    def filter_by_tag(self, tag: str) -> List[Strategy]:
        """
        Filter strategies by tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            List of strategies containing the tag
        """
        return [s for s in self._strategies.values() if tag in s.tags]
    
    def filter_by_market(self, market_id: str) -> List[Strategy]:
        """
        Filter strategies involving a specific market.
        
        Args:
            market_id: Market ID
            
        Returns:
            List of strategies involving this market
        """
        return [s for s in self._strategies.values() if market_id in s.get_markets()]
    
    def filter_by_event(self, event_id: str) -> List[Strategy]:
        """
        Filter strategies involving a specific event.
        
        Args:
            event_id: Event ID
            
        Returns:
            List of strategies involving this event
        """
        return [s for s in self._strategies.values() if event_id in s.get_events()]
    
    def get_pure_arbitrage_strategies(self) -> List[Strategy]:
        """
        Get all pure arbitrage strategies (no residual risk).
        
        Returns:
            List of pure arbitrage strategies
        """
        return self.filter_by_type(StrategyType.PURE_LOGICAL)
    
    def count(self) -> int:
        """
        Get total number of strategies in registry.
        
        Returns:
            Number of strategies
        """
        return len(self._strategies)
    
    def clear(self) -> None:
        """Clear all strategies from the registry."""
        self._strategies.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Export registry to dictionary format.
        
        Returns:
            Dictionary representation
        """
        return {
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "method": s.method.value,
                    "type": s.strategy_type.value,
                    "position_count": s.get_position_count(),
                    "markets": s.get_markets(),
                    "events": s.get_events(),
                }
                for s in self._strategies.values()
            ],
            "total_count": self.count()
        }
