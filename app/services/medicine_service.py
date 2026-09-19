from __future__ import annotations

from app.db.database import get_db, row_to_dict, rows_to_dicts, transaction
from app.services import audit_service, settings_service


def list_companies(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM companies"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY name"
    return rows_to_dicts(get_db().execute(sql).fetchall())


def save_company(name: str, notes: str = "", company_id: int | None = None, active: bool = True) -> int:
    with transaction() as conn:
        if company_id:
            conn.execute(
                "UPDATE companies SET name = ?, notes = ?, active = ? WHERE id = ?",
                (name.strip(), notes, 1 if active else 0, company_id),
            )
            audit_service.log("company.update", "companies", company_id, name)
            return company_id
        cur = conn.execute(
            "INSERT INTO companies(name, notes, active) VALUES (?, ?, ?)",
            (name.strip(), notes, 1 if active else 0),
        )
        audit_service.log("company.create", "companies", cur.lastrowid, name)
        return cur.lastrowid


def list_formulations(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM formulations"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY name"
    return rows_to_dicts(get_db().execute(sql).fetchall())


def save_formulation(name: str, notes: str = "", formulation_id: int | None = None, active: bool = True) -> int:
    with transaction() as conn:
        if formulation_id:
            conn.execute(
                "UPDATE formulations SET name = ?, notes = ?, active = ? WHERE id = ?",
                (name.strip(), notes, 1 if active else 0, formulation_id),
            )
            audit_service.log("formulation.update", "formulations", formulation_id, name)
            return formulation_id
        cur = conn.execute(
            "INSERT INTO formulations(name, notes, active) VALUES (?, ?, ?)",
            (name.strip(), notes, 1 if active else 0),
        )
        audit_service.log("formulation.create", "formulations", cur.lastrowid, name)
        return cur.lastrowid


def get_or_create_company(name: str) -> int | None:
    name = (name or "").strip()
    if not name or name == "-":
        return None
    row = get_db().execute("SELECT id FROM companies WHERE lower(name) = lower(?)", (name,)).fetchone()
    if row:
        return row["id"]
    return save_company(name)


def get_or_create_formulation(name: str) -> int | None:
    name = (name or "").strip()
    if not name or name == "-":
        return None
    row = get_db().execute("SELECT id FROM formulations WHERE lower(name) = lower(?)", (name,)).fetchone()
    if row:
        return row["id"]
    return save_formulation(name)


def list_medicines(search: str = "", active_only: bool = False) -> list[dict]:
    q = f"%{search.strip()}%"
    sql = """
        SELECT m.*, c.name AS company_name, f.name AS formulation_name,
               COALESCE((SELECT SUM(b.qty) FROM batches b WHERE b.medicine_id = m.id), 0) AS stock_qty
        FROM medicines m
        LEFT JOIN companies c ON c.id = m.company_id
        LEFT JOIN formulations f ON f.id = m.formulation_id
        WHERE (? = '' OR m.brand_name LIKE ? OR m.generic_name LIKE ? OR IFNULL(m.barcode,'') LIKE ?)
    """
    params: list = [search.strip(), q, q, q]
    if active_only:
        sql += " AND m.active = 1"
    sql += " ORDER BY m.brand_name"
    return rows_to_dicts(get_db().execute(sql, params).fetchall())


def get_medicine(medicine_id: int) -> dict | None:
    return row_to_dict(
        get_db().execute(
            """
            SELECT m.*, c.name AS company_name, f.name AS formulation_name
            FROM medicines m
            LEFT JOIN companies c ON c.id = m.company_id
            LEFT JOIN formulations f ON f.id = m.formulation_id
            WHERE m.id = ?
            """,
            (medicine_id,),
        ).fetchone()
    )


def save_medicine(data: dict, medicine_id: int | None = None) -> int:
    barcode = (data.get("barcode") or "").strip() or None
    gst = float(data.get("gst_pct") if data.get("gst_pct") not in (None, "") else settings_service.default_gst())
    fields = (
        data["brand_name"].strip(),
        (data.get("generic_name") or "").strip(),
        data.get("formulation_id") or None,
        data.get("company_id") or None,
        data.get("category") or "",
        data.get("unit") or "",
        data.get("pack_size") or "",
        gst,
        barcode,
        1 if data.get("controlled") else 0,
        int(data.get("reorder_level") or 0),
        1 if data.get("active", True) else 0,
        float(data.get("discount_pct") or 0),
        (data.get("rack") or "").strip(),
        int(data.get("sale_paisa") or 0),
        int(data.get("cost_paisa") or 0),
        max(1, int(data.get("units_per_pack") or 1)),
    )
    with transaction() as conn:
        if medicine_id:
            conn.execute(
                """
                UPDATE medicines SET brand_name=?, generic_name=?, formulation_id=?, company_id=?,
                    category=?, unit=?, pack_size=?, gst_pct=?, barcode=?, controlled=?,
                    reorder_level=?, active=?, discount_pct=?, rack=?, sale_paisa=?, cost_paisa=?,
                    units_per_pack=?
                WHERE id=?
                """,
                (*fields, medicine_id),
            )
            audit_service.log("medicine.update", "medicines", medicine_id, data["brand_name"])
            mid = medicine_id
        else:
            cur = conn.execute(
                """
                INSERT INTO medicines(brand_name, generic_name, formulation_id, company_id,
                    category, unit, pack_size, gst_pct, barcode, controlled, reorder_level, active,
                    discount_pct, rack, sale_paisa, cost_paisa, units_per_pack)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fields,
            )
            mid = cur.lastrowid
            audit_service.log("medicine.create", "medicines", mid, data["brand_name"])
        from app.utils.pack import unit_paisa, units_per_pack

        upp = units_per_pack({"units_per_pack": data.get("units_per_pack"), "pack_size": data.get("pack_size")})
        unit_cost = unit_paisa(int(data.get("cost_paisa") or 0), upp)
        unit_sale = unit_paisa(int(data.get("sale_paisa") or 0), upp)
        conn.execute(
            "UPDATE batches SET cost_paisa = ?, sale_paisa = ? WHERE medicine_id = ?",
            (unit_cost, unit_sale, mid),
        )
        qty = int(data.get("opening_qty") or 0)
        batch_no = (data.get("batch_no") or "").strip()
        if qty > 0:
            from app.constants import REF_ADJUST
            from app.services.stock_service import add_stock, find_or_create_batch
            from app.utils.dates import today

            expiry = (data.get("expiry") or "").strip() or "2099-12-31"
            if expiry < today():
                raise ValueError("Expiry cannot be in the past")
            bid = find_or_create_batch(
                conn,
                mid,
                batch_no or "NA",
                expiry,
                unit_cost,
                unit_sale,
            )
            add_stock(conn, bid, qty, REF_ADJUST, mid, "Opening / add stock")
        return mid


def search_pos(query: str, limit: int = 40) -> list[dict]:
    from app.utils.phonetic import fold, search_variants

    q = query.strip()
    if not q:
        return []
    variants = search_variants(q)
    likes = [f"%{v}%" for v in variants]
    folded = fold(q)
    clauses = ["m.barcode = ?"]
    params: list = [q]
    for like in likes:
        clauses.append("m.brand_name LIKE ?")
        clauses.append("IFNULL(m.generic_name,'') LIKE ?")
        params.extend([like, like])
    sql = f"""
        SELECT m.*, c.name AS company_name, f.name AS formulation_name,
               COALESCE((SELECT SUM(b.qty) FROM batches b WHERE b.medicine_id = m.id AND b.qty > 0
                         AND b.expiry >= date('now')), 0) AS stock_qty
        FROM medicines m
        LEFT JOIN companies c ON c.id = m.company_id
        LEFT JOIN formulations f ON f.id = m.formulation_id
        WHERE m.active = 1 AND ({' OR '.join(clauses)})
        ORDER BY CASE WHEN m.barcode = ? THEN 0
                      WHEN lower(m.brand_name) LIKE ? THEN 1 ELSE 2 END, m.brand_name
        LIMIT ?
    """
    params.extend([q, f"{q.lower()}%", limit])
    rows = rows_to_dicts(get_db().execute(sql, params).fetchall())
    if folded:
        ranked = []
        for r in rows:
            score = 0
            if fold(r["brand_name"] or "") == folded or fold(r["generic_name"] or "") == folded:
                score = 1
            ranked.append((score, r))
        ranked.sort(key=lambda x: -x[0])
        rows = [r for _, r in ranked]
    return rows


def import_template_headers() -> list[str]:
    return [
        "brand_name",
        "generic_name",
        "company",
        "formulation",
        "category",
        "unit",
        "pack_size",
        "gst_pct",
        "barcode",
        "reorder_level",
    ]


def write_import_template(path: str) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Medicines"
    ws.append(import_template_headers())
    ws.append(["Panadol", "Paracetamol", "GSK", "Paracetamol 500mg", "Tablet", "Tab", "10s", 0, "123456", 10])
    wb.save(path)


def import_from_excel(path: str) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    ws = wb.active
    needed = import_template_headers()
    errors: list[str] = []
    rows = []
    seen_barcodes: set[str] = set()
    existing = {
        (r.get("barcode") or "").strip()
        for r in list_medicines()
        if r.get("barcode")
    }
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        data = {needed[j]: (row[j] if j < len(row) else None) for j in range(len(needed))}
        brand = str(data.get("brand_name") or "").strip()
        if not brand:
            errors.append(f"Row {i}: brand_name required")
            continue
        try:
            float(data.get("gst_pct") or 0)
        except (TypeError, ValueError):
            errors.append(f"Row {i}: gst_pct must be a number")
            continue
        try:
            int(data.get("reorder_level") or 0)
        except (TypeError, ValueError):
            errors.append(f"Row {i}: reorder_level must be a whole number")
            continue
        barcode = str(data.get("barcode") or "").strip()
        if barcode:
            if barcode in seen_barcodes or barcode in existing:
                errors.append(f"Row {i}: barcode already used ({barcode})")
                continue
            seen_barcodes.add(barcode)
        rows.append((i, data))
    if errors:
        return {"ok": False, "errors": errors, "imported": 0}

    imported = 0
    companies = {c["name"].lower(): c["id"] for c in list_companies()}
    formulations = {f["name"].lower(): f["id"] for f in list_formulations()}
    for i, data in rows:
        try:
            company_id = None
            formulation_id = None
            cname = str(data.get("company") or "").strip()
            fname = str(data.get("formulation") or "").strip()
            if cname:
                company_id = companies.get(cname.lower())
                if not company_id:
                    company_id = save_company(cname)
                    companies[cname.lower()] = company_id
            if fname:
                formulation_id = formulations.get(fname.lower())
                if not formulation_id:
                    formulation_id = save_formulation(fname)
                    formulations[fname.lower()] = formulation_id
            save_medicine(
                {
                    "brand_name": str(data["brand_name"]).strip(),
                    "generic_name": str(data.get("generic_name") or "").strip(),
                    "company_id": company_id,
                    "formulation_id": formulation_id,
                    "category": str(data.get("category") or "Other"),
                    "unit": str(data.get("unit") or "Other"),
                    "pack_size": str(data.get("pack_size") or ""),
                    "gst_pct": float(data.get("gst_pct") or 0),
                    "barcode": str(data.get("barcode") or "").strip(),
                    "controlled": False,
                    "reorder_level": int(data.get("reorder_level") or 0),
                    "active": True,
                }
            )
            imported += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
    return {"ok": not errors, "errors": errors, "imported": imported}
