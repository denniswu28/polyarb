"""
Database models for Polymarket data storage.

These models represent events, markets, outcomes, orderbooks, and trades
using SQLAlchemy ORM for PostgreSQL storage.
"""

from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, DateTime, Numeric, Integer, Boolean, 
    ForeignKey, JSON, Text, Enum as SQLEnum, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


class PriceType(str, Enum):
    """Price types for market data."""
    ASK = "ask"  # Lowest ask price (buy price)
    BID = "bid"  # Highest bid price (sell price)
    MID = "mid"  # Mid-market price (bid + ask) / 2
    LIVE = "live"  # Last traded price
    ACTUAL = "actual"  # Actual execution price for this user/bot


class Event(Base):
    """
    Represents a Polymarket event (group of related markets).
    """
    __tablename__ = "events"
    
    id = Column(String, primary_key=True)
    ticker = Column(String, nullable=True, index=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    creation_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True, index=True)
    volume = Column(Numeric(20, 2), nullable=True)
    liquidity = Column(Numeric(20, 2), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Store raw API response
    raw = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    markets = relationship("DBMarket", back_populates="event", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_events_end_date_volume", "end_date", "volume"),
        Index("ix_events_active_volume", "is_active", "volume"),
    )
    
    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "Event":
        """
        Create Event instance from Gamma API response.
        
        Args:
            data: Raw event data from API
            
        Returns:
            Event instance
        """
        return cls(
            id=data.get("id"),
            ticker=data.get("ticker"),
            slug=data.get("slug"),
            title=data.get("title", ""),
            description=data.get("description"),
            start_date=cls._parse_datetime(data.get("start_date_iso")),
            creation_date=cls._parse_datetime(data.get("creation_date_iso")),
            end_date=cls._parse_datetime(data.get("end_date_iso")),
            volume=Decimal(str(data.get("volume", 0))) if data.get("volume") else None,
            liquidity=Decimal(str(data.get("liquidity", 0))) if data.get("liquidity") else None,
            is_active=data.get("active", True),
            raw=data,
        )
    
    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API."""
        if not dt_str:
            return None
        try:
            # Handle ISO format with Z suffix
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None


class DBMarket(Base):
    """
    Represents a market within an event.
    """
    __tablename__ = "markets"
    
    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, index=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    question = Column(Text, nullable=False)
    rules = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    end_date = Column(DateTime, nullable=True, index=True)
    volume = Column(Numeric(20, 2), nullable=True)
    liquidity = Column(Numeric(20, 2), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # NegRisk information
    is_neg_risk = Column(Boolean, default=False, index=True)
    neg_risk_id = Column(String, nullable=True, index=True)
    neg_risk_market_type = Column(String, nullable=True)
    
    # Store raw API response
    raw = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="markets")
    outcomes = relationship("Outcome", back_populates="market", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_markets_neg_risk", "is_neg_risk", "neg_risk_id"),
        Index("ix_markets_active_volume", "is_active", "volume"),
    )
    
    @classmethod
    def from_api_data(cls, event_id: str, data: Dict[str, Any]) -> "DBMarket":
        """
        Create Market instance from API response.
        
        Args:
            event_id: ID of parent event
            data: Raw market data from API
            
        Returns:
            DBMarket instance
        """
        return cls(
            id=data.get("id") or data.get("condition_id"),
            event_id=event_id,
            slug=data.get("slug", ""),
            question=data.get("question", ""),
            rules=data.get("rules"),
            description=data.get("description"),
            end_date=Event._parse_datetime(data.get("end_date_iso")),
            volume=Decimal(str(data.get("volume", 0))) if data.get("volume") else None,
            liquidity=Decimal(str(data.get("liquidity", 0))) if data.get("liquidity") else None,
            is_active=data.get("active", True),
            is_neg_risk=data.get("neg_risk", False),
            neg_risk_id=data.get("neg_risk_id"),
            neg_risk_market_type=data.get("neg_risk_market_type"),
            raw=data,
        )


class Outcome(Base):
    """
    Represents an outcome/condition within a market.
    """
    __tablename__ = "outcomes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, ForeignKey("markets.id"), nullable=False, index=True)
    condition_id = Column(String, nullable=False, unique=True, index=True)
    label = Column(Text, nullable=False)
    
    # Token IDs for YES and NO sides
    yes_token_id = Column(String, nullable=False, unique=True, index=True)
    no_token_id = Column(String, nullable=False, unique=True, index=True)
    
    # NegRisk membership
    is_neg_risk_member = Column(Boolean, default=False)
    neg_risk_id = Column(String, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    market = relationship("DBMarket", back_populates="outcomes")
    
    @classmethod
    def from_api_data(cls, market_id: str, data: Dict[str, Any]) -> "Outcome":
        """
        Create Outcome instance from API response.
        
        Args:
            market_id: ID of parent market
            data: Raw outcome data
            
        Returns:
            Outcome instance
        """
        return cls(
            market_id=market_id,
            condition_id=data.get("condition_id"),
            label=data.get("label", ""),
            yes_token_id=data.get("yes_token_id", ""),
            no_token_id=data.get("no_token_id", ""),
            is_neg_risk_member=data.get("neg_risk", False),
            neg_risk_id=data.get("neg_risk_id"),
        )


class OrderBookSnapshot(Base):
    """
    Represents an orderbook snapshot for a token.
    """
    __tablename__ = "orderbook_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Best bid/ask
    best_bid = Column(Numeric(10, 8), nullable=True)
    best_bid_size = Column(Numeric(20, 2), nullable=True)
    best_ask = Column(Numeric(10, 8), nullable=True)
    best_ask_size = Column(Numeric(20, 2), nullable=True)
    
    # Derived metrics
    mid_price = Column(Numeric(10, 8), nullable=True)
    spread_bps = Column(Numeric(10, 2), nullable=True)
    
    # Full orderbook (top N levels)
    bids = Column(JSONB, nullable=True)  # [{price, size}, ...]
    asks = Column(JSONB, nullable=True)  # [{price, size}, ...]
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("ix_orderbook_token_timestamp", "token_id", "timestamp"),
    )


class Trade(Base):
    """
    Represents an executed trade.
    """
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # 'buy' or 'sell'
    price = Column(Numeric(10, 8), nullable=False)
    size = Column(Numeric(20, 2), nullable=False)
    
    # User/bot identification (optional)
    user_id = Column(String, nullable=True, index=True)
    
    # Strategy information
    strategy_id = Column(String, nullable=True, index=True)
    opportunity_id = Column(String, nullable=True, index=True)
    
    # Execution details
    execution_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    order_id = Column(String, nullable=True)
    
    # Slippage tracking
    expected_price = Column(Numeric(10, 8), nullable=True)
    slippage_bps = Column(Numeric(10, 2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("ix_trades_token_timestamp", "token_id", "execution_timestamp"),
        Index("ix_trades_user_strategy", "user_id", "strategy_id"),
    )
