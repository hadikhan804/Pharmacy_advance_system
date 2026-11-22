from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import data_dir
from app.i18n import t
from app.printing import escpos, receipt
from app.services import backup_service, settings_service
from app.ui.widgets.helpers import ask, error, info


class SettingsPage(QWidget):
    def __init__(self, apply_language, pos_is_open, logout):
        super().__init__()
        self.apply_language = apply_language
        self.pos_is_open = pos_is_open
        self.logout = logout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        form = QFormLayout()
        self.name = QLineEdit()
        self.address = QLineEdit()
        self.phone = QLineEdit()
        self.ntn = QLineEdit()
        self.logo = QLineEdit()
        logo_row = QHBoxLayout()
        logo_btn = QPushButton(t("choose_file"))
        logo_btn.clicked.connect(self._logo)
        logo_row.addWidget(self.logo)
        logo_row.addWidget(logo_btn)
        logo_w = QWidget()
        logo_w.setLayout(logo_row)
        self.footer_en = QTextEdit()
        self.footer_en.setMaximumHeight(70)
        self.footer_ur = QTextEdit()
        self.footer_ur.setMaximumHeight(70)
        self.printer = QComboBox()
        self.printer.addItem("")
        for p in QPrinterInfo.availablePrinterNames():
            self.printer.addItem(p)
        self.gst = QSpinBox()
        self.gst.setRange(0, 100)
        self.lang = QComboBox()
        self.lang.addItem(t("english"), "en")
        self.lang.addItem(t("urdu"), "ur")
        self.backup = QLineEdit()
        b_row = QHBoxLayout()
        b_btn = QPushButton(t("choose_folder"))
        b_btn.clicked.connect(self._folder)
        b_row.addWidget(self.backup)
        b_row.addWidget(b_btn)
        b_w = QWidget()
        b_w.setLayout(b_row)
        self.secondary = QLineEdit()
        s_row = QHBoxLayout()
        s_btn = QPushButton(t("choose_folder"))
        s_btn.clicked.connect(self._folder_secondary)
        s_row.addWidget(self.secondary)
        s_row.addWidget(s_btn)
        s_w = QWidget()
        s_w.setLayout(s_row)
        self.bak_status = QLabel()
        self.bak_status.setWordWrap(True)
        self.bak_status.setObjectName("WarnText")
        self.retention = QListWidget()
        self.retention.setMaximumHeight(140)
        self.alerts = QLineEdit()
        self.overdue = QSpinBox()
        self.overdue.setRange(1, 365)
        form.addRow(t("pharmacy_name"), self.name)
        form.addRow(t("address"), self.address)
        form.addRow(t("phone"), self.phone)
        form.addRow(t("ntn"), self.ntn)
        form.addRow(t("logo"), logo_w)
        form.addRow(t("footer_en"), self.footer_en)
        form.addRow(t("footer_ur"), self.footer_ur)
        form.addRow(t("printer"), self.printer)
        self.receipt_mode = QComboBox()
        self.receipt_mode.addItem(t("receipt_mode_direct"), "direct")
        self.receipt_mode.addItem(t("receipt_mode_driver"), "driver")
        form.addRow(t("receipt_mode"), self.receipt_mode)
        self.paper = QComboBox()
        self.paper.addItem("80 mm (48)", "48")
        self.paper.addItem("80 mm (42)", "42")
        self.paper.addItem("58 mm (32)", "32")
        form.addRow(t("paper_width"), self.paper)
        self.feed = QSpinBox()
        self.feed.setRange(0, 10)
        form.addRow(t("feed_before_cut"), self.feed)
        p_row = QHBoxLayout()
        self.test_btn = QPushButton(t("test_print"))
        self.test_btn.setObjectName("GhostBtn")
        self.test_btn.clicked.connect(self._test_print)
        self.queue_btn = QPushButton(t("printer_state"))
        self.queue_btn.setObjectName("GhostBtn")
        self.queue_btn.clicked.connect(self._printer_state)
        p_row.addWidget(self.test_btn)
        p_row.addWidget(self.queue_btn)
        p_row.addStretch()
        p_w = QWidget()
        p_w.setLayout(p_row)
        form.addRow("", p_w)
        self.printer_hint = QLabel(t("printer_hint"))
        self.printer_hint.setWordWrap(True)
        self.printer_hint.setObjectName("Muted")
        form.addRow("", self.printer_hint)
        d_row = QHBoxLayout()
        self.data_lab = QLineEdit(str(data_dir()))
        self.data_lab.setReadOnly(True)
        self.data_btn = QPushButton(t("open_folder"))
        self.data_btn.setObjectName("GhostBtn")
        self.data_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        d_row.addWidget(self.data_lab)
        d_row.addWidget(self.data_btn)
        d_w = QWidget()
        d_w.setLayout(d_row)
        form.addRow(t("data_folder"), d_w)
        form.addRow(t("default_gst"), self.gst)
        form.addRow(t("language"), self.lang)
        form.addRow(t("backup_folder"), b_w)
        form.addRow(t("secondary_backup"), s_w)
        form.addRow(t("backup_status"), self.bak_status)
        form.addRow(t("retention"), self.retention)
        form.addRow(t("alert_days"), self.alerts)
        form.addRow(t("overdue_days"), self.overdue)
        layout.addLayout(form)
        btns = QHBoxLayout()
        self.save_btn = QPushButton(t("save"))
        self.save_btn.setObjectName("GoldBtn")
        self.bak_btn = QPushButton(t("backup_now"))
        self.exp_btn = QPushButton(t("export_everything"))
        self.res_btn = QPushButton(t("restore"))
        self.save_btn.clicked.connect(self._save)
        self.bak_btn.clicked.connect(self._backup)
        self.exp_btn.clicked.connect(self._export_all)
        self.res_btn.clicked.connect(self._restore)
        btns.addWidget(self.save_btn)
        btns.addWidget(self.bak_btn)
        btns.addWidget(self.exp_btn)
        btns.addWidget(self.res_btn)
        layout.addLayout(btns)
        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._load()

    def retranslate(self) -> None:
        self.save_btn.setText(t("save"))
        self.bak_btn.setText(t("backup_now"))
        self.exp_btn.setText(t("export_everything"))
        self.res_btn.setText(t("restore"))
        self.printer_hint.setText(t("printer_hint"))
        self.test_btn.setText(t("test_print"))
        self.queue_btn.setText(t("printer_state"))
        self.data_btn.setText(t("open_folder"))
        self._load()

    def reload(self) -> None:
        self._load()

    def _load(self) -> None:
        d = settings_service.pharmacy_info()
        self.name.setText(d["name"])
        self.address.setText(d["address"])
        self.phone.setText(d["phone"])
        self.ntn.setText(d["ntn"])
        self.logo.setText(d["logo_path"])
        self.footer_en.setPlainText(d["footer_en"])
        self.footer_ur.setPlainText(d["footer_ur"])
        idx = self.printer.findText(d["printer_name"])
        if idx >= 0:
            self.printer.setCurrentIndex(idx)
        idx = self.receipt_mode.findData(settings_service.get("receipt_mode", "direct") or "direct")
        self.receipt_mode.setCurrentIndex(max(idx, 0))
        idx = self.paper.findData(settings_service.get("thermal_width", "48") or "48")
        self.paper.setCurrentIndex(max(idx, 0))
        try:
            self.feed.setValue(int(settings_service.get("thermal_feed", "4") or 4))
        except ValueError:
            self.feed.setValue(4)
        try:
            self.gst.setValue(int(float(d["default_gst"] or 0)))
        except ValueError:
            self.gst.setValue(0)
        idx = self.lang.findData(d["language"] or "en")
        if idx >= 0:
            self.lang.setCurrentIndex(idx)
        self.backup.setText(d["backup_folder"])
        self.secondary.setText(d.get("secondary_backup_folder") or "")
        self.alerts.setText(d["expiry_alert_days"])
        self.overdue.setValue(int(d["udhaar_overdue_days"] or 30))
        st = backup_service.status()
        warn = t("backup_warning") if st["warning"] else t("backup_ok")
        self.bak_status.setText(f"{warn}\n{t('last_verified')}: {st['last_verified'] or '—'}")
        self.bak_status.setStyleSheet(
            "color:#f87171; font-weight:700;" if st["warning"] else "color:#34d399; font-weight:700;"
        )
        self.retention.clear()
        for row in backup_service.list_backups(20):
            ok = "ok" if row.get("integrity_ok") else "fail"
            self.retention.addItem(f"{row.get('ts','')}  {row.get('triggered_by','')}  {row.get('kind','')}  {ok}")

    def _folder_secondary(self) -> None:
        path = QFileDialog.getExistingDirectory(self, t("secondary_backup"))
        if path:
            self.secondary.setText(path)

    def _export_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("export_everything"), "HadiPharmacy_export.yms", "Backup (*.yms *.zip)"
        )
        if not path:
            return
        try:
            out = backup_service.export_everything(path)
            info(self, f"{t('success')}\n{out}")
        except Exception as exc:
            error(self, exc)

    def _logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("logo"), "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.logo.setText(path)

    def _folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, t("backup_folder"))
        if path:
            self.backup.setText(path)

    def _save(self) -> None:
        settings_service.set_value("pharmacy_name", self.name.text())
        settings_service.set_value("pharmacy_address", self.address.text())
        settings_service.set_value("pharmacy_phone", self.phone.text())
        settings_service.set_value("ntn", self.ntn.text())
        settings_service.set_value("logo_path", self.logo.text())
        settings_service.set_value("receipt_footer_en", self.footer_en.toPlainText())
        settings_service.set_value("receipt_footer_ur", self.footer_ur.toPlainText())
        self._save_printer()
        settings_service.set_value("default_gst", str(self.gst.value()))
        settings_service.set_value("backup_folder", self.backup.text())
        settings_service.set_value("secondary_backup_folder", self.secondary.text())
        settings_service.set_value("expiry_alert_days", self.alerts.text())
        settings_service.set_value("udhaar_overdue_days", str(self.overdue.value()))
        lang = self.lang.currentData()
        settings_service.set_value("language", lang)
        info(self, t("success"))
        self.apply_language(lang)

    def _save_printer(self) -> None:
        settings_service.set_value("printer_name", self.printer.currentText())
        settings_service.set_value("receipt_mode", self.receipt_mode.currentData())
        settings_service.set_value("thermal_width", self.paper.currentData())
        settings_service.set_value("thermal_feed", str(self.feed.value()))

    def _test_print(self) -> None:
        self._save_printer()
        if receipt.print_test_slip(self):
            info(self, t("test_sent"))
        self._load()

    def _printer_state(self) -> None:
        self._save_printer()
        name = self.printer.currentText() or escpos.default_printer()
        if not name:
            error(self, t("no_printers"))
            return
        try:
            st = escpos.printer_state(name)
        except OSError as exc:
            error(self, exc)
            return
        status = ", ".join(st["status"]) or "ready"
        msg = f"{name}\n{t('port')}: {st['port']}\n{t('status')}: {status}\n{t('jobs_waiting')}: {st['jobs']}"
        if st["jobs"] and ask(self, msg + "\n\n" + t("clear_queue_q")):
            try:
                escpos.purge_queue(name)
                info(self, t("queue_cleared"))
            except OSError as exc:
                error(self, f"{t('queue_clear_failed')}\n{exc}")
        elif not st["jobs"]:
            info(self, msg)

    def _backup(self) -> None:
        try:
            path = backup_service.backup_to(self.backup.text() or None)
            info(self, f"{t('backup_done')}\n{path}")
            self._load()
        except Exception as exc:
            error(self, exc)

    def _restore(self) -> None:
        if self.pos_is_open():
            error(self, t("no_open_sale"))
            return
        if not ask(self, t("restore_confirm")):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, t("restore"), self.backup.text(), "Backups (*.db *.enc *.yms *.zip);;All (*.*)"
        )
        if not path:
            return
        password = None
        while True:
            try:
                found = backup_service.check_backup(path, password)
                break
            except backup_service.PasswordNeeded as exc:
                password, ok = QInputDialog.getText(
                    self, t("restore"), f"{exc}\n\n{t('backup_password')}", QLineEdit.EchoMode.Password
                )
                if not ok or not password:
                    return
            except Exception as exc:
                error(self, exc)
                return
        summary = (
            t("restore_summary")
            .replace("{medicines}", str(found["medicines"]))
            .replace("{sales}", str(found["sales"]))
            .replace("{last}", found["last_sale"] or "—")
        )
        if not ask(self, summary):
            return
        try:
            backup_service.restore_from(path, password)
            info(self, t("restore_done"))
            self.logout()
        except Exception as exc:
            error(self, exc)
