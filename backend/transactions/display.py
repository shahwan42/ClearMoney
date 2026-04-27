"""
Display helpers for transaction-related UI computations.

This module provides functions to compute display-layer values (colors, indicators)
that should live in the service/view layer instead of templates. All logic is
testable, documented, and separated from template rendering.
"""

from decimal import Decimal


def get_tx_indicator_color(tx_type: str) -> str:
    """
    Return hex color for transaction type indicator dot.

    Used in transaction row to show a colored dot indicating transaction type.

    Args:
        tx_type: Transaction type string ("expense", "income", "transfer", "exchange")

    Returns:
        Hex color string:
        - "#f87171" (red-400) for expense
        - "#4ade80" (green-400) for income
        - "#60a5fa" (blue-400) for other (transfer, exchange)
    """
    if tx_type == "expense":
        return "#f87171"  # red-400
    if tx_type == "income":
        return "#4ade80"  # green-400
    return "#60a5fa"  # blue-400 (transfer, exchange, or unknown)


def get_tx_amount_color_class(
    tx_type: str, balance_delta: Decimal | None = None
) -> str:
    """
    Return Tailwind color class for transaction amount text.

    For expense/income, color is based solely on type. For transfer/exchange,
    color indicates whether balance increased or decreased.

    Args:
        tx_type: Transaction type ("expense", "income", "transfer", "exchange")
        balance_delta: For transfer/exchange, whether balance moved up or down.
                      Ignored for expense/income.

    Returns:
        Tailwind CSS class string for amount text coloring:
        - "text-red-600" for expense
        - "text-green-600" for income
        - "text-green-600" if transfer/exchange with positive delta (deposited)
        - "text-red-600" if transfer/exchange with negative delta (withdrawn)
    """
    if tx_type == "expense":
        return "text-red-600"
    if tx_type == "income":
        return "text-green-600"
    # For transfer/exchange: red = withdrawn, green = deposited
    if balance_delta is not None and balance_delta < 0:
        return "text-red-600"
    return "text-green-600"
