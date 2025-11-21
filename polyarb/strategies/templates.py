"""
Template functions for creating common strategy types.
"""

import uuid
from typing import List, Optional
from polyarb.strategies.base import (
    Strategy,
    StrategyMethod,
    StrategyType,
    StrategyPosition,
    LogicalSpec,
)


def create_all_no_strategy(
    name: str,
    subtitle: str,
    positions: List[Dict],
    topic: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Strategy:
    """
    Create an 'all_no' strategy (Dutch-book on mutually exclusive NOs).
    
    This strategy buys NO on a set of mutually exclusive outcomes.
    Exactly one outcome should occur, so exactly one leg loses (pays 0),
    and all others win (pay 1). Total payoff = (n-1) where n = number of legs.
    
    Args:
        name: Strategy name
        subtitle: Short description
        positions: List of position dicts with keys:
            - event_id, event_slug
            - market_id, market_slug
            - outcome_label, outcome_id
            - token_id (NO token)
        topic: Topic/category
        notes: Additional notes
        tags: List of tags
        
    Returns:
        Strategy instance
    """
    strategy_id = str(uuid.uuid4())
    
    # Convert position dicts to StrategyPosition objects
    strategy_positions = []
    for pos_dict in positions:
        strategy_positions.append(
            StrategyPosition(
                event_id=pos_dict["event_id"],
                event_slug=pos_dict["event_slug"],
                market_id=pos_dict["market_id"],
                market_slug=pos_dict["market_slug"],
                outcome_label=pos_dict["outcome_label"],
                outcome_id=pos_dict["outcome_id"],
                token_id=pos_dict["token_id"],
                side="NO",
                price=pos_dict.get("price"),
                size=pos_dict.get("size"),
            )
        )
    
    # Create logical spec
    n = len(strategy_positions)
    logical_spec = LogicalSpec(
        description=(
            f"Buy NO on {n} mutually exclusive outcomes. "
            f"Exactly one outcome occurs, so (n-1) legs win, 1 leg loses. "
            f"Guaranteed payoff = {n-1} if outcomes are truly mutually exclusive."
        ),
        scenarios=[
            {
                "winning_outcome": i,
                "payoff": n - 1,
                "explanation": f"If outcome {i} occurs, all other NO positions win"
            }
            for i in range(n)
        ],
        worst_case_payoff=float(n - 1),
        best_case_payoff=float(n - 1),
    )
    
    return Strategy(
        id=strategy_id,
        name=name,
        subtitle=subtitle,
        method=StrategyMethod.ALL_NO,
        strategy_type=StrategyType.PURE_LOGICAL,
        positions=strategy_positions,
        logical_spec=logical_spec,
        topic=topic,
        notes=notes,
        tags=tags or [],
    )


def create_balanced_strategy(
    name: str,
    subtitle: str,
    side_a_positions: List[Dict],
    side_b_positions: List[Dict],
    strategy_type: StrategyType = StrategyType.PURE_LOGICAL,
    worst_case_payoff: float = 1.0,
    best_case_payoff: float = 1.0,
    topic: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Strategy:
    """
    Create a 'balanced' strategy with two complementary position baskets.
    
    In pure arbitrage: side_a_positions + side_b_positions cover all outcomes
    such that at least one leg always pays 1, and at most one loses.
    
    In hedges: almost all realistic scenarios are covered, with small residual risk.
    
    Args:
        name: Strategy name
        subtitle: Short description
        side_a_positions: List of position dicts for side A
        side_b_positions: List of position dicts for side B
        strategy_type: PURE_LOGICAL or HIGH_PROB_HEDGE
        worst_case_payoff: Minimum guaranteed payoff
        best_case_payoff: Maximum possible payoff
        topic: Topic/category
        notes: Additional notes
        tags: List of tags
        
    Returns:
        Strategy instance
    """
    strategy_id = str(uuid.uuid4())
    
    # Convert side A positions
    side_a = []
    for pos_dict in side_a_positions:
        side_a.append(
            StrategyPosition(
                event_id=pos_dict["event_id"],
                event_slug=pos_dict["event_slug"],
                market_id=pos_dict["market_id"],
                market_slug=pos_dict["market_slug"],
                outcome_label=pos_dict["outcome_label"],
                outcome_id=pos_dict["outcome_id"],
                token_id=pos_dict["token_id"],
                side=pos_dict.get("side", "YES"),
                price=pos_dict.get("price"),
                size=pos_dict.get("size"),
            )
        )
    
    # Convert side B positions
    side_b = []
    for pos_dict in side_b_positions:
        side_b.append(
            StrategyPosition(
                event_id=pos_dict["event_id"],
                event_slug=pos_dict["event_slug"],
                market_id=pos_dict["market_id"],
                market_slug=pos_dict["market_slug"],
                outcome_label=pos_dict["outcome_label"],
                outcome_id=pos_dict["outcome_id"],
                token_id=pos_dict["token_id"],
                side=pos_dict.get("side", "YES"),
                price=pos_dict.get("price"),
                size=pos_dict.get("size"),
            )
        )
    
    # Create logical spec
    logical_spec = LogicalSpec(
        description=(
            f"Balanced strategy with {len(side_a)} positions on side A "
            f"and {len(side_b)} positions on side B. "
            f"{'Pure arbitrage: ' if strategy_type == StrategyType.PURE_LOGICAL else 'Hedge: '}"
            f"at least one position wins in all scenarios."
        ),
        scenarios=[],  # To be filled by LLM or scenario analysis
        worst_case_payoff=worst_case_payoff,
        best_case_payoff=best_case_payoff,
    )
    
    return Strategy(
        id=strategy_id,
        name=name,
        subtitle=subtitle,
        method=StrategyMethod.BALANCED,
        strategy_type=strategy_type,
        side_a_positions=side_a,
        side_b_positions=side_b,
        logical_spec=logical_spec,
        topic=topic,
        notes=notes,
        tags=tags or [],
    )


def create_custom_strategy(
    name: str,
    subtitle: str,
    positions: List[Dict],
    strategy_type: StrategyType = StrategyType.CUSTOM,
    logical_spec: Optional[LogicalSpec] = None,
    topic: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Strategy:
    """
    Create a custom strategy with arbitrary positions.
    
    Args:
        name: Strategy name
        subtitle: Short description
        positions: List of position dicts
        strategy_type: Strategy classification
        logical_spec: Optional logical specification
        topic: Topic/category
        notes: Additional notes
        tags: List of tags
        
    Returns:
        Strategy instance
    """
    strategy_id = str(uuid.uuid4())
    
    # Convert position dicts to StrategyPosition objects
    strategy_positions = []
    for pos_dict in positions:
        strategy_positions.append(
            StrategyPosition(
                event_id=pos_dict["event_id"],
                event_slug=pos_dict["event_slug"],
                market_id=pos_dict["market_id"],
                market_slug=pos_dict["market_slug"],
                outcome_label=pos_dict["outcome_label"],
                outcome_id=pos_dict["outcome_id"],
                token_id=pos_dict["token_id"],
                side=pos_dict.get("side", "YES"),
                price=pos_dict.get("price"),
                size=pos_dict.get("size"),
            )
        )
    
    return Strategy(
        id=strategy_id,
        name=name,
        subtitle=subtitle,
        method=StrategyMethod.CUSTOM,
        strategy_type=strategy_type,
        positions=strategy_positions,
        logical_spec=logical_spec,
        topic=topic,
        notes=notes,
        tags=tags or [],
    )
