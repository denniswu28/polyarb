"""Shared helpers for building Gamma API query parameters."""

from typing import Any, Dict, Optional


def build_market_query_params(
    *,
    limit: Optional[int] = 250,
    offset: int = 0,
    active: Optional[bool] = True,
    closed: Optional[bool] = False,
    archived: Optional[bool] = False,
    slug: Optional[str] = None,
    tag_id: Optional[str] = None,
    order: Optional[str] = "liquidity",
    ascending: Optional[bool] = False,
    liquidity_num_min: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a Gamma market list query payload with consistent defaults."""

    params: Dict[str, Any] = {"offset": offset}

    if limit is not None:
        params["limit"] = limit

    for flag, key in (
        (active, "active"),
        (closed, "closed"),
        (archived, "archived"),
    ):
        if flag is not None:
            params[key] = "true" if flag else "false"

    if slug:
        params["slug"] = slug

    if tag_id:
        params["tag_id"] = tag_id

    if order:
        params["order"] = order

    if ascending is not None:
        params["ascending"] = "true" if ascending else "false"

    if liquidity_num_min is not None:
        params["liquidity-num-min"] = liquidity_num_min

    return params
