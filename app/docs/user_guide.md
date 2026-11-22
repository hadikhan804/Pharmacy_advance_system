# Hadi Pharmacy — User Guide

Phone support: **03716931861**

This guide explains every screen and button, and — most important — **how your shop data is kept safe** so nothing is ever lost. You can open this guide any time inside the program from the **Help** button in the top menu (or press **F1**). A copy is also in the program folder as **User Guide.html**.

---

## 1. The 5 golden rules (read these first)

1. **Never delete the `data` folder** next to HadiPharmacy.exe. That folder *is* your shop: medicines, stock, sales, udhaar, backups and bills.
2. **Close the program with the Logout button** at the end of the day. Closing takes a backup automatically.
3. **Set a Secondary backup folder** (USB drive or Google Drive / OneDrive folder) in **Settings**. If the computer dies, this copy saves you.
4. **Remember the owner password.** Backups made while the owner is logged in are locked with that password. You will need it to restore them on a new computer.
5. **Do not open the program from inside a zip file.** Always use `HadiPharmacy-Setup.exe` or the extracted folder.

---

## 2. Installing and opening the program

### First install
1. Double-click **HadiPharmacy-Setup.exe**.
2. It installs the program **in the same folder where the Setup file is** (for example `E:\HADI\hadi_pharmacy`): `HadiPharmacy.exe`, `_internal`, the `data` folder and the two guides all appear there, and the program starts. So first put the Setup file in the folder where you want the shop to live (for example a folder on the Desktop or on drive D:).
   - If Setup is on a **USB drive**, the shop data is saved on that USB. Keep it plugged in while working, and never unplug it while the program is open.
   - If an earlier install on the Desktop has shop data, Setup asks to copy that data into the new folder — say **Yes** to keep every record.
3. To make a shortcut: open that folder, right-click **HadiPharmacy.exe** → *Send to* → *Desktop (create shortcut)*.

Next time, open **HadiPharmacy.exe** (or the shortcut). Only one copy of the program can be open at a time; if you try to open a second one it says *"The app is already running."*

### Updating to a new version (your data is kept)
1. Click **Logout** so the program is closed.
2. Run the new **HadiPharmacy-Setup.exe**.
3. Setup replaces the program files only. It **never touches** the `data` folder. When it finds your data it shows *"Update installed. Your existing shop data was kept in …"*.
4. If Setup says *"Hadi Pharmacy is still open"*, close the program (and any open bill window) and run Setup again. Your data is safe.

### If the program folder was deleted by mistake
Just run Setup again. The program keeps a hidden safety copy of your database in
`C:\Users\<you>\AppData\Local\HadiPharmacy\mirror`.
On the next start it finds that copy and shows *"Your previous shop data was found and restored."* The safety copy is refreshed when the program starts, every 10 minutes while it is open, and when you log out.

---

## 3. First login and first-time setup

1. Login with **Username: `admin`**, **Password: `admin123`**.
2. **Change the password now:** top menu **Users** → click the `admin` row → **Change password** → type the new password twice (at least 6 characters) → OK. Write it down somewhere safe.
3. Open **Settings** and fill in:
   - **Pharmacy name, Address, Phone, NTN** — printed on every bill.
   - **Logo** → *Choose file* (optional, shown on the bill). Tip: first copy the picture into the `data` folder and choose it from there, so it moves with your data to a new computer.
   - **Receipt footer (English / Urdu)** — for example *"No return without bill"*.
   - **Printer** — choose your bill printer (for example BC-86AC). See section 13.
   - **Default GST %**, **Expiry alert days**, **Udhaar overdue days**, **Language** (English / Urdu).
   - **Backup folder** — leave as it is (it points to `data\backups`).
   - **Secondary backup** → *Choose folder* → pick your USB drive or Google Drive / OneDrive folder.
4. Click **Save**, then click **Test print** to check the printer.
5. Add your companies (section 8), then medicines (section 5), then enter your opening stock with **Purchases → New purchase** (section 7) or **Stock → Restock**.

---

## 4. The top menu

| Button | What it is for | Who sees it |
|---|---|---|
| Home | Today / week / month / year sale and profit, stock alerts, udhaar, payables, backup status | Owner |
| POS | Selling to customers and printing bills | Owner, Cashier |
| Medicines | Your medicine list (add, edit, delete, Excel import) | Owner |
| Stock | Current stock, batches, corrections, stock history | Owner, Cashier |
| Purchases | Stock bought from companies, payments, returns to company | Owner |
| Sales | Old bills: view, reprint, return / refund, delete (owner) | Owner, Cashier |
| Customers | Customer names and phones (needed for udhaar) | Owner |
| Companies | Companies you buy from — **the company is the supplier** | Owner |
| Forms | Formulations (Tablet, Syrup, …) | Owner |
| Udhaar | Money customers owe you | Owner |
| Payables | Money you owe to companies | Owner |
| Expiry | Medicines expiring in 30 / 60 / 90 days / 6 months and already expired | Owner |
| Reports | All reports, Excel / PDF export, month close | Owner, Cashier |
| Users | Owner and cashier accounts | Owner |
| Audit | Log of every important action (who did what, when) | Owner |
| Settings | Shop details, printer, backups, restore | Owner |
| Help | This guide | Everyone |
| Logout | Closes the program safely (takes a backup) | Everyone |

The bell (🔔) opens the Expiry page. **F2 / F8 / F9 / F10** chips at the top are the POS shortcuts.

When the program starts, a message may tell you how many medicines expire within 6 months and how many are below their reorder level. Click it to jump to the list.

---

## 5. Medicines

**Add** — opens the medicine form:
- **Brand name** (required) and **Generic name**
- **Company** and **Formulation**
- **Category** (Tablet, Capsule, Syrup, Injection, Cream, Drops, …) and **Unit**
- **Tablets per box** — how many units are in one box / strip pack (1 for syrups and bottles)
- **Cost price (box)** and **Sale price (box)** — the program works out the per-tablet price by itself
- **Rack** — where it is kept on the shelf (shown on POS so staff can find it)
- **GST %**, **Barcode**, **Controlled** (shows a warning at sale), **Reorder level** (low-stock alert)

**Edit** — select a row, click Edit (or double-click the row). Change anything and save.

**Delete** — select a row, click Delete. The program first takes a backup, then the medicine **disappears everywhere at once**: POS search, the POS cart, Stock, Dashboard (stock value, expiring, low stock), Expiry and the start-up alert.
- If the medicine was **never bought or sold**, it is erased completely together with its stock (for typing mistakes).
- If it **has old bills or purchases**, those bills stay correct: the medicine is kept as hidden history and **its remaining stock is written off** (the write-off is recorded in Stock → Stock ledger with the note *"Medicine deleted"*).
- If the medicine was in an open POS cart, it is taken out of the cart the next time you open POS, and you are told.
- **To see deleted medicines:** tick **Show deleted** on the Medicines page.
- **To bring one back:** simply **Add** it again with the same name (the old record and its old bills are re-linked), or tick Show deleted → **Edit** → tick **Active**. Then enter its stock again with Restock or a purchase.

The program will not let you add a medicine that already exists (same brand name and tablets per box). It tells you to use **Edit** or **Restock** instead. This keeps your stock in one place.

**Excel template / Import Excel** — click *Excel template* to save an empty sheet, fill it in Excel, then *Import Excel* to add many medicines at once. Rows with problems are listed so you can fix them; medicines that already exist are not duplicated.

---

## 6. Stock

Three tabs:

- **Current stock** — total per medicine.
  - **Re-edit stock** — fix a wrong entry (batch number, expiry, quantity, cost, sale price). You must type a **reason**; the change is saved in the Audit log.
  - **Restock** — add more boxes of a medicine you already have (quick stock-in without a company bill).
- **By batch** — every batch with its expiry.
  - **Re-edit stock** — same as above for the selected batch.
  - **Adjust qty** — set the counted quantity after a physical stock check (reason required).
- **Stock ledger** — the full history of every stock in / out (purchase, sale, return, correction).

Stock can never go below zero: the POS refuses to sell more than you have, and **expired batches cannot be sold**.

---

## 7. Purchases (buying from a company)

**New purchase**
1. **Company** — pick from the list, or type a new name. If the name is new, the program asks *"Add it as a new company?"* → Yes.
2. **Invoice** number and **Date**.
3. Add each medicine line: medicine, **batch**, **expiry**, **quantity**, **cost** and **sale** price.
4. **Paid now** — how much you paid at delivery (0 if everything is on credit). It cannot be more than the bill.
5. Save. Stock goes up immediately and a backup is taken.

**Record payment** — select a purchase → pay part or all of what is still due on that bill.

**Purchase return** — select a purchase → choose the items and quantities you sent back to the company. Stock goes down and the company's due goes down.

**Delete purchase** — only for a purchase entered **by mistake**. You must type a reason. A backup is taken first, the stock it added is removed and the full details are kept in the Audit log. It is **not allowed** when:
- some of that stock was already sold (use **Stock → Re-edit stock** instead),
- it already has a return, or
- a company payment is linked to it.

---

## 8. Companies (the company is the supplier)

There is no separate "Suppliers" list. You buy from companies, so each company holds its own phone, address, purchases and dues.

- **Add** — name (required), phone, address, notes.
- **Edit** — change details. Renaming a company also updates the name on all its old purchases.
- **Pay company** — shows how much you owe that company and records a payment. The payment is applied to the oldest unpaid bills first. You cannot pay more than is owed.
- **Delete** — a company with no medicines, purchases or payments is erased. Otherwise it is **archived** (hidden) and all its history and dues stay. To bring it back: **Edit** → tick **Active** → Save.

Old data from earlier versions: every old "supplier" was automatically turned into a company with the same name, phone and address, and all its purchases and dues moved with it.

---

## 9. POS — selling

1. **Search** (F2): type part of the medicine name, generic name or scan the barcode. Pick it from the list. You will see rack, stock, batch, expiry and prices.
2. Choose **Sell tablets** or **Sell full box**. The **1 box** chip fills one box quickly.
3. Set the **quantity** and any **discount**, then **ADD TO CART**.
4. Repeat for more medicines. To remove a line, select it and press **Delete**. **Esc** or **Clear** empties the cart.
5. Choose the **payment method**: Cash, Card, Easypaisa, JazzCash or **Credit** (udhaar — pick the customer first).
6. Type what the customer **Paid**; the program shows the **Change** to give back.
7. Finish:
   - **Pay only** — saves the sale and shows the bill on screen.
   - **Pay + Print (F9)** — saves the sale and prints the bill.

Other buttons: **Hold (F8)** parks the current sale (for example while the customer fetches money) and **Resume** brings it back. **F10** reprints the last bill. **New month** closes the previous month if it was not closed yet (see section 15).

The sale is saved the moment you press Pay — even if printing fails, the sale is safe and can be reprinted from **Sales**.

---

## 10. Sales (old bills, returns, delete)

Select a bill, then:
- **View bill** — see it on screen.
- **Print 80mm** (thermal) or **Print A4**.
- **Return / refund** — the customer returned some items: choose items and quantities, type a reason. Stock goes back up, and the refund is taken off the sale total on the Home page and in reports.
- **Delete sale** — **Owner only**, any date. A backup is taken first. The bill is removed from Sales, the Home page, reports and the customer's udhaar. Tablets not already returned go back into stock (written in the stock ledger as "Sale deleted").

The **Total** column on the Sales page shows the amount after returns.

---

## 11. Customers and Udhaar (credit)

**Customers** — **Add** (name, phone, CNIC, address), **Edit**, **Delete**.
- A customer who **still owes udhaar cannot be deleted** — collect or settle first.
- A customer with old bills is **archived**, not erased.
- If you add a customer with the same name and phone as an existing one, the program asks first.

**Udhaar** page:
- **Udhaar** tab — everyone who owes money.
- **Overdue** tab — owed longer than the days set in Settings.
- **Customer ledger** tab — every credit sale and payment for a customer.
- **Record payment** — customer paid back (part or full).
- **Excel** — export the udhaar list.

---

## 12. Payables (money you owe companies)

- The list shows each **company** with its phone and total amount due.
- **Record payment** — pay a company.
- The history tab shows that company's purchases; the **Company ledger** tab shows purchases, payments and returns with the running balance.

---

## 13. Printer (80 mm thermal, for example Black Copper BC-86AC)

**Setup** (Settings):
1. **Printer** — select your thermal printer.
2. **Bill print mode** — keep **Direct ESC/POS (recommended)**. Each bill is sent as *one* job that feeds a few lines and cuts, so the paper stops right after the bill.
3. **Paper width (characters)** — 48 for 80 mm paper (use 32 for 58 mm).
4. **Blank lines before cut** — 4 is normal.
5. **Save**, then **Test print**. A short slip should print and stop.

**If the printer keeps printing again and again or prints old bills:**
1. Settings → **Printer status / clear stuck jobs**. It shows how many old jobs are waiting and offers to clear them. Say Yes.
2. When you print a bill and old jobs are waiting, the program asks: *Yes* = clear them and print, *No* = keep them, *Cancel* = do not print.
3. The same bill cannot be sent twice within 5 seconds, so double-clicking does not print twice.
4. If clearing fails: Windows **Settings → Printers** → select the printer → *Open queue* → cancel all.

**If nothing prints:** check the USB cable and power, check that the right printer is selected in Settings, use **Test print**. If the Windows driver shows the printer offline, turn it off and on. The sale is already saved — reprint it from **Sales → Print 80mm**.

---

## 14. Expiry and Reports

**Expiry** — tabs for 30, 60, 90 days, 6 months and **Expired**. Check it every week; return near-expiry stock to the company with **Purchases → Purchase return**.

**Reports** — choose a **Report** type, set **From / To** dates (or use *This week / This month / This year*), click **Generate**, then **Excel** or **PDF** to save it. Reports include daily sales, date-range sales, daily / weekly / monthly / yearly profit, top medicines, top customers, expiry, low stock, stock valuation, customer udhaar, company payables, sales by company / formulation, purchases and comparisons.

---

## 15. Month close

On the first login of a new month the program closes the previous month automatically and shows *"Previous month archived. The new month is open."* You can also press **Close last month** (Home / Reports) or **New month** (POS).

Closing a month **does not delete anything**. It saves a summary of that month (see **Reports → Closed months**) and takes a backup. All sales stay available for reports.

---

## 16. Users

- **Add** — username, role (**Owner** = everything, **Cashier** = POS, Stock, Sales, Reports), password (at least 6 characters).
- **Edit** — change username or role.
- **Change password** — for the selected user.
- **Disable / Enable** — stop a user from logging in (for example staff who left). Users are never erased so their old sales still show who made them.
- Safety: you cannot disable yourself, and the program always keeps at least one active owner so you can never be locked out of Settings.

**Audit** shows every important action: logins, sales, voids, returns, stock corrections, deletes, restores and settings changes.

---

## 17. Where your data is kept

Everything is in the `data` folder next to the program:

```
<the folder where you ran Setup>\
    HadiPharmacy.exe      <- the program
    _internal\                 <- program files (keep together with the exe)
    data\                      <- YOUR SHOP DATA — never delete
        pharmacy.db            <- medicines, stock, sales, udhaar, everything
        backups\               <- automatic backups
        bills\                 <- saved bills
```

Settings → **Data folder** shows this location, and **Open folder** opens it.

**Two guides are always kept next to HadiPharmacy.exe** (rewritten every time the program starts and closes):
- **User Guide.html** — this complete guide.
- **DATA AND RECOVERY - READ ME.txt** — the *exact* paths of your data, backups, safety copy and secondary backup on this computer, how many medicines / sales are inside, the latest backup file, and step-by-step what to do if the program is deleted, how to move it to another folder or another computer, and how to restore. A copy of it is also kept inside the `data` folder, so it travels with your data.

Extra safety copy (hidden): `C:\Users\<you>\AppData\Local\HadiPharmacy\mirror\pharmacy.db`.

The database is written safely after every action. A power cut will not corrupt it; at most the very last unsaved click is lost.

---

## 18. Backups — automatic and manual

**Automatic backups are taken:**
- once a day, when the program starts,
- when you **Logout** / close the program,
- after every **purchase**,
- before any **delete**,
- before a **restore**,
- when a month is closed.

Each backup is two files in `data\backups`: `pharmacy_<date>_<time>.db` (the full database) and `.xlsx` (the same data in Excel, readable without the program). If the owner was logged in, the files end in **.enc** and are locked with the owner password.

The program keeps every backup of the last 30 days and one per month for the last 12 months; older ones are removed automatically.

**Secondary backup** (Settings) — every backup is also copied to this folder. Use a USB drive or a Google Drive / OneDrive folder. If the USB is not plugged in, the copy waits and is sent the next time it is available. **Backup status** on Settings and Home turns into a WARNING if there is no backup for 2 days or the secondary copy is waiting.

**Manual:**
- **Backup now** — take a backup immediately.
- **Export everything** — one file with the full database, an Excel copy and instructions. It is `.zip` (or `.yms` when locked with the owner password). Use this to move to another computer.

**Good habit:** once a week, click **Export everything** and save the file to a USB or send it to yourself on WhatsApp / Google Drive.

---

## 19. Restore — getting data back

Use this when: the computer was changed, the database was damaged, or you want to go back to an earlier point.

1. Make sure the POS cart is empty.
2. Settings → **Restore** → Yes.
3. Pick a backup file: `pharmacy_….db`, `.db.enc`, an **Export everything** `.zip` or `.yms` file.
4. If the file is locked, the program asks for the **owner password that was used when the backup was made** (this may be your old password).
5. The program opens and checks the backup **before** touching anything, then shows: *number of medicines, number of sales, date of the last sale*. Check that it is the right one → Yes.
6. A backup of the current data is taken first (so even a restore can be undone), then the data is replaced. Log in again.

If the file is damaged, not a backup, or the password is wrong, the program says so and **your current data is not changed**.

---

## 20. Moving to a new computer

On the **old** computer:
1. Settings → **Export everything** → save to a USB drive (or, after Logout, copy the whole program folder including `data` to the USB).

On the **new** computer:
1. Run **HadiPharmacy-Setup.exe**.
2. **Option A (easiest):** close the program, copy your saved `data` folder next to the new `HadiPharmacy.exe` (replace the new empty one), then open the program. Log in with your usual password.
3. **Option B:** log in with `admin` / `admin123` → Settings → **Restore** → pick the exported file → enter the old owner password if asked → log in again with your usual password.
4. Set the **Printer** and **Secondary backup** folder again in Settings (these are per-computer).

---

## 21. Deleting old data safely

Nothing is deleted without asking, and a backup is taken first. The rule everywhere:

| Record | Never used | Has history |
|---|---|---|
| Medicine | Erased with its stock | Hidden, remaining stock written off, old bills kept |
| Company | Erased | Archived (hidden, dues stay) |
| Formulation | Erased | Archived |
| Customer | Erased | Archived; **blocked** if udhaar is still due |
| Purchase | Deleted with its stock (reason required) | Blocked if stock was sold / returned / paid — use Stock re-edit or Purchase return |
| Sale | Sales page → Delete sale (owner) | Removed everywhere; unreturned tablets go back to stock |
| User | — | Disable instead of delete |

Deleted items vanish from every screen straight away (POS, cart, Stock, Dashboard, Expiry, alerts, company and customer lists). Hidden history keeps every old bill and report correct. Tick **Show deleted** on the Medicines, Companies, Forms or Customers page to see them; to bring one back, **Edit** it and tick **Active** (a medicine can also simply be added again).

If you deleted something by mistake: Settings → **Restore** → pick the backup made just before the delete (file name contains the date and time).

---

## 22. Daily, weekly and monthly checklist

**Every day**
- Open the program; look at the start-up alert (expiry / low stock).
- Sell from **POS**. Enter every company delivery in **Purchases** the same day.
- At closing: check **Home** (today's sale and profit), then press **Logout**.

**Every week**
- **Expiry** page — return or discount near-expiry stock.
- **Udhaar → Overdue** — call customers.
- **Payables** — plan company payments.
- **Settings → Export everything** to USB / Drive.

**Every month**
- Month closes automatically on the first login. Check **Reports → Monthly profit**.
- Do a quick stock count of fast-moving items and correct with **Stock → Adjust qty**.

---

## 23. Common problems

| Problem | What to do |
|---|---|
| "The app is already running" | The program is already open (check the taskbar). If not, restart the computer. |
| Forgot the owner password | Log in with another owner account → Users → Change password. If there is no other owner, call support. Locked backups need the password they were made with. |
| Setup says the app is still open | Click Logout, close any bill window, run Setup again. Data is safe. |
| Printer prints again and again | Settings → Printer status / clear stuck jobs (section 13). |
| Wrong stock quantity | Stock → Re-edit stock or Adjust qty, with a reason. |
| Wrong purchase entered | Purchases → Delete purchase (if nothing sold yet) or Stock → Re-edit stock. |
| Customer returned medicine | Sales → select bill → Return / refund. |
| Medicine not showing on POS | It may be deleted (Medicines → tick Show deleted → Edit → Active, or Add it again), expired, or out of stock (Purchases / Restock). |
| Where exactly is my data? | Open **DATA AND RECOVERY - READ ME.txt** next to HadiPharmacy.exe — it lists the exact paths on this computer. |
| Backup status shows WARNING | Settings → Backup now. Plug in the USB for the secondary copy. |
| Computer crashed / new PC | Section 20. |

For help call **03716931861**.
