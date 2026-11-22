SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner', 'cashier')),
    active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    details TEXT,
    ts TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS formulations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY,
    brand_name TEXT NOT NULL,
    generic_name TEXT,
    formulation_id INTEGER,
    company_id INTEGER,
    category TEXT,
    unit TEXT,
    pack_size TEXT,
    units_per_pack INTEGER NOT NULL DEFAULT 1,
    gst_pct REAL NOT NULL DEFAULT 0,
    barcode TEXT UNIQUE,
    controlled INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    discount_pct REAL NOT NULL DEFAULT 0,
    rack TEXT DEFAULT '',
    sale_paisa INTEGER NOT NULL DEFAULT 0,
    cost_paisa INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(formulation_id) REFERENCES formulations(id),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cnic TEXT,
    phone TEXT,
    address TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY,
    medicine_id INTEGER NOT NULL,
    batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    cost_paisa INTEGER NOT NULL,
    sale_paisa INTEGER NOT NULL,
    FOREIGN KEY(medicine_id) REFERENCES medicines(id)
);

CREATE TABLE IF NOT EXISTS stock_ledger (
    id INTEGER PRIMARY KEY,
    medicine_id INTEGER NOT NULL,
    batch_id INTEGER,
    direction TEXT NOT NULL CHECK(direction IN ('in', 'out')),
    qty INTEGER NOT NULL,
    ref_type TEXT NOT NULL,
    ref_id INTEGER,
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(medicine_id) REFERENCES medicines(id),
    FOREIGN KEY(batch_id) REFERENCES batches(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER NOT NULL,
    invoice_no TEXT,
    date TEXT NOT NULL,
    total_paisa INTEGER NOT NULL DEFAULT 0,
    paid_paisa INTEGER NOT NULL DEFAULT 0,
    returned_paisa INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unpaid',
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY,
    purchase_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    batch_id INTEGER,
    batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL,
    qty INTEGER NOT NULL,
    cost_paisa INTEGER NOT NULL,
    sale_paisa INTEGER NOT NULL,
    FOREIGN KEY(purchase_id) REFERENCES purchases(id),
    FOREIGN KEY(medicine_id) REFERENCES medicines(id),
    FOREIGN KEY(batch_id) REFERENCES batches(id)
);

CREATE TABLE IF NOT EXISTS purchase_payments (
    id INTEGER PRIMARY KEY,
    purchase_id INTEGER,
    supplier_id INTEGER NOT NULL,
    amount_paisa INTEGER NOT NULL,
    method TEXT,
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(purchase_id) REFERENCES purchases(id),
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_returns (
    id INTEGER PRIMARY KEY,
    purchase_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    batch_id INTEGER,
    qty INTEGER NOT NULL,
    amount_paisa INTEGER NOT NULL,
    reason TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(purchase_id) REFERENCES purchases(id),
    FOREIGN KEY(medicine_id) REFERENCES medicines(id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    invoice_no TEXT UNIQUE,
    customer_id INTEGER,
    date TEXT NOT NULL,
    subtotal_paisa INTEGER NOT NULL DEFAULT 0,
    discount_paisa INTEGER NOT NULL DEFAULT 0,
    gst_paisa INTEGER NOT NULL DEFAULT 0,
    total_paisa INTEGER NOT NULL DEFAULT 0,
    paid_paisa INTEGER NOT NULL DEFAULT 0,
    due_paisa INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    batch_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    unit_price_paisa INTEGER NOT NULL,
    discount_paisa INTEGER NOT NULL DEFAULT 0,
    gst_paisa INTEGER NOT NULL DEFAULT 0,
    cost_paisa INTEGER NOT NULL,
    line_profit_paisa INTEGER NOT NULL,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(medicine_id) REFERENCES medicines(id),
    FOREIGN KEY(batch_id) REFERENCES batches(id)
);

CREATE TABLE IF NOT EXISTS sale_returns (
    id INTEGER PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    sale_item_id INTEGER,
    medicine_id INTEGER NOT NULL,
    batch_id INTEGER,
    qty INTEGER NOT NULL,
    amount_paisa INTEGER NOT NULL,
    profit_reversal_paisa INTEGER NOT NULL,
    reason TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(medicine_id) REFERENCES medicines(id)
);

CREATE TABLE IF NOT EXISTS customer_payments (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    sale_id INTEGER,
    amount_paisa INTEGER NOT NULL,
    method TEXT,
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id),
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

CREATE TABLE IF NOT EXISTS supplier_payments (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER NOT NULL,
    purchase_id INTEGER,
    amount_paisa INTEGER NOT NULL,
    method TEXT,
    notes TEXT,
    user_id INTEGER,
    ts TEXT NOT NULL,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY(purchase_id) REFERENCES purchases(id)
);

CREATE TABLE IF NOT EXISTS backup_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    location TEXT NOT NULL,
    kind TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    integrity_ok INTEGER,
    size_bytes INTEGER,
    details TEXT
);

CREATE TABLE IF NOT EXISTS period_closes (
    id INTEGER PRIMARY KEY,
    period_key TEXT NOT NULL UNIQUE,
    period_kind TEXT NOT NULL DEFAULT 'month',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    sale_paisa INTEGER NOT NULL DEFAULT 0,
    profit_paisa INTEGER NOT NULL DEFAULT 0,
    invoices INTEGER NOT NULL DEFAULT 0,
    stock_cost_paisa INTEGER NOT NULL DEFAULT 0,
    stock_sale_paisa INTEGER NOT NULL DEFAULT 0,
    closed_at TEXT NOT NULL,
    user_id INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_medicines_barcode ON medicines(barcode);
CREATE INDEX IF NOT EXISTS idx_medicines_brand ON medicines(brand_name);
CREATE INDEX IF NOT EXISTS idx_medicines_generic ON medicines(generic_name);
CREATE INDEX IF NOT EXISTS idx_batches_medicine ON batches(medicine_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches(expiry);
CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);
CREATE INDEX IF NOT EXISTS idx_ledger_medicine ON stock_ledger(medicine_id);
CREATE INDEX IF NOT EXISTS idx_ledger_ts ON stock_ledger(ts);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_cnic ON customers(cnic);
"""
