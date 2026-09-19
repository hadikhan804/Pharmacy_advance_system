ROLE_OWNER = "owner"
ROLE_CASHIER = "cashier"
ROLES = (ROLE_OWNER, ROLE_CASHIER)

PAYMENT_CASH = "Cash"
PAYMENT_CARD = "Card"
PAYMENT_EASYPAISA = "Easypaisa"
PAYMENT_JAZZCASH = "JazzCash"
PAYMENT_CREDIT = "Credit"
PAYMENT_METHODS = (
    PAYMENT_CASH,
    PAYMENT_CARD,
    PAYMENT_EASYPAISA,
    PAYMENT_JAZZCASH,
    PAYMENT_CREDIT,
)

STATUS_HELD = "held"
STATUS_COMPLETED = "completed"
STATUS_RETURNED = "returned"
STATUS_VOIDED = "voided"

PAY_UNPAID = "unpaid"
PAY_PARTIAL = "partial"
PAY_PAID = "paid"

REF_PURCHASE = "purchase"
REF_PURCHASE_RETURN = "purchase_return"
REF_SALE = "sale"
REF_SALE_RETURN = "sale_return"
REF_ADJUST = "adjustment"

UNITS = ("Tab", "Cap", "Syp", "Inj", "Crm", "Oint", "Drops", "Sachet", "Bottle", "Pack", "Other")
CATEGORIES = (
    "Tablet",
    "Capsule",
    "Syrup",
    "Suspension",
    "Injection",
    "Infusion",
    "Cream",
    "Ointment",
    "Drops",
    "Inhaler",
    "Sachet",
    "Bottle",
    "Other",
)
