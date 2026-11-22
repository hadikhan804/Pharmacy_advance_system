"""Pack vs loose-tablet helpers. Stock qty is always tablets."""


def units_per_pack(row) -> int:
    if not row:
        return 1
    n = row.get("units_per_pack") if isinstance(row, dict) else None
    try:
        if n is not None and int(n) > 0:
            return int(n)
    except (TypeError, ValueError):
        pass
    raw = str((row.get("pack_size") if isinstance(row, dict) else "") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 1


def unit_paisa(pack_paisa: int, upp: int) -> int:
    """Price of one tablet from a box price. 500-tab box of Rs 250.00 → Rs 0.50."""
    upp = max(1, int(upp or 1))
    return int(round(int(pack_paisa or 0) / upp))


def charge_paisa(pack_paisa: int, upp: int, units: int) -> int:
    """Exact amount for N tablets from a box price (avoids leftover paisa on a full box)."""
    upp = max(1, int(upp or 1))
    units = max(0, int(units or 0))
    return int(round(int(pack_paisa or 0) * units / upp))


def pack_to_units(packs: int, upp: int) -> int:
    return max(0, int(packs)) * max(1, int(upp or 1))


def medicine_unit_prices(med, batch=None) -> tuple[int, int]:
    """Always derive tablet cost/sale from the saved box price, not a stale batch."""
    med = med or {}
    batch = batch or {}
    upp = units_per_pack(med)
    pack_sale = int(med.get("sale_paisa") or 0)
    pack_cost = int(med.get("cost_paisa") or 0)
    sale = unit_paisa(pack_sale, upp) if pack_sale else int(batch.get("sale_paisa") or 0)
    cost = unit_paisa(pack_cost, upp) if pack_cost else int(batch.get("cost_paisa") or 0)
    return sale, cost
