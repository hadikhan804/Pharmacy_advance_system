from __future__ import annotations


def to_paisa(amount) -> int:
    if amount is None or amount == "":
        return 0
    if isinstance(amount, int):
        return amount
    return int(round(float(amount) * 100))


def from_paisa(paisa: int | None) -> float:
    if not paisa:
        return 0.0
    return paisa / 100.0


def format_pkr(paisa: int | None) -> str:
    value = from_paisa(paisa or 0)
    return f"Rs {value:,.2f}"
