"""Risk approval limits with aggregate exposure reservations."""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from polyarb.core.lifecycle import LifecycleState
from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, RiskLevel


@dataclass(frozen=True)
class _LegApprovalFingerprint:
    """Immutable copy of every modeled leg field used by execution or risk."""

    token_id: str
    side: str
    outcome_label: str
    market_id: str
    market_question: str
    price: float
    price_type: str
    size: Optional[float]
    spread_bps: Optional[float]
    depth: Optional[float]


@dataclass(frozen=True)
class _OpportunityApprovalFingerprint:
    """Immutable approval-time copy of execution-relevant opportunity state."""

    opportunity_id: str
    opportunity_class: str
    approved_size: float
    strategy_id: Optional[str]
    name: str
    description: str
    legs: Tuple[_LegApprovalFingerprint, ...]
    total_cost: float
    worst_case_payoff: float
    best_case_payoff: float
    expected_profit: float
    profit_percentage: float
    adjusted_cost: Optional[float]
    adjusted_profit: Optional[float]
    adjusted_profit_percentage: Optional[float]
    risk_level: str
    rule_risk_notes: Tuple[str, ...]
    max_size: Optional[float]
    liquidity_score: Optional[float]
    market_ids: Tuple[str, ...]
    event_ids: Tuple[str, ...]
    tags: Tuple[str, ...]
    topic: Optional[str]
    is_pure_arbitrage: bool
    expires_at: Optional[str]


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
        self.validate()

    def validate(self) -> None:
        """Reject non-finite limits, including values mutated after construction."""
        float_fields = (
            "max_total_notional",
            "max_per_strategy_notional",
            "max_per_market_notional",
            "max_per_topic_notional",
            "min_profit_threshold",
            "max_rule_risk_exposure",
            "max_slippage_tolerance",
            "min_liquidity_score",
        )
        for field_name in float_fields:
            try:
                normalized = float(getattr(self, field_name))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be a finite number") from exc
            if not math.isfinite(normalized):
                raise ValueError(f"{field_name} must be a finite number")
            setattr(self, field_name, normalized)

        for field_name in ("max_positions", "max_positions_per_market"):
            value = getattr(self, field_name)
            if isinstance(value, bool):
                raise ValueError(f"{field_name} must be a finite integer")
            try:
                normalized = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be a finite integer") from exc
            if not math.isfinite(normalized) or not normalized.is_integer():
                raise ValueError(f"{field_name} must be a finite integer")
            setattr(self, field_name, int(normalized))

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
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def _now_utc(self) -> datetime:
        now = self._utc_now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("RiskManager clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _finite_float(value: Any, field_name: str) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be finite") from exc
        if not math.isfinite(normalized):
            raise ValueError(f"{field_name} must be finite")
        return normalized

    @classmethod
    def _optional_float(
        cls,
        value: Optional[float],
        field_name: str,
    ) -> Optional[float]:
        return None if value is None else cls._finite_float(value, field_name)

    @staticmethod
    def _expiration_utc(opportunity: EnhancedOpportunity) -> Optional[datetime]:
        expires_at = opportunity.expires_at
        if expires_at is None:
            return None
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a timezone-aware datetime")
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("expires_at must be a timezone-aware datetime")
        return expires_at.astimezone(timezone.utc)

    @classmethod
    def _input_violations(
        cls,
        opportunity: EnhancedOpportunity,
        proposed_size: Any,
        now: datetime,
    ) -> List[str]:
        """Validate numeric and expiration inputs before comparison/fingerprinting."""
        violations: List[str] = []

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("RiskManager clock must return a timezone-aware datetime")
        now = now.astimezone(timezone.utc)

        try:
            normalized_size = cls._finite_float(proposed_size, "Proposed size")
        except ValueError as exc:
            violations.append(str(exc))
            normalized_size = None

        numeric_fields = (
            "total_cost",
            "worst_case_payoff",
            "best_case_payoff",
            "expected_profit",
            "profit_percentage",
            "adjusted_cost",
            "adjusted_profit",
            "adjusted_profit_percentage",
            "max_size",
            "liquidity_score",
        )
        for field_name in numeric_fields:
            value = getattr(opportunity, field_name)
            if value is None:
                continue
            try:
                cls._finite_float(value, field_name)
            except ValueError as exc:
                violations.append(str(exc))

        for index, leg in enumerate(opportunity.legs):
            for field_name in ("price", "size", "spread_bps", "depth"):
                value = getattr(leg, field_name, None)
                if value is None:
                    continue
                try:
                    cls._finite_float(value, f"Leg {index} {field_name}")
                except ValueError as exc:
                    violations.append(str(exc))

        if normalized_size is not None:
            try:
                total_cost = cls._finite_float(opportunity.total_cost, "total_cost")
                cls._finite_float(
                    total_cost * normalized_size,
                    "Proposed total notional",
                )
            except ValueError as exc:
                violations.append(str(exc))
            for index, leg in enumerate(opportunity.legs):
                try:
                    leg_price = cls._finite_float(leg.price, f"Leg {index} price")
                    cls._finite_float(
                        leg_price * normalized_size,
                        f"Leg {index} notional",
                    )
                except ValueError as exc:
                    violations.append(str(exc))

        try:
            expiration = cls._expiration_utc(opportunity)
        except ValueError as exc:
            violations.append(str(exc))
        else:
            if expiration is not None and expiration <= now:
                violations.append("Opportunity has expired")

        return list(dict.fromkeys(violations))

    @classmethod
    def _approval_fingerprint(
        cls,
        opportunity: EnhancedOpportunity,
        approved_size: float,
    ) -> _OpportunityApprovalFingerprint:
        """Copy mutable opportunity state into an immutable approval fingerprint."""
        legs = tuple(
            _LegApprovalFingerprint(
                token_id=str(leg.token_id),
                side=str(leg.side),
                outcome_label=str(leg.outcome_label),
                market_id=str(leg.market_id),
                market_question=str(leg.market_question),
                price=cls._finite_float(leg.price, "leg price"),
                price_type=str(leg.price_type),
                size=cls._optional_float(leg.size, "leg size"),
                spread_bps=cls._optional_float(leg.spread_bps, "leg spread_bps"),
                depth=cls._optional_float(leg.depth, "leg depth"),
            )
            for leg in opportunity.legs
        )
        return _OpportunityApprovalFingerprint(
            opportunity_id=str(opportunity.id),
            opportunity_class=opportunity.opportunity_class.value,
            approved_size=cls._finite_float(approved_size, "approved size"),
            strategy_id=(
                None if opportunity.strategy_id is None else str(opportunity.strategy_id)
            ),
            name=str(opportunity.name),
            description=str(opportunity.description),
            legs=legs,
            total_cost=cls._finite_float(opportunity.total_cost, "total_cost"),
            worst_case_payoff=cls._finite_float(
                opportunity.worst_case_payoff,
                "worst_case_payoff",
            ),
            best_case_payoff=cls._finite_float(
                opportunity.best_case_payoff,
                "best_case_payoff",
            ),
            expected_profit=cls._finite_float(
                opportunity.expected_profit,
                "expected_profit",
            ),
            profit_percentage=cls._finite_float(
                opportunity.profit_percentage,
                "profit_percentage",
            ),
            adjusted_cost=cls._optional_float(
                opportunity.adjusted_cost,
                "adjusted_cost",
            ),
            adjusted_profit=cls._optional_float(
                opportunity.adjusted_profit,
                "adjusted_profit",
            ),
            adjusted_profit_percentage=cls._optional_float(
                opportunity.adjusted_profit_percentage,
                "adjusted_profit_percentage",
            ),
            risk_level=opportunity.risk_level.value,
            rule_risk_notes=tuple(str(note) for note in opportunity.rule_risk_notes),
            max_size=cls._optional_float(opportunity.max_size, "max_size"),
            liquidity_score=cls._optional_float(
                opportunity.liquidity_score,
                "liquidity_score",
            ),
            market_ids=tuple(str(market_id) for market_id in opportunity.market_ids),
            event_ids=tuple(str(event_id) for event_id in opportunity.event_ids),
            tags=tuple(str(tag) for tag in opportunity.tags),
            topic=None if opportunity.topic is None else str(opportunity.topic),
            is_pure_arbitrage=bool(opportunity.is_pure_arbitrage),
            expires_at=(
                cls._expiration_utc(opportunity).isoformat()
                if opportunity.expires_at is not None
                else None
            ),
        )

    @classmethod
    def _proposal(
        cls,
        opportunity: EnhancedOpportunity,
        size: float,
    ) -> Dict[str, Any]:
        """Build an exposure reservation whose market allocations sum to notional."""
        normalized_size = cls._finite_float(size, "Proposed size")
        total_cost = cls._finite_float(opportunity.total_cost, "total_cost")
        total_notional = cls._finite_float(
            total_cost * normalized_size,
            "Proposed total notional",
        )
        total_notional = max(0.0, total_notional)
        raw_market_costs: Dict[str, float] = {}
        market_position_counts: Dict[str, int] = {}

        for leg in opportunity.legs:
            leg_price = cls._finite_float(leg.price, "leg price")
            leg_notional = cls._finite_float(
                leg_price * normalized_size,
                "leg notional",
            )
            market_total = cls._finite_float(
                raw_market_costs.get(leg.market_id, 0.0)
                + max(0.0, leg_notional),
                "market notional",
            )
            raw_market_costs[leg.market_id] = market_total
            market_position_counts[leg.market_id] = (
                market_position_counts.get(leg.market_id, 0) + 1
            )

        if not raw_market_costs and opportunity.market_ids:
            unique_markets = list(dict.fromkeys(opportunity.market_ids))
            raw_market_costs = {market_id: 1.0 for market_id in unique_markets}

        raw_total = cls._finite_float(
            sum(raw_market_costs.values()),
            "aggregate leg notional",
        )
        if raw_total > 0:
            market_exposures = {}
            for market_id, raw_cost in raw_market_costs.items():
                market_exposures[market_id] = cls._finite_float(
                    total_notional * raw_cost / raw_total,
                    "market exposure",
                )
        else:
            market_exposures = {market_id: 0.0 for market_id in raw_market_costs}

        return {
            "opportunity_id": opportunity.id,
            "opportunity": opportunity,
            "approval_fingerprint": cls._approval_fingerprint(
                opportunity,
                normalized_size,
            ),
            "size": normalized_size,
            "expires_at_utc": cls._expiration_utc(opportunity),
            "total_notional": total_notional,
            "position_count": len(opportunity.legs),
            "market_exposures": market_exposures,
            "market_position_counts": market_position_counts,
            "strategy_id": opportunity.strategy_id,
            "topic": opportunity.topic,
            "high_rule_risk": opportunity.risk_level == RiskLevel.HIGH,
        }

    def _release_expired_approvals(self) -> None:
        """Release reservations whose approval-time UTC expiration has passed."""
        now = self._now_utc()
        expired_ids = []
        for opportunity_id, proposal in self.approvals.items():
            expires_at = proposal.get("expires_at_utc")
            if expires_at is None:
                continue
            if (
                not isinstance(expires_at, datetime)
                or expires_at.tzinfo is None
                or expires_at.utcoffset() is None
                or expires_at <= now
            ):
                expired_ids.append(opportunity_id)
        for opportunity_id in expired_ids:
            self.release_approval(opportunity_id)

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
        if not math.isfinite(delta):
            raise ValueError("Aggregate exposure delta must be finite")
        updated = bucket.get(key, 0.0) + delta
        if not math.isfinite(updated):
            raise ValueError("Aggregate exposure must remain finite")
        if abs(updated) < 1e-12:
            bucket.pop(key, None)
        else:
            bucket[key] = updated

    def _adjust_aggregates(self, proposal: Dict[str, Any], direction: float) -> None:
        delta = direction * proposal["total_notional"]
        if not math.isfinite(delta):
            raise ValueError("Aggregate exposure delta must be finite")
        updated_total = self.total_notional + delta
        if not math.isfinite(updated_total):
            raise ValueError("Aggregate exposure must remain finite")
        self.total_notional = updated_total
        self._update_bucket(
            self.strategy_exposures,
            proposal.get("strategy_id"),
            delta,
        )
        self._update_bucket(self.topic_exposures, proposal.get("topic"), delta)
        for market_id, value in proposal["market_exposures"].items():
            self._update_bucket(self.market_exposures, market_id, direction * value)
        if proposal.get("high_rule_risk"):
            updated_rule_risk = self.total_rule_risk_exposure + delta
            if not math.isfinite(updated_rule_risk):
                raise ValueError("Rule-risk exposure must remain finite")
            self.total_rule_risk_exposure = updated_rule_risk

    def check_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        proposed_size: float,
    ) -> tuple[bool, List[str]]:
        """Check a proposed approval against positions and prior reservations."""
        self._release_expired_approvals()
        self.limits.validate()
        violations = self._input_violations(
            opportunity,
            proposed_size,
            self._now_utc(),
        )
        if violations:
            return False, violations

        normalized_size = self._finite_float(proposed_size, "Proposed size")
        max_size = self._optional_float(opportunity.max_size, "max_size")
        profit_percentage = self._finite_float(
            opportunity.profit_percentage,
            "profit_percentage",
        )
        liquidity_score = self._optional_float(
            opportunity.liquidity_score,
            "liquidity_score",
        )

        if opportunity.id in self.approvals:
            violations.append(f"Opportunity {opportunity.id} is already approved")
        if normalized_size <= 0:
            violations.append("Proposed size must be positive")
        if max_size is not None and normalized_size > max_size:
            violations.append(
                f"Proposed size {normalized_size:.2f} exceeds liquidity-constrained "
                f"maximum {max_size:.2f}"
            )
        if profit_percentage < self.limits.min_profit_threshold:
            violations.append(
                f"Modeled edge {profit_percentage:.2f}% below threshold "
                f"{self.limits.min_profit_threshold:.2f}%"
            )

        proposal = self._proposal(opportunity, normalized_size)
        proposed_total = self.total_notional + proposal["total_notional"]
        if not math.isfinite(proposed_total):
            violations.append("Proposed aggregate notional must remain finite")
            return False, violations
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
            if not math.isfinite(strategy_total):
                violations.append("Per-strategy exposure must remain finite")
            elif strategy_total > self.limits.max_per_strategy_notional:
                violations.append(f"Would exceed per-strategy limit for {strategy_id}")

        for market_id, proposed_exposure in proposal["market_exposures"].items():
            market_total = self.market_exposures.get(market_id, 0.0) + proposed_exposure
            if not math.isfinite(market_total):
                violations.append("Per-market exposure must remain finite")
            elif market_total > self.limits.max_per_market_notional:
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
            if not math.isfinite(topic_total):
                violations.append("Per-topic exposure must remain finite")
            elif topic_total > self.limits.max_per_topic_notional:
                violations.append(f"Would exceed per-topic limit for {topic}")

        if proposal.get("high_rule_risk"):
            rule_risk_total = self.total_rule_risk_exposure + proposal["total_notional"]
            if not math.isfinite(rule_risk_total):
                violations.append("Rule-risk exposure must remain finite")
            elif rule_risk_total > self.limits.max_rule_risk_exposure:
                violations.append("Would exceed rule risk exposure limit")

        if liquidity_score is not None and liquidity_score < self.limits.min_liquidity_score:
            violations.append(
                f"Liquidity score {liquidity_score:.2f} below minimum "
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
            expires_at = proposal.get("expires_at_utc")
            if expires_at is not None and expires_at <= self._now_utc():
                return False, ["Opportunity has expired"]
            self.approvals[opportunity.id] = proposal
            self._adjust_aggregates(proposal, 1.0)
            opportunity.approve()
        return passed, violations

    def has_active_approval(
        self,
        opportunity: EnhancedOpportunity,
        requested_size: float,
    ) -> bool:
        """Require the exact object, size, and immutable approval-time fingerprint."""
        self._release_expired_approvals()
        try:
            self.limits.validate()
        except ValueError:
            return False

        proposal = self.approvals.get(opportunity.id)
        if (
            proposal is None
            or proposal.get("opportunity") is not opportunity
            or opportunity.lifecycle_state != LifecycleState.APPROVED
        ):
            return False

        now = self._now_utc()
        violations = self._input_violations(opportunity, requested_size, now)
        if violations:
            if "Opportunity has expired" in violations:
                self.release_approval(opportunity.id)
            return False

        normalized_size = self._finite_float(requested_size, "Requested size")
        if normalized_size <= 0:
            return False
        try:
            current_fingerprint = self._approval_fingerprint(
                opportunity,
                normalized_size,
            )
        except (AttributeError, TypeError, ValueError):
            return False
        return bool(
            current_fingerprint == proposal.get("approval_fingerprint")
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
        if not self.has_active_approval(opportunity, size):
            raise ValueError(
                "Opportunity state and size must match the immutable risk approval"
            )
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
        self._release_expired_approvals()
        self.limits.validate()
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
        self._release_expired_approvals()
        try:
            self.limits.validate()
            if max_size is not None:
                max_size = self._finite_float(max_size, "max_size")
            validation_size = 1.0 if max_size is None else max_size
            if self._input_violations(
                opportunity,
                validation_size,
                self._now_utc(),
            ):
                return 0.0
            total_cost = self._finite_float(opportunity.total_cost, "total_cost")
        except ValueError:
            return 0.0

        if total_cost <= 0 or opportunity.id in self.approvals:
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
        size = min(size, available_notional / total_cost)

        strategy_id = opportunity.strategy_id
        if strategy_id:
            available = (
                self.limits.max_per_strategy_notional
                - self.strategy_exposures.get(strategy_id, 0.0)
            )
            size = min(size, available / total_cost)

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
            size = min(size, available / total_cost)

        if opportunity.risk_level == RiskLevel.HIGH:
            available = (
                self.limits.max_rule_risk_exposure - self.total_rule_risk_exposure
            )
            size = min(size, available / total_cost)

        return max(0.0, size) if math.isfinite(size) else 0.0
