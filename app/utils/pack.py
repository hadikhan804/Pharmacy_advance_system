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
    upp = max(1, int(upp or 1))
    return int(round(int(pack_paisa or 0) / upp))


def pack_to_units(packs: int, upp: int) -> int:
    return max(0, int(packs)) * max(1, int(upp or 1))
