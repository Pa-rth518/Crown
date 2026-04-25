"""Kelly criterion sizing for binary outcomes with unit odds (b = 1)."""

from __future__ import annotations


def kelly_fraction(*, p: float, b: float = 1.0) -> float:
    """
    Full Kelly bet fraction of bankroll.

    .. math::

        f = \\frac{b \\cdot p - q}{b}, \\quad q = 1 - p

    With **b = 1** (win pays 1:1 net of stake): :math:`f = 2p - 1`.

    Parameters
    ----------
    p
        Probability of winning the bet (must lie in ``[0, 1]``).
    b
        Odds: net profit per unit staked if you win (``1`` means you gain ``1×`` stake on a win).

    Returns
    -------
    float
        Raw Kelly fraction; **can be negative** when there is no edge (:math:`p \\le 1/(1+b)` for general ``b``).
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    if b <= 0:
        raise ValueError(f"b (odds) must be positive, got {b}")

    q = 1.0 - p
    return (b * p - q) / b


def safe_kelly_fraction(*, p: float, b: float = 1.0) -> float:
    """
    Kelly fraction floored at zero, capped at one.

    If the raw Kelly :func:`kelly_fraction` is negative (no edge), returns ``0``.
    Otherwise returns ``min(1, max(0, f))``.
    """
    raw = kelly_fraction(p=p, b=b)
    if raw < 0:
        return 0.0
    return min(1.0, raw)
