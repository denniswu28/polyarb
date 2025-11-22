"""
LLM-based dependency detection for discovering logical relationships between markets.

This module uses LLMs to analyze markets and identify dependencies,
contradictions, and logical relationships that enable combinatorial arbitrage.
"""

from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime, timedelta


class DependencyDetector:
    """
    Detects logical dependencies between markets using LLM analysis.
    
    Note: This is a framework class. In production, you would integrate
    with an actual LLM API (OpenAI, Anthropic, etc.).
    """
    
    def __init__(
        self,
        max_outcomes_per_market: int = 4,
        llm_client: Optional[Any] = None
    ):
        """
        Initialize dependency detector.
        
        Args:
            max_outcomes_per_market: Max outcomes to consider per market (rest aggregated)
            llm_client: Optional LLM client instance
        """
        self.max_outcomes_per_market = max_outcomes_per_market
        self.llm_client = llm_client
    
    def analyze_market_pair(
        self,
        market1: Dict[str, Any],
        market2: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze two markets for logical dependencies.
        
        Args:
            market1: First market dictionary
            market2: Second market dictionary
            
        Returns:
            Dependency analysis result or None if no dependency
        """
        # Check basic compatibility
        if not self._are_markets_compatible(market1, market2):
            return None
        
        # Reduce outcomes to top K by volume
        outcomes1 = self._reduce_outcomes(market1)
        outcomes2 = self._reduce_outcomes(market2)
        
        # Generate outcome compatibility table via LLM
        outcome_table = self._generate_outcome_table(
            market1, outcomes1,
            market2, outcomes2
        )
        
        if not outcome_table:
            return None
        
        # Analyze the outcome table for arbitrage opportunities
        dependencies = self._analyze_outcome_table(
            outcome_table,
            market1, outcomes1,
            market2, outcomes2
        )
        
        return dependencies
    
    def _are_markets_compatible(
        self,
        market1: Dict[str, Any],
        market2: Dict[str, Any]
    ) -> bool:
        """
        Check if two markets are compatible for dependency analysis.
        
        Markets should:
        - Be from same topic/category
        - Have similar end dates
        - Share key entities (candidates, teams, etc.)
        """
        # Check end dates are within reasonable range (e.g., 7 days)
        end1 = market1.get("end_date")
        end2 = market2.get("end_date")
        
        if end1 and end2:
            # Parse dates if strings
            if isinstance(end1, str):
                end1 = datetime.fromisoformat(end1.replace("Z", "+00:00"))
            if isinstance(end2, str):
                end2 = datetime.fromisoformat(end2.replace("Z", "+00:00"))
            
            if abs((end1 - end2).days) > 7:
                return False
        
        # Check for topic similarity (if available)
        topic1 = market1.get("topic", "").lower()
        topic2 = market2.get("topic", "").lower()
        
        if topic1 and topic2 and topic1 != topic2:
            return False
        
        return True
    
    def _reduce_outcomes(self, market: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Reduce outcomes to top K by volume, aggregate rest as "Other".
        
        Args:
            market: Market dictionary
            
        Returns:
            List of reduced outcomes
        """
        outcomes = market.get("outcomes", [])
        
        if len(outcomes) <= self.max_outcomes_per_market:
            return outcomes
        
        # Sort by volume (if available) or keep top K
        sorted_outcomes = sorted(
            outcomes,
            key=lambda x: float(x.get("volume", 0)),
            reverse=True
        )
        
        top_outcomes = sorted_outcomes[:self.max_outcomes_per_market]
        
        # Add "Other outcomes" aggregation
        other_outcomes = sorted_outcomes[self.max_outcomes_per_market:]
        if other_outcomes:
            top_outcomes.append({
                "label": "Other outcomes",
                "aggregated": True,
                "original_count": len(other_outcomes)
            })
        
        return top_outcomes
    
    def _generate_outcome_table(
        self,
        market1: Dict[str, Any],
        outcomes1: List[Dict[str, Any]],
        market2: Dict[str, Any],
        outcomes2: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generate outcome compatibility table using LLM.
        
        This asks the LLM: "Given these two markets, which combinations
        of outcomes are logically possible?"
        
        Args:
            market1: First market
            outcomes1: Reduced outcomes for market 1
            market2: Second market
            outcomes2: Reduced outcomes for market 2
            
        Returns:
            List of valid outcome combinations, or None
        """
        # If no LLM client, return all combinations (conservative)
        if not self.llm_client:
            return self._generate_all_combinations(outcomes1, outcomes2)
        
        # Prepare prompt for LLM
        prompt = self._create_outcome_table_prompt(
            market1, outcomes1,
            market2, outcomes2
        )
        
        # Call LLM (placeholder - implement with actual LLM API)
        try:
            # response = self.llm_client.complete(prompt)
            # outcome_table = self._parse_llm_response(response)
            # return outcome_table
            
            # For now, return all combinations
            return self._generate_all_combinations(outcomes1, outcomes2)
        except Exception:
            return None
    
    def _generate_all_combinations(
        self,
        outcomes1: List[Dict[str, Any]],
        outcomes2: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate all possible outcome combinations (conservative fallback)."""
        combinations = []
        
        for o1 in outcomes1:
            for o2 in outcomes2:
                combinations.append({
                    "market1_outcome": o1.get("label", ""),
                    "market2_outcome": o2.get("label", ""),
                    "valid": True
                })
        
        return combinations
    
    def _create_outcome_table_prompt(
        self,
        market1: Dict[str, Any],
        outcomes1: List[Dict[str, Any]],
        market2: Dict[str, Any],
        outcomes2: List[Dict[str, Any]]
    ) -> str:
        """Create LLM prompt for outcome table generation."""
        return f"""
Given these two prediction markets, identify all logically valid combinations of outcomes.

Market 1: {market1.get('question', '')}
Outcomes: {', '.join(o.get('label', '') for o in outcomes1)}

Market 2: {market2.get('question', '')}
Outcomes: {', '.join(o.get('label', '') for o in outcomes2)}

For each valid combination, output a JSON object with:
- market1_outcome: outcome from market 1
- market2_outcome: outcome from market 2
- explanation: why this combination is possible

Only include combinations that are logically possible given the market descriptions.
Output as a JSON array.
"""
    
    def _analyze_outcome_table(
        self,
        outcome_table: List[Dict[str, Any]],
        market1: Dict[str, Any],
        outcomes1: List[Dict[str, Any]],
        market2: Dict[str, Any],
        outcomes2: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze outcome table for arbitrage opportunities.
        
        Looks for:
        - Equivalences: outcome A in M1 <=> outcome B in M2
        - Implications: outcome A in M1 => outcome B in M2
        - Mutual exclusions that create balanced strategies
        """
        n1 = len(outcomes1)
        n2 = len(outcomes2)
        total_possible = n1 * n2
        valid_combinations = len([c for c in outcome_table if c.get("valid", True)])
        
        # If all combinations are valid, markets are independent
        if valid_combinations == total_possible:
            return None
        
        # Detect dependency type
        dependency = {
            "type": "dependent",
            "market1_id": market1.get("id"),
            "market2_id": market2.get("id"),
            "valid_combinations": valid_combinations,
            "total_possible": total_possible,
            "dependency_strength": 1 - (valid_combinations / total_possible),
            "outcome_table": outcome_table,
        }
        
        # Check for specific patterns (equivalences, implications)
        # This would require more sophisticated analysis
        
        return dependency
