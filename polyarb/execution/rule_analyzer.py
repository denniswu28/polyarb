"""
LLM-based rule risk analyzer for market rules.
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class RuleRiskCategory(str, Enum):
    """Categories of rule risk."""
    LOW = "low"  # Clear, unambiguous rules
    MEDIUM = "medium"  # Some interpretation needed
    HIGH = "high"  # Significant discretion or ambiguity
    CRITICAL = "critical"  # Path-dependent or void conditions


class RuleRiskAnalyzer:
    """
    Analyzes market rules for resolution risk using LLM.
    
    Note: This is a framework class. In production, integrate with actual LLM API.
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize rule risk analyzer.
        
        Args:
            llm_client: Optional LLM client for analysis
        """
        self.llm_client = llm_client
        
        # Known risk patterns (can be expanded)
        self.high_risk_keywords = [
            "replacement",
            "substitution",
            "void",
            "cancel",
            "discretion",
            "interpretation",
            "dispute",
            "unclear",
        ]
        
        self.medium_risk_keywords = [
            "before",
            "after",
            "timing",
            "announcement",
            "official",
            "certification",
        ]
    
    def analyze_market_rules(
        self,
        market: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze market rules for resolution risk.
        
        Args:
            market: Market dictionary with 'rules' field
            
        Returns:
            Analysis result with risk category and notes
        """
        rules = market.get("rules", "")
        question = market.get("question", "")
        
        if not rules and not question:
            return {
                "risk_category": RuleRiskCategory.MEDIUM,
                "risk_score": 0.5,
                "notes": ["No rules provided"],
                "flags": []
            }
        
        # If LLM available, use it for analysis
        if self.llm_client:
            return self._llm_analyze(market)
        
        # Fallback to keyword-based analysis
        return self._keyword_analyze(rules, question)
    
    def _keyword_analyze(
        self,
        rules: str,
        question: str
    ) -> Dict[str, Any]:
        """
        Simple keyword-based rule risk analysis.
        
        Args:
            rules: Market rules text
            question: Market question
            
        Returns:
            Analysis result
        """
        text = (rules + " " + question).lower()
        
        flags = []
        risk_score = 0.2  # Base risk
        
        # Check for high-risk patterns
        for keyword in self.high_risk_keywords:
            if keyword in text:
                flags.append(f"High-risk keyword: {keyword}")
                risk_score += 0.15
        
        # Check for medium-risk patterns
        for keyword in self.medium_risk_keywords:
            if keyword in text:
                flags.append(f"Medium-risk keyword: {keyword}")
                risk_score += 0.05
        
        # Determine category
        if risk_score >= 0.7:
            category = RuleRiskCategory.HIGH
        elif risk_score >= 0.4:
            category = RuleRiskCategory.MEDIUM
        else:
            category = RuleRiskCategory.LOW
        
        notes = []
        if not flags:
            notes.append("No obvious risk patterns detected")
        
        return {
            "risk_category": category,
            "risk_score": min(risk_score, 1.0),
            "notes": notes,
            "flags": flags
        }
    
    def _llm_analyze(self, market: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM-based rule risk analysis.
        
        This would call an LLM to analyze the market rules and return:
        - Risk category
        - Specific concerns
        - Recommended actions
        
        Args:
            market: Market dictionary
            
        Returns:
            Analysis result
        """
        rules = market.get("rules", "")
        question = market.get("question", "")
        
        prompt = f"""
Analyze the following prediction market for resolution risk:

Question: {question}

Rules: {rules}

Identify any of the following risk factors:
1. Candidate replacement or substitution clauses
2. Void or cancellation conditions
3. Timing ambiguities
4. Discretionary resolution
5. Path-dependent outcomes
6. Unclear or contradictory rules

Provide:
- Risk category (LOW, MEDIUM, HIGH, CRITICAL)
- Specific risk factors identified
- Recommendations for arbitrage traders

Output as JSON.
"""
        
        # Placeholder for actual LLM call
        # response = self.llm_client.complete(prompt)
        # return self._parse_llm_response(response)
        
        # Fallback to keyword analysis
        return self._keyword_analyze(rules, question)
    
    def batch_analyze_markets(
        self,
        markets: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze multiple markets for rule risk.
        
        Args:
            markets: List of market dictionaries
            
        Returns:
            Dictionary mapping market_id to analysis result
        """
        results = {}
        
        for market in markets:
            market_id = market.get("id")
            if market_id:
                results[market_id] = self.analyze_market_rules(market)
        
        return results
    
    def filter_by_risk_level(
        self,
        markets: List[Dict[str, Any]],
        max_risk_category: RuleRiskCategory = RuleRiskCategory.MEDIUM
    ) -> List[Dict[str, Any]]:
        """
        Filter markets by maximum acceptable rule risk.
        
        Args:
            markets: List of markets
            max_risk_category: Maximum acceptable risk category
            
        Returns:
            Filtered list of markets
        """
        risk_order = {
            RuleRiskCategory.LOW: 0,
            RuleRiskCategory.MEDIUM: 1,
            RuleRiskCategory.HIGH: 2,
            RuleRiskCategory.CRITICAL: 3,
        }
        
        max_risk_value = risk_order[max_risk_category]
        
        filtered = []
        for market in markets:
            analysis = self.analyze_market_rules(market)
            risk_category = analysis["risk_category"]
            
            if risk_order[risk_category] <= max_risk_value:
                filtered.append(market)
        
        return filtered
