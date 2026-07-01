"""PySide6 desktop interface for PDF2EPUB AI."""

from __future__ import annotations

import logging
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from pdf2epub_ai.core.config import AiProviderName, AppConfig, OcrEngineName
from pdf2epub_ai.core.pipeline import ConversionPipeline
from pdf2epub_ai.exceptions import ConversionCancelledError
from pdf2epub_ai.ocr.engines import OcrEngineRegistry
from pdf2epub_ai.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Launch the PDF2EPUB AI desktop app."""

    configure_logging()
    try:
        from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal
        from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import (
            QApplication,
            QButtonGroup,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSpinBox,
            QSplitter,
            QStyle,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:
        raise RuntimeError(
            "PySide6 is required for the GUI. Install with: pip install .[gui]"
        ) from exc

    class LogEmitter(QObject):
        message = Signal(str)

    class LogBridge(logging.Handler):
        """Forward Python log records to the Qt event loop."""

        def __init__(self) -> None:
            super().__init__()
            self.emitter = LogEmitter()
            self.setFormatter(
                logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%H:%M:%S")
            )

        def emit(self, record: logging.LogRecord) -> None:
            self.emitter.message.emit(self.format(record))

    class ConversionWorker(QThread):
        progress_signal = Signal(int, int, str)
        preview_signal = Signal(int, str, str)
        finished_signal = Signal(str)
        error_signal = Signal(str)
        cancelled_signal = Signal()

        def __init__(
            self,
            input_pdf: Path,
            output_epub: Path,
            config: AppConfig,
            resume: bool,
        ) -> None:
            super().__init__()
            self.input_pdf = input_pdf
            self.output_epub = output_epub
            self.config = config
            self.resume = resume
            self._cancel_requested = False

        def request_cancel(self) -> None:
            self._cancel_requested = True

        def run(self) -> None:
            try:
                result = ConversionPipeline(self.config).convert(
                    self.input_pdf,
                    self.output_epub,
                    resume=self.resume,
                    progress=lambda current, total, message: self.progress_signal.emit(
                        current, total, message
                    ),
                    preview=lambda page, raw, repaired: self.preview_signal.emit(
                        page, raw, repaired
                    ),
                    cancelled=lambda: self._cancel_requested,
                )
                self.finished_signal.emit(str(result))
            except ConversionCancelledError:
                self.cancelled_signal.emit()
            except Exception as exc:
                LOGGER.exception("Conversion failed")
                self.error_signal.emit(str(exc))

    class DropZone(QFrame):
        file_dropped = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("dropZone")
            self.setAcceptDrops(True)
            self.setMinimumHeight(92)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 14, 16, 14)
            self.title = QLabel("PDF dosyasını buraya bırakın")
            self.title.setObjectName("dropTitle")
            self.path = QLabel("Dosya seçilmedi")
            self.path.setObjectName("mutedText")
            self.path.setWordWrap(True)
            layout.addWidget(self.title)
            layout.addWidget(self.path)

        def dragEnterEvent(self, event: QDragEnterEvent) -> None:
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()

        def dropEvent(self, event: QDropEvent) -> None:
            urls = event.mimeData().urls()
            if urls:
                self.file_dropped.emit(urls[0].toLocalFile())
                event.acceptProposedAction()

        def set_path(self, path: Path) -> None:
            self.title.setText(path.name)
            self.path.setText(str(path))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.settings = QSettings("PDF2EPUB AI", "Desktop")
            self.base_config = AppConfig.from_file(None)
            self.input_pdf: Path | None = None
            self.worker: ConversionWorker | None = None
            self.started_at = 0.0
            self.log_bridge = LogBridge()
            self.log_bridge.emitter.message.connect(self.append_log)
            logging.getLogger().addHandler(self.log_bridge)

            self.setWindowTitle("PDF2EPUB AI")
            self.setMinimumSize(1040, 720)
            self.resize(1260, 820)
            self.setAcceptDrops(True)
            self.setWindowIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
            )

            self._build_ui()
            self._load_settings()
            self._apply_theme()
            self._refresh_dependencies()

            self.clock = QTimer(self)
            self.clock.timeout.connect(self._update_elapsed)
            self.clock.start(1000)

        def _build_ui(self) -> None:
            root = QWidget()
            root_layout = QVBoxLayout(root)
            root_layout.setContentsMargins(22, 18, 22, 18)
            root_layout.setSpacing(14)
            root_layout.addLayout(self._build_header())

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setChildrenCollapsible(False)
            splitter.addWidget(self._build_settings_panel())
            splitter.addWidget(self._build_workspace())
            splitter.setSizes([390, 820])
            root_layout.addWidget(splitter, 1)
            root_layout.addLayout(self._build_footer())
            self.setCentralWidget(root)

        def _build_header(self) -> QHBoxLayout:
            layout = QHBoxLayout()
            brand = QVBoxLayout()
            title = QLabel("PDF2EPUB AI")
            title.setObjectName("brandTitle")
            self.header_status = QLabel("Hazır")
            self.header_status.setObjectName("mutedText")
            brand.addWidget(title)
            brand.addWidget(self.header_status)
            layout.addLayout(brand)
            layout.addStretch()

            self.mode_group = QButtonGroup(self)
            self.mode_group.setExclusive(True)
            self.ai_button = QPushButton("AI ile")
            self.rule_button = QPushButton("AI olmadan")
            for button in (self.ai_button, self.rule_button):
                button.setCheckable(True)
                button.setObjectName("modeButton")
                button.setMinimumSize(118, 38)
                self.mode_group.addButton(button)
            self.ai_button.setChecked(self.base_config.ai.provider != AiProviderName.RULE)
            self.rule_button.setChecked(not self.ai_button.isChecked())
            self.mode_group.buttonClicked.connect(self._sync_mode)
            layout.addWidget(self.ai_button)
            layout.addWidget(self.rule_button)

            self.theme_button = QPushButton()
            self.theme_button.setCheckable(True)
            self.theme_button.setToolTip("Koyu temayı değiştir")
            self.theme_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
            )
            self.theme_button.setFixedSize(38, 38)
            self.theme_button.clicked.connect(self._toggle_theme)
            layout.addWidget(self.theme_button)
            return layout

        def _build_settings_panel(self) -> QWidget:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            panel = QWidget()
            panel.setObjectName("settingsPanel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(0, 0, 12, 0)
            layout.setSpacing(12)

            source_group = QGroupBox("Kaynak")
            source_layout = QVBoxLayout(source_group)
            self.drop_zone = DropZone()
            self.drop_zone.file_dropped.connect(lambda path: self._set_input(Path(path)))
            source_layout.addWidget(self.drop_zone)
            choose = QPushButton("PDF seç")
            choose.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            choose.clicked.connect(self._choose_pdf)
            source_layout.addWidget(choose)
            layout.addWidget(source_group)

            metadata_group = QGroupBox("Kitap bilgileri")
            metadata_form = QFormLayout(metadata_group)
            self.title_edit = QLineEdit()
            self.author_edit = QLineEdit()
            self.language_combo = QComboBox()
            self.language_combo.addItems(["tr", "en", "de", "fr", "es"])
            metadata_form.addRow("Başlık", self.title_edit)
            metadata_form.addRow("Yazar", self.author_edit)
            metadata_form.addRow("Dil", self.language_combo)
            layout.addWidget(metadata_group)

            processing_group = QGroupBox("OCR ve sayfa işleme")
            processing_form = QFormLayout(processing_group)
            self.ocr_combo = QComboBox()
            self.ocr_combo.addItems([item.value for item in OcrEngineName])
            self.ocr_combo.setCurrentText(self.base_config.ocr.engine.value)
            self.dpi_spin = QSpinBox()
            self.dpi_spin.setRange(150, 600)
            self.dpi_spin.setSingleStep(50)
            self.dpi_spin.setValue(self.base_config.ocr.dpi)
            self.resume_check = QCheckBox("Kesilen işlemi sürdür")
            self.resume_check.setChecked(True)
            self.split_check = QCheckBox("Çift sayfaları ayır")
            self.split_check.setChecked(self.base_config.ocr.split_double_pages)
            self.keep_check = QCheckBox("Ara dosyaları koru")
            processing_form.addRow("OCR motoru", self.ocr_combo)
            processing_form.addRow("Çözünürlük", self.dpi_spin)
            processing_form.addRow("", self.resume_check)
            processing_form.addRow("", self.split_check)
            processing_form.addRow("", self.keep_check)
            layout.addWidget(processing_group)

            self.ai_group = QGroupBox("AI sağlayıcısı")
            ai_form = QFormLayout(self.ai_group)
            self.provider_combo = QComboBox()
            self.provider_combo.addItem("Ollama", AiProviderName.OLLAMA.value)
            self.provider_combo.addItem("OpenAI uyumlu", AiProviderName.OPENAI_COMPATIBLE.value)
            self.provider_combo.addItem("Lokal komut", AiProviderName.LOCAL.value)
            configured_index = self.provider_combo.findData(self.base_config.ai.provider.value)
            self.provider_combo.setCurrentIndex(max(0, configured_index))
            self.model_edit = QLineEdit(self.base_config.ai.model)
            self.url_edit = QLineEdit(self.base_config.ai.base_url)
            self.api_key_edit = QLineEdit()
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.timeout_spin = QSpinBox()
            self.timeout_spin.setRange(5, 900)
            self.timeout_spin.setValue(self.base_config.ai.timeout_seconds)
            ai_form.addRow("Sağlayıcı", self.provider_combo)
            ai_form.addRow("Model", self.model_edit)
            ai_form.addRow("Sunucu", self.url_edit)
            ai_form.addRow("API anahtarı", self.api_key_edit)
            ai_form.addRow("Zaman aşımı", self.timeout_spin)
            layout.addWidget(self.ai_group)

            output_group = QGroupBox("Çıktı")
            output_layout = QHBoxLayout(output_group)
            self.output_edit = QLineEdit()
            browse_output = QPushButton()
            browse_output.setToolTip("EPUB hedefini seç")
            browse_output.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
            )
            browse_output.setFixedWidth(40)
            browse_output.clicked.connect(self._choose_output)
            output_layout.addWidget(self.output_edit)
            output_layout.addWidget(browse_output)
            layout.addWidget(output_group)

            actions = QHBoxLayout()
            self.start_button = QPushButton("Dönüştür")
            self.start_button.setObjectName("primaryButton")
            self.start_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.start_button.clicked.connect(self._start_conversion)
            self.cancel_button = QPushButton("İptal")
            self.cancel_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton)
            )
            self.cancel_button.setEnabled(False)
            self.cancel_button.clicked.connect(self._cancel_conversion)
            actions.addWidget(self.start_button, 2)
            actions.addWidget(self.cancel_button, 1)
            layout.addLayout(actions)
            layout.addStretch()
            scroll.setWidget(panel)
            scroll.setMinimumWidth(360)
            return scroll

        def _build_workspace(self) -> QWidget:
            workspace = QWidget()
            layout = QVBoxLayout(workspace)
            layout.setContentsMargins(12, 0, 0, 0)
            layout.setSpacing(12)

            status_frame = QFrame()
            status_frame.setObjectName("statusFrame")
            status_layout = QGridLayout(status_frame)
            self.stage_label = QLabel("Dosya bekleniyor")
            self.stage_label.setObjectName("stageLabel")
            self.page_label = QLabel("0 / 0")
            self.page_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.elapsed_label = QLabel("00:00")
            self.elapsed_label.setObjectName("mutedText")
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
            status_layout.addWidget(self.stage_label, 0, 0)
            status_layout.addWidget(self.page_label, 0, 1)
            status_layout.addWidget(self.progress, 1, 0, 1, 2)
            status_layout.addWidget(self.elapsed_label, 2, 0)
            layout.addWidget(status_frame)

            self.tabs = QTabWidget()
            preview_page = QWidget()
            preview_layout = QHBoxLayout(preview_page)
            preview_layout.setContentsMargins(0, 10, 0, 0)
            raw_layout = QVBoxLayout()
            raw_layout.addWidget(QLabel("Ham OCR"))
            self.raw_preview = QPlainTextEdit()
            self.raw_preview.setReadOnly(True)
            raw_layout.addWidget(self.raw_preview)
            repaired_layout = QVBoxLayout()
            repaired_layout.addWidget(QLabel("Düzeltilmiş metin"))
            self.repaired_preview = QPlainTextEdit()
            self.repaired_preview.setReadOnly(True)
            repaired_layout.addWidget(self.repaired_preview)
            preview_layout.addLayout(raw_layout)
            preview_layout.addLayout(repaired_layout)
            self.tabs.addTab(preview_page, "Metin önizleme")

            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setMaximumBlockCount(3000)
            self.tabs.addTab(self.log_view, "İşlem günlüğü")

            system_page = QWidget()
            system_layout = QVBoxLayout(system_page)
            self.system_grid = QGridLayout()
            self.system_labels: dict[str, QLabel] = {}
            for row, (key, title) in enumerate(
                (("ocr", "OCR motoru"), ("ai", "AI sunucusu"), ("disk", "Disk alanı"))
            ):
                self.system_grid.addWidget(QLabel(title), row, 0)
                value = QLabel("Kontrol ediliyor")
                value.setObjectName("statusValue")
                self.system_labels[key] = value
                self.system_grid.addWidget(value, row, 1)
            refresh = QPushButton("Yeniden kontrol et")
            refresh.clicked.connect(self._refresh_dependencies)
            system_layout.addLayout(self.system_grid)
            system_layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
            system_layout.addStretch()
            self.tabs.addTab(system_page, "Sistem")
            layout.addWidget(self.tabs, 1)
            return workspace

        def _build_footer(self) -> QHBoxLayout:
            layout = QHBoxLayout()
            self.footer_mode = QLabel()
            self.footer_mode.setObjectName("mutedText")
            layout.addWidget(self.footer_mode)
            layout.addStretch()
            version = QLabel("EPUB 3 · Türkçe OCR")
            version.setObjectName("mutedText")
            layout.addWidget(version)
            self._sync_mode()
            return layout

        def _choose_pdf(self) -> None:
            filename, _ = QFileDialog.getOpenFileName(self, "PDF seç", "", "PDF (*.pdf)")
            if filename:
                self._set_input(Path(filename))

        def _set_input(self, path: Path) -> None:
            if path.suffix.casefold() != ".pdf" or not path.exists():
                QMessageBox.warning(self, "PDF2EPUB AI", "Geçerli bir PDF dosyası seçin.")
                return
            self.input_pdf = path
            self.drop_zone.set_path(path)
            self.output_edit.setText(str(path.with_suffix(".epub")))
            if not self.title_edit.text().strip():
                self.title_edit.setText(path.stem.replace("-", " ").title())
            self.stage_label.setText("Dönüşüme hazır")
            self.header_status.setText(str(path))
            self.append_log(f"PDF seçildi: {path}")

        def _choose_output(self) -> None:
            default = self.output_edit.text() or (
                str(self.input_pdf.with_suffix(".epub")) if self.input_pdf else "book.epub"
            )
            filename, _ = QFileDialog.getSaveFileName(self, "EPUB hedefi", default, "EPUB (*.epub)")
            if filename:
                self.output_edit.setText(filename)

        def _start_conversion(self) -> None:
            if self.input_pdf is None:
                QMessageBox.warning(self, "PDF2EPUB AI", "Önce bir PDF seçin.")
                return
            output = Path(self.output_edit.text().strip())
            if not output.name:
                QMessageBox.warning(self, "PDF2EPUB AI", "EPUB çıktı yolunu seçin.")
                return
            output.parent.mkdir(parents=True, exist_ok=True)
            config = self._build_config()
            self.worker = ConversionWorker(
                self.input_pdf,
                output,
                config,
                resume=self.resume_check.isChecked(),
            )
            self.worker.progress_signal.connect(self._on_progress)
            self.worker.preview_signal.connect(self._on_preview)
            self.worker.finished_signal.connect(self._on_finished)
            self.worker.error_signal.connect(self._on_error)
            self.worker.cancelled_signal.connect(self._on_cancelled)
            self._set_running(True)
            self.started_at = time.monotonic()
            self.progress.setValue(0)
            self.raw_preview.clear()
            self.repaired_preview.clear()
            self.stage_label.setText("Başlatılıyor")
            self.append_log(
                f"Dönüşüm başladı: {'AI ile' if self.ai_button.isChecked() else 'AI olmadan'}"
            )
            self._save_settings()
            self.worker.start()

        def _build_config(self) -> AppConfig:
            provider = (
                str(self.provider_combo.currentData())
                if self.ai_button.isChecked()
                else AiProviderName.RULE.value
            )
            return self.base_config.merged(
                {
                    "ocr.engine": self.ocr_combo.currentText(),
                    "ocr.language": "tur" if self.language_combo.currentText() == "tr" else "eng",
                    "ocr.dpi": self.dpi_spin.value(),
                    "ocr.split_double_pages": self.split_check.isChecked(),
                    "ai.provider": provider,
                    "ai.model": self.model_edit.text().strip(),
                    "ai.base_url": self.url_edit.text().strip(),
                    "ai.api_key": self.api_key_edit.text().strip() or None,
                    "ai.timeout_seconds": self.timeout_spin.value(),
                    "epub.title": self.title_edit.text().strip()
                    or (self.input_pdf.stem if self.input_pdf else "Untitled"),
                    "epub.author": self.author_edit.text().strip() or "Unknown",
                    "epub.language": self.language_combo.currentText(),
                    "performance.keep_temp": self.keep_check.isChecked(),
                }
            )

        def _cancel_conversion(self) -> None:
            if self.worker and self.worker.isRunning():
                self.worker.request_cancel()
                self.cancel_button.setEnabled(False)
                self.stage_label.setText("İptal ediliyor")
                self.append_log("İptal istendi; geçerli sayfa tamamlanınca duracak.")

        def _on_progress(self, current: int, total: int, message: str) -> None:
            percent = int(current / max(total, 1) * 100)
            self.progress.setValue(percent)
            self.page_label.setText(f"{current} / {total}")
            self.stage_label.setText(message)
            self.header_status.setText(f"%{percent} · {message}")

        def _on_preview(self, page: int, raw: str, repaired: str) -> None:
            self.raw_preview.setPlainText(raw)
            self.repaired_preview.setPlainText(repaired)
            self.tabs.setTabText(0, f"Metin önizleme · Sayfa {page}")

        def _on_finished(self, path: str) -> None:
            self._set_running(False)
            self.progress.setValue(100)
            self.stage_label.setText("EPUB hazır")
            self.header_status.setText(path)
            self.append_log(f"EPUB kaydedildi: {path}")
            QMessageBox.information(self, "PDF2EPUB AI", f"EPUB hazır:\n{path}")

        def _on_error(self, message: str) -> None:
            self._set_running(False)
            self.stage_label.setText("İşlem başarısız")
            self.header_status.setText(message)
            QMessageBox.critical(self, "PDF2EPUB AI", message)

        def _on_cancelled(self) -> None:
            self._set_running(False)
            self.stage_label.setText("İşlem iptal edildi")
            self.header_status.setText("Önbellek korundu")
            self.append_log("Dönüşüm iptal edildi; daha sonra sürdürülebilir.")

        def _set_running(self, running: bool) -> None:
            self.start_button.setEnabled(not running)
            self.cancel_button.setEnabled(running)
            self.ai_button.setEnabled(not running)
            self.rule_button.setEnabled(not running)

        def _sync_mode(self) -> None:
            ai_enabled = self.ai_button.isChecked()
            self.ai_group.setEnabled(ai_enabled)
            self.footer_mode.setText(
                "Mod: Lokal/API destekli OCR onarımı"
                if ai_enabled
                else "Mod: Kural tabanlı OCR onarımı"
            )

        def _toggle_theme(self) -> None:
            self.settings.setValue("dark_mode", self.theme_button.isChecked())
            self._apply_theme()

        def _apply_theme(self) -> None:
            dark = self.theme_button.isChecked()
            colors = {
                "bg": "#15191d" if dark else "#f3f5f6",
                "panel": "#1d2328" if dark else "#ffffff",
                "field": "#111518" if dark else "#f8fafb",
                "text": "#edf1f2" if dark else "#172126",
                "muted": "#94a3aa" if dark else "#62737b",
                "border": "#344047" if dark else "#d7dfe2",
                "accent": "#2db39f" if dark else "#087f6f",
                "accent_hover": "#35c8b1" if dark else "#06695d",
                "danger": "#dc6b63" if dark else "#b8403a",
            }
            css = [
                "QMainWindow, QWidget {",
                f"  background: {colors['bg']}; color: {colors['text']}; font-size: 13px;",
                "}",
                "QLabel#brandTitle { font-size: 24px; font-weight: 700; }",
                "QLabel#dropTitle, QLabel#stageLabel { font-size: 15px; font-weight: 600; }",
                f"QLabel#mutedText {{ color: {colors['muted']}; }}",
                "QGroupBox {",
                f"  background: {colors['panel']}; border: 1px solid {colors['border']};",
                "  border-radius: 6px; margin-top: 9px; padding: 14px 10px 10px 10px;",
                "  font-weight: 600;",
                "}",
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }",
                "QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {",
                f"  background: {colors['field']}; border: 1px solid {colors['border']};",
                "  border-radius: 5px; padding: 7px;",
                f"  selection-background-color: {colors['accent']};",
                "}",
                "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {",
                f"  border-color: {colors['accent']};",
                "}",
                "QPushButton {",
                f"  background: {colors['panel']}; border: 1px solid {colors['border']};",
                "  border-radius: 5px; padding: 8px 12px;",
                "}",
                f"QPushButton:hover {{ border-color: {colors['accent']}; }}",
                f"QPushButton:disabled {{ color: {colors['muted']}; }}",
                "QPushButton#primaryButton, QPushButton#modeButton:checked {",
                f"  background: {colors['accent']}; border-color: {colors['accent']};",
                "  color: white; font-weight: 700;",
                "}",
                f"QPushButton#primaryButton:hover {{ background: {colors['accent_hover']}; }}",
                "QFrame#dropZone {",
                f"  background: {colors['field']}; border: 1px dashed {colors['accent']};",
                "  border-radius: 6px;",
                "}",
                "QFrame#statusFrame {",
                f"  background: {colors['panel']}; border: 1px solid {colors['border']};",
                "  border-radius: 6px;",
                "}",
                "QProgressBar {",
                f"  background: {colors['field']}; border: 0; border-radius: 4px;",
                "  min-height: 8px; max-height: 8px;",
                "}",
                f"QProgressBar::chunk {{ background: {colors['accent']}; border-radius: 4px; }}",
                "QTabWidget::pane {",
                f"  border: 1px solid {colors['border']}; background: {colors['panel']};",
                "}",
                "QTabBar::tab {",
                f"  background: {colors['bg']}; border: 1px solid {colors['border']};",
                "  padding: 9px 14px;",
                "}",
                "QTabBar::tab:selected {",
                f"  background: {colors['panel']}; color: {colors['accent']};",
                f"  border-bottom-color: {colors['panel']};",
                "}",
                "QScrollArea { border: 0; }",
            ]
            self.setStyleSheet("\n".join(css))

        def _refresh_dependencies(self) -> None:
            try:
                engine = OcrEngineRegistry(self._build_config().ocr).get(
                    OcrEngineName(self.ocr_combo.currentText())
                )
                self._set_system_status("ocr", f"Hazır · {engine.name.value}", True)
            except Exception as exc:
                self._set_system_status("ocr", str(exc), False)
            try:
                url = self.url_edit.text().strip().rstrip("/") + "/api/tags"
                with urllib.request.urlopen(url, timeout=2) as response:
                    ai_ready = response.status == 200
                self._set_system_status("ai", "Hazır" if ai_ready else "Yanıt yok", ai_ready)
            except (urllib.error.URLError, TimeoutError, ValueError):
                self._set_system_status("ai", "Bağlantı yok", False)
            free_gb = shutil.disk_usage(Path.cwd()).free / (1024**3)
            self._set_system_status("disk", f"{free_gb:.1f} GB boş", free_gb >= 5)

        def _set_system_status(self, key: str, text: str, ready: bool) -> None:
            label = self.system_labels[key]
            label.setText(text)
            label.setStyleSheet(f"color: {'#2db39f' if ready else '#d95d55'}; font-weight: 600;")

        def append_log(self, message: str) -> None:
            if hasattr(self, "log_view"):
                self.log_view.appendPlainText(message)

        def _update_elapsed(self) -> None:
            if self.worker and self.worker.isRunning() and self.started_at:
                elapsed = int(time.monotonic() - self.started_at)
                self.elapsed_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")

        def _save_settings(self) -> None:
            self.settings.setValue("dark_mode", self.theme_button.isChecked())
            self.settings.setValue("ocr", self.ocr_combo.currentText())
            self.settings.setValue("dpi", self.dpi_spin.value())
            self.settings.setValue("model", self.model_edit.text())
            self.settings.setValue("url", self.url_edit.text())
            self.settings.setValue("provider", self.provider_combo.currentData())
            self.settings.setValue("ai_mode", self.ai_button.isChecked())

        def _load_settings(self) -> None:
            self.theme_button.setChecked(self.settings.value("dark_mode", True, bool))
            self.ocr_combo.setCurrentText(
                str(self.settings.value("ocr", self.base_config.ocr.engine.value))
            )
            self.dpi_spin.setValue(int(self.settings.value("dpi", self.base_config.ocr.dpi)))
            self.model_edit.setText(str(self.settings.value("model", self.base_config.ai.model)))
            self.url_edit.setText(str(self.settings.value("url", self.base_config.ai.base_url)))
            provider = str(self.settings.value("provider", self.base_config.ai.provider.value))
            provider_index = self.provider_combo.findData(provider)
            if provider_index >= 0:
                self.provider_combo.setCurrentIndex(provider_index)
            ai_mode = self.settings.value(
                "ai_mode", self.base_config.ai.provider != AiProviderName.RULE, bool
            )
            self.ai_button.setChecked(ai_mode)
            self.rule_button.setChecked(not ai_mode)
            self._sync_mode()

        def dragEnterEvent(self, event: QDragEnterEvent) -> None:
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()

        def dropEvent(self, event: QDropEvent) -> None:
            urls = event.mimeData().urls()
            if urls:
                self._set_input(Path(urls[0].toLocalFile()))
                event.acceptProposedAction()

        def closeEvent(self, event: QCloseEvent) -> None:
            if self.worker and self.worker.isRunning():
                answer = QMessageBox.question(
                    self,
                    "PDF2EPUB AI",
                    "Dönüşüm sürüyor. İşlemi iptal edip çıkılsın mı?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                self.worker.request_cancel()
                self.worker.wait(5000)
            logging.getLogger().removeHandler(self.log_bridge)
            self._save_settings()
            event.accept()

    app = QApplication(sys.argv)
    app.setApplicationName("PDF2EPUB AI")
    app.setOrganizationName("PDF2EPUB AI")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
