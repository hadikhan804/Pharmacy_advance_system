from __future__ import annotations

from pathlib import Path

from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_TITLE
from app.i18n import i18n, t
from app.services import backup_service, settings_service
from app.ui.widgets.helpers import error, info


class SetupWizard(QDialog):
    def __init__(self, parent=None, recover_mode: bool = True):
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE + " — " + t("setup_title"))
        self.setModal(True)
        self.resize(680, 560)
        self._restored = False
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.page_recover = QWidget()
        r = QVBoxLayout(self.page_recover)
        title = QLabel(t("recover_data"))
        title.setObjectName("PageHeading")
        r.addWidget(title)
        hint = QLabel(t("recover_hint"))
        hint.setWordWrap(True)
        r.addWidget(hint)
        self.found = QListWidget()
        for p in backup_service.scan_recover_candidates():
            self.found.addItem(str(p))
        r.addWidget(self.found, 1)
        browse = QPushButton(t("choose_file"))
        browse.clicked.connect(self._browse_recover)
        restore_btn = QPushButton(t("restore_selected"))
        restore_btn.setObjectName("GoldBtn")
        restore_btn.clicked.connect(self._restore_selected)
        r.addWidget(browse)
        r.addWidget(restore_btn)
        self.stack.addWidget(self.page_recover)

        self.page_info = QWidget()
        form = QFormLayout(self.page_info)
        d = settings_service.pharmacy_info()
        self.name = QLineEdit(d["name"] or APP_TITLE)
        self.address = QLineEdit(d["address"])
        self.phone = QLineEdit(d["phone"])
        self.ntn = QLineEdit(d["ntn"])
        self.logo = QLineEdit(d.get("logo_path") or "")
        logo_row = QHBoxLayout()
        logo_btn = QPushButton(t("choose_file"))
        logo_btn.clicked.connect(self._pick_logo)
        logo_row.addWidget(self.logo)
        logo_row.addWidget(logo_btn)
        logo_w = QWidget()
        logo_w.setLayout(logo_row)
        self.gst = QSpinBox()
        self.gst.setRange(0, 100)
        try:
            self.gst.setValue(int(float(d["default_gst"] or 0)))
        except ValueError:
            pass
        self.lang = QComboBox()
        self.lang.addItem(t("english"), "en")
        self.lang.addItem(t("urdu"), "ur")
        idx = self.lang.findData(d.get("language") or "en")
        if idx >= 0:
            self.lang.setCurrentIndex(idx)
        self.printer = QComboBox()
        self.printer.addItem("")
        for p in QPrinterInfo.availablePrinterNames():
            self.printer.addItem(p)
        if d.get("printer_name"):
            pidx = self.printer.findText(d["printer_name"])
            if pidx >= 0:
                self.printer.setCurrentIndex(pidx)
        form.addRow(t("pharmacy_name"), self.name)
        form.addRow(t("address"), self.address)
        form.addRow(t("phone"), self.phone)
        form.addRow(t("ntn"), self.ntn)
        form.addRow(t("logo"), logo_w)
        form.addRow(t("default_gst"), self.gst)
        form.addRow(t("language"), self.lang)
        form.addRow(t("printer"), self.printer)
        self.stack.addWidget(self.page_info)

        self.page_backup = QWidget()
        b = QVBoxLayout(self.page_backup)
        btitle = QLabel(t("secondary_backup"))
        btitle.setObjectName("PageHeading")
        b.addWidget(btitle)
        bhint = QLabel(t("secondary_backup_hint"))
        bhint.setWordWrap(True)
        b.addWidget(bhint)
        self.secondary = QComboBox()
        self.secondary.setEditable(True)
        for p in backup_service.suggested_secondary_folders():
            self.secondary.addItem(str(p))
        if d.get("secondary_backup_folder"):
            self.secondary.setCurrentText(d["secondary_backup_folder"])
        pick = QPushButton(t("choose_folder"))
        pick.clicked.connect(self._pick_secondary)
        b.addWidget(self.secondary)
        b.addWidget(pick)
        b.addStretch()
        self.stack.addWidget(self.page_backup)

        nav = QHBoxLayout()
        self.back_btn = QPushButton(t("back"))
        self.next_btn = QPushButton(t("next"))
        self.next_btn.setObjectName("GoldBtn")
        self.back_btn.clicked.connect(self._back)
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        layout.addLayout(nav)
        if not recover_mode:
            self.stack.setCurrentIndex(1)
        self._sync_nav()

    def _sync_nav(self) -> None:
        i = self.stack.currentIndex()
        self.back_btn.setEnabled(i > 0)
        if i == 0:
            self.next_btn.setText(t("skip_new"))
        elif i == self.stack.count() - 1:
            self.next_btn.setText(t("finish"))
        else:
            self.next_btn.setText(t("next"))

    def _back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync_nav()

    def _next(self) -> None:
        if self.stack.currentIndex() < self.stack.count() - 1:
            self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
            self._sync_nav()
            return
        if not self.name.text().strip():
            error(self, t("required"))
            return
        settings_service.set_value("pharmacy_name", self.name.text().strip())
        settings_service.set_value("pharmacy_address", self.address.text())
        settings_service.set_value("pharmacy_phone", self.phone.text())
        settings_service.set_value("ntn", self.ntn.text())
        settings_service.set_value("logo_path", self.logo.text())
        settings_service.set_value("default_gst", str(self.gst.value()))
        settings_service.set_value("printer_name", self.printer.currentText())
        lang = self.lang.currentData() or "en"
        settings_service.set_value("language", lang)
        i18n.load(lang)
        secondary = self.secondary.currentText().strip()
        if secondary:
            Path(secondary).mkdir(parents=True, exist_ok=True)
            settings_service.set_value("secondary_backup_folder", secondary)
        settings_service.set_value("setup_complete", "1")
        self.accept()

    def _pick_secondary(self) -> None:
        path = QFileDialog.getExistingDirectory(self, t("backup_folder"))
        if path:
            self.secondary.setCurrentText(path)

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("logo"), "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.logo.setText(path)

    def _browse_recover(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("restore"), "", "Backups (*.db *.enc *.yms *.zip);;All (*.*)"
        )
        if path:
            self.found.addItem(path)
            self.found.setCurrentRow(self.found.count() - 1)

    def _restore_selected(self) -> None:
        item = self.found.currentItem()
        if not item:
            error(self, t("select_row"))
            return
        password = None
        try:
            backup_service.check_backup(item.text())
        except backup_service.PasswordNeeded as exc:
            from PySide6.QtWidgets import QInputDialog, QLineEdit

            password, ok = QInputDialog.getText(self, t("restore"), str(exc), QLineEdit.EchoMode.Password)
            if not ok:
                return
        except Exception as exc:
            error(self, exc)
            return
        try:
            backup_service.restore_from(item.text(), password)
            self._restored = True
            d = settings_service.pharmacy_info()
            self.name.setText(d["name"] or APP_TITLE)
            self.address.setText(d["address"])
            self.phone.setText(d["phone"])
            self.ntn.setText(d["ntn"])
            self.logo.setText(d.get("logo_path") or "")
            info(self, t("restore_done"))
            self.stack.setCurrentIndex(1)
            self._sync_nav()
        except Exception as exc:
            error(self, exc)

    def reject(self) -> None:
        error(self, t("setup_required"))
