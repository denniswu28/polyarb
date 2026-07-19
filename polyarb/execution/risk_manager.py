"""Risk approval limits with aggregate exposure reservations."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from polyarb.core.lifecycle import LifecycleState
from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, RiskLevel


@dataclass
class RiskLimits:
    """Risk limits configuration."""

    # Notional limits
    max_total_notional: float = 10000.0
    max_per_strategy_notional: float = 2000.0
    max_per_market_notional: float = 1000.0
    max_per_topic_notional: float = 3000.0

    # Position limits
    max_positions: int = 50
    max_positions_per_market: int = 5

    # Quality limits
    min_profit_threshold: float = 0.5
    max_rule_risk_exposure: float = 2000.0

    # Execution limits
    max_slippage_tolerance: float = 50
    min_liquidity_score: float = 0.3

    def __post_init__(self) -> None:
        if self.max_slippage_tolerance < 0:
            raise ValueError("max_slippage_tolerance must be non-negative")


class RiskManager:
    """Apply research limits and reserve approved aggregate exposure."""

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()

        # Positions are materialized records; approvals are reservations. Aggregate
        # exposure dictionaries include both so repeated approvals cannot exceed caps.
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.approvals: Dict[str, Dict[str, Any]] = {}
        self.strategy_exposures: Dict[str, float] = {}
        self.market_exposures: Dict[str, float] = {}
        self.topic_exposures: Dict[str, float] = {}
        self.total_notional = 0.0
        self.total_rule_risk_exposure = 0.0

    @staticmethod
    def _proposal(opportunity: EnhancedOpportunity, size: float) -> Dict[str, Any]:
        """Build an exposure reservation whose market allocations sum to notional."""
        total_notional = max(0.0, opportunity.total_cost * size)
        raw_market_costs: Dict[str, float] = {}
        market_position_counts: Dict[str, int] = {}

        for leg in opportunity.legs:
            raw_market_costs[leg.market_id] = (
                raw_market_costs.get(leg.market_id, 0.0) + max(0.0, leg.price * size)
            )
            market_position_counts[leg.market_id] = (
                market_position_counts.get(leg.market_id, 0) + 1
            )

        if not raw_market_costs and opportunity.market_ids:
            unique_markets = list(dict.fromkeys(opportunity.market_ids))
            raw_market_costs = {market_id: 1.0 for market_id in unique_markets}

        raw_total = sum(raw_market_costs.values())
        if raw_total > 0:
            market_exposures = {
                market_id: total_notional * raw_cost / raw_total
                for market_id, raw_cost in raw_market_costs.items()
            }
        else:
            market_exposures = {market_id: 0.0 for market_id in raw_market_costs}

        return {
            "opportunity_id": opportunity.id,
            "opportunity": opportunity,
            "size": size,
            "total_notional": total_notional,
            "position_count": len(opportunity.legs),
            "market_exposures": market_exposures,
            "market_position_counts": market_position_counts,
            "strategy_id": opportunity.strategy_id,
            "topic": opportunity.topic,
            "high_rule_risk": opportunity.risk_level == RiskLevel.HIGH,
        }

    def _reserved_position_count(self, market_id: Optional[str] = None) -> int:
        if market_id is None:
            return sum(item["position_count"] for item in self.approvals.values())
        return sum(
            item["market_position_counts"].get(market_id, 0)
            for item in self.approvals.values()
        )

    def _open_position_count(self, market_id: Optional[str] = None) -> int:
        if market_id is None:
            return len(self.positions)
        return sum(
            1 for position in self.positions.values()
            if position.get("market_id") == market_id
        )

    @staticmethod
    def _update_bucket(bucket: Dict[str, float], key: Optional[str], delta: float) -> None:
        if not key:
            return
        updated = bucket.get(key, 0.0) + delta
        if abs(updated) < 1e-12:
            bucket.pop(key, None)
        else:
            bucket[key] = updated

    def _adjust_aggregates(self, proposal: Dict[str, Any], direction: float) -> None:
        delta = direction * proposal["total_notional"]
        self.total_notional += delta
        self._update_bucket(
            self.strategy_exposures,
            proposal.get("strategy_id"),
            delta,
        )
        self._update_bucket(self.topic_exposures, proposal.get("topic"), delta)
        for market_id, value in proposal["market_exposures"].items():
            self._update_bucket(self.market_exposures, market_id, direction * value)
        if proposal.get("high_rule_risk"):
            self.total_rule_risk_exposure += delta

    def check_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        proposed_size: float,
    ) -> tuple[bool, List[str]]:
        """Check a proposed approval against positions and prior reservations."""
        violations: List[str] = []

        if opportunity.id in self.approvals:
            violations.append(f"Opportunity {opportunity.id} is already approved")
        if proposed_size <= 0:
            violations.append("Proposed size must be positive")
        if opportunity.max_size is not None and proposed_size > opportunity.max_size:
            violations.append(
                f"Proposed size {proposed_size:.2f} exceeds liquidity-constrained "
                f"maximum {opportunity.max_size:.2f}"
            )
        if opportunity.profit_percentage < self.limits.min_profit_threshold:
            violations.append(
                f"Modeled edge {opportunity.profit_percentage:.2f}% below threshold "
                f"{self.limits.min_profit_threshold:.2f}%"
            )

        proposal = self._proposal(opportunity, max(0.0, proposed_size))
        proposed_total = self.total_notional + proposal["total_notional"]
        if proposed_total > self.limits.max_total_notional:
            violations.append(
                f"Would exceed max total notional: {proposed_total:.2f} > "
                f"{self.limits.max_total_notional:.2f}"
            )

        strategy_id = proposal.get("strategy_id")
        if strategy_id:
            strategy_total = (
                self.strategy_exposures.get(strategy_id, 0.0)
                + proposal["total_notional"]
            )
            if strategy_total > self.limits.max_per_strategy_notional:
                violations.append(f"Would exceed per-strategy limit for {strategy_id}")

        for market_id, proposed_exposure in proposal["market_exposures"].items():
            market_total = self.market_exposures.get(market_id, 0.0) + proposed_exposure
            if market_total > self.limits.max_per_market_notional:
                violations.append(f"Would exceed per-market limit for {market_id}")

            market_positions = (
                self._open_position_count(market_id)
                + self._reserved_position_count(market_id)
                + proposal["market_position_counts"].get(market_id, 0)
            )
            if market_positions > self.limits.max_positions_per_market:
                violations.append(f"Would exceed position-count limit for {market_id}")

        topic = proposal.get("topic")
        if topic:
            topic_total = self.topic_exposures.get(topic, 0.0) + proposal["total_notional"]
            if topic_total > self.limits.max_per_topic_notional:
                violations.append(f"Would exceed per-topic limit for {topic}")

        if proposal.get("high_rule_risk"):
            rule_risk_total = self.total_rule_risk_exposure + proposal["total_notional"]
            if rule_risk_total > self.limits.max_rule_risk_exposure:
                violations.append("Would exceed rule risk exposure limit")

        if (
            opportunity.liquidity_score is not None
            and opportunity.liquidity_score < self.limits.min_liquidity_score
        ):
            violations.append(
                f"Liquidity score {opportunity.liquidity_score:.2f} below minimum "
                f"{self.limits.min_liquidity_score:.2f}"
            )

        aggregate_positions = (
            self._open_position_count()
            + self._reserved_position_count()
            + proposal["position_count"]
        )
        if aggregate_positions > self.limits.max_positions:
            violations.append(
                f"Would exceed max positions limit: {aggregate_positions} > "
                f"{self.limits.max_positions}"
            )

        return not violations, violations

    def approve_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        proposed_size: float,
    ) -> tuple[bool, List[str]]:
        """Approve and reserve aggregate notional/leg capacity atomically."""
        passed, violations = self.check_opportunity(opportunity, proposed_size)
        if passed:
            proposal = self._proposal(opportunity, proposed_size)
            self.approvals[opportunity.id] = proposal
            self._adjust_aggregates(proposal, 1.0)
            opportunity.approve()
        return passed, violations

    def has_active_approval(
        self,
        opportunity: EnhancedOpportunity,
        requested_size: float,
    ) -> bool:
        """Return whether this manager has an active reservation for this object."""
        proposal = self.approvals.get(opportunity.id)
        return bool(
            proposal is not None
            and proposal.get("opportunity") is opportunity
            and opportunity.lifecycle_state == LifecycleState.APPROVED
            and requested_size > 0
            and requested_size <= proposal["size"] + 1e-12
        )

    def release_approval(self, opportunity_id: str) -> None:
        """Release an unmaterialized reservation and revoke approval state."""
        proposal = self.approvals.pop(opportunity_id, None)
        if proposal is not None:
            self._adjust_aggregates(proposal, -1.0)
            proposal["opportunity"].revoke_approval()

    def add_position(
        self,
        opportunity: EnhancedOpportunity,
        size: float,
        execution_id: str,
    ) -> None:
        """Convert a matching approval reservation into position records."""
        proposal = self.approvals.get(opportunity.id)
        if proposal is None:
            raise ValueError("A matching risk approval is required before adding positions")
        if proposal.get("opportunity") is not opportunity:
            raise ValueError("The risk approval belongs to a different opportunity object")
        if abs(proposal["size"] - size) > 1e-12:
            raise ValueError("Position size must match the approved reservation")
        if any(leg.token_id in self.positions for leg in opportunity.legs):
            raise ValueError("A position already exists for one or more opportunity legs")

        raw_total = sum(max(0.0, leg.price * size) for leg in opportunity.legs)
        self.approvals.pop(opportunity.id)
        for leg in opportunity.legs:
            raw_cost = max(0.0, leg.price * size)
            exposure_cost = (
                proposal["total_notional"] * raw_cost / raw_total
                if raw_total > 0
                else 0.0
            )
            self.positions[leg.token_id] = {
                "opportunity_id": opportunity.id,
                "execution_id": execution_id,
                "size": size,
                "cost": raw_cost,
                "exposure_cost": exposure_cost,
                "market_id": leg.market_id,
                "side": leg.side,
                "strategy_id": opportunity.strategy_id,
                "topic": opportunity.topic,
                "high_rule_risk": opportunity.risk_level == RiskLevel.HIGH,
            }

    def remove_position(self, token_id: str) -> None:
        """Remove one materialized position and its aggregate exposure."""
        position = self.positions.pop(token_id, None)
        if position is None:
            return

        exposure_cost = position["exposure_cost"]
        self.total_notional -= exposure_cost
        self._update_bucket(
            self.strategy_exposures,
            position.get("strategy_id"),
            -exposure_cost,
        )
        self._update_bucket(
            self.market_exposures,
            position.get("market_id"),
            -exposure_cost,
        )
        self._update_bucket(
            self.topic_exposures,
            position.get("topic"),
            -exposure_cost,
        )
        if position.get("high_rule_risk"):
            self.total_rule_risk_exposure -= exposure_cost

    @staticmethod
    def _utilization(value: float, limit: float) -> float:
        return value / limit if limit > 0 else 0.0

    def get_exposure_summary(self) -> Dict[str, Any]:
        """Return aggregate positions plus approval reservations."""
        approved_notional = sum(
            proposal["total_notional"] for proposal in self.approvals.values()
        )
        approved_positions = self._reserved_position_count()
        total_positions = self._open_position_count() + approved_positions
        return {
            "total_notional": self.total_notional,
            "approved_notional": approved_notional,
            "open_positions": self._open_position_count(),
            "approved_positions": approved_positions,
            "total_positions": total_positions,
            "rule_risk_exposure": self.total_rule_risk_exposure,
            "strategy_exposures": dict(self.strategy_exposures),
            "market_exposures": dict(self.market_exposures),
            "topic_exposures": dict(self.topic_exposures),
            "utilization": {
                "total_notional": self._utilization(
                    self.total_notional,
                    self.limits.max_total_notional,
                ),
                "positions": self._utilization(
                    total_positions,
                    self.limits.max_positions,
                ),
                "rule_risk": self._utilization(
                    self.total_rule_risk_exposure,
                    self.limits.max_rule_risk_exposure,
                ),
            },
        }

    def suggest_position_size(
        self,
        opportunity: EnhancedOpportunity,
        max_size: Optional[float] = None,
    ) -> float:
        """Suggest a size constrained by liquidity and aggregate reservations."""
        if opportunity.total_cost <= 0 or opportunity.id in self.approvals:
            return 0.0

        liquidity_limit = max_size if max_size is not None else opportunity.max_size
        size = 100.0 if liquidity_limit is None else liquidity_limit
        if size <= 0:
            return 0.0

        position_count = len(opportunity.legs)
        if (
            self._open_position_count()
            + self._reserved_position_count()
            + position_count
            > self.limits.max_positions
        ):
            return 0.0

        unit = self._proposal(opportunity, 1.0)
        available_notional = self.limits.max_total_notional - self.total_notional
        size = min(size, available_notional / opportunity.total_cost)

        strategy_id = opportunity.strategy_id
        if strategy_id:
            available = (
                self.limits.max_per_strategy_notional
                - self.strategy_exposures.get(strategy_id, 0.0)
            )
            size = min(size, available / opportunity.total_cost)

        for market_id, unit_exposure in unit["market_exposures"].items():
            current_positions = (
                self._open_position_count(market_id)
                + self._reserved_position_count(market_id)
                + unit["market_position_counts"].get(market_id, 0)
            )
            if current_positions > self.limits.max_positions_per_market:
                return 0.0
            if unit_exposure > 0:
                available = (
                    self.limits.max_per_market_notional
                    - self.market_exposures.get(market_id, 0.0)
                )
                size = min(size, available / unit_exposure)

        if opportunity.topic:
            available = (
                self.limits.max_per_topic_notional
                - self.topic_exposures.get(opportunity.topic, 0.0)
            )
            size = min(size, available / opportunity.total_cost)

        if opportunity.risk_level == RiskLevel.HIGH:
            available = (
                self.limits.max_rule_risk_exposure - self.total_rule_risk_exposure
            )
            size = min(size, available / opportunity.total_cost)

        return max(0.0, size)
