"""Speech-to-Text settings page — model selection and download."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings

_MODELS = {
    "tiny.en": ("~75 MB", "Fastest, lower accuracy — good for simple commands"),
    "base.en": ("~145 MB", "Recommended — best speed/accuracy balance"),
    "small.en": ("~465 MB", "Higher accuracy, slower on CPU"),
    "medium.en": ("~1.5 GB", "Highest accuracy, requires a fast CPU"),
}


class _DownloadThread(QThread):
    progress = Signal(int, str)  # percent, status text
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, model_size: str) -> None:
        super().__init__()
        self._model_size = model_size

    def run(self) -> None:
        try:
            from nova.stt import ModelManager

            mgr = ModelManager()
            if mgr.is_model_cached(self._model_size):
                self.progress.emit(100, "Already downloaded ✓")
                self.finished_ok.emit()
                return
            self.progress.emit(5, "Connecting to HuggingFace…")
            mgr.download_model(self._model_size)
            self.progress.emit(100, "Download complete ✓")
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class STTPage(QWidget):
    """STT model selection and cache management."""

    def __init__(self, settings: NovaSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._download_thread: _DownloadThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        model_group = QGroupBox("Whisper Model (runs 100% offline on your CPU)")
        form = QFormLayout(model_group)

        self._model_combo = QComboBox()
        for name, (size, _desc) in _MODELS.items():
            self._model_combo.addItem(f"{name}  ({size})", userData=name)
        # Select current
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == self._settings.stt.model_size:
                self._model_combo.setCurrentIndex(i)
                break
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        form.addRow("Model:", self._model_combo)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: grey; font-size: 11px;")
        form.addRow("", self._desc_label)
        self._update_desc()

        self._cache_status = QLabel()
        form.addRow("Status:", self._cache_status)
        self._refresh_cache_status()

        self._download_btn = QPushButton("⬇  Download Model")
        self._download_btn.clicked.connect(self._start_download)
        form.addRow(self._download_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        form.addRow(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("font-size: 11px;")
        form.addRow(self._progress_label)

        layout.addWidget(model_group)
        layout.addStretch()

    def _update_desc(self) -> None:
        name = self._model_combo.currentData()
        _, desc = _MODELS.get(name, ("", ""))
        self._desc_label.setText(desc)

    def _refresh_cache_status(self) -> None:
        try:
            from nova.stt import ModelManager

            mgr = ModelManager()
            model = self._model_combo.currentData()
            cached = mgr.is_model_cached(model)
            self._cache_status.setText(
                "✅ Downloaded & ready" if cached else "⬇ Not yet downloaded"
            )
            self._cache_status.setStyleSheet("color: #10B981;" if cached else "color: #F59E0B;")
            self._download_btn.setEnabled(not cached)
        except Exception:
            self._cache_status.setText("Unknown")

    def _on_model_changed(self) -> None:
        self._update_desc()
        self._refresh_cache_status()

    def _start_download(self) -> None:
        if self._download_thread and self._download_thread.isRunning():
            return
        model = self._model_combo.currentData()
        self._download_thread = _DownloadThread(model)
        self._download_thread.progress.connect(self._on_progress)
        self._download_thread.finished_ok.connect(self._on_download_done)
        self._download_thread.failed.connect(self._on_download_failed)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._download_btn.setEnabled(False)
        self._download_thread.start()

    def _on_progress(self, percent: int, text: str) -> None:
        self._progress_bar.setValue(percent)
        self._progress_label.setText(text)

    def _on_download_done(self) -> None:
        self._progress_bar.setVisible(False)
        self._refresh_cache_status()

    def _on_download_failed(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText(f"❌ Download failed: {error}")
        self._download_btn.setEnabled(True)

    def apply_to(self, settings: NovaSettings) -> None:
        settings.stt.model_size = self._model_combo.currentData()
