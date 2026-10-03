"""LLM and AI settings page — provider strategy, models, and API keys."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings, SettingsManager
from nova.llm.credentials import (
    get_agnes_api_key,
    get_gemini_api_key,
    set_agnes_api_key,
    set_gemini_api_key,
)


class LLMPage(QWidget):
    """Configuration page for Tier 2 LLM providers, cascading, and API keys."""

    def __init__(
        self,
        settings: NovaSettings,
        settings_manager: SettingsManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._mgr = settings_manager
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        intro = QLabel(
            "Configure optional Tier 2 AI reasoning. Simple commands (volume, media, app launches) "
            "always resolve locally in 0ms without internet. When Tier 1 doesn't match, "
            "NOVA cascades through your configured AI models."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: grey; font-size: 11px;")
        layout.addWidget(intro)

        # ── General Strategy ──
        strat_group = QGroupBox("AI Reasoning Strategy")
        strat_form = QFormLayout(strat_group)

        self._enabled_cb = QCheckBox("Enable Tier 2 AI reasoning for complex requests")
        self._enabled_cb.setChecked(self._settings.llm.enabled)
        strat_form.addRow(self._enabled_cb)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem("Cascade (Agnes -> Gemini -> Ollama)", "cascade")
        self._provider_combo.addItem("Agnes 3.0 Flash (Unlimited tokens)", "agnes")
        self._provider_combo.addItem("Gemini 3.8 Live (Realtime Voice)", "gemini_live")
        self._provider_combo.addItem("Gemini 2.0 Flash (Turn-based)", "gemini")
        self._provider_combo.addItem("Ollama (Local Offline)", "ollama")
        self._provider_combo.addItem("Offline Only (No cloud)", "offline")

        # Select current provider
        current_idx = self._provider_combo.findData(self._settings.llm.provider)
        if current_idx >= 0:
            self._provider_combo.setCurrentIndex(current_idx)
        strat_form.addRow("Primary Engine:", self._provider_combo)

        self._fallback_cb = QCheckBox("Enable automatic cascade fallback if primary provider fails")
        self._fallback_cb.setChecked(self._settings.llm.cascade_fallback)
        strat_form.addRow(self._fallback_cb)

        layout.addWidget(strat_group)

        # ── API Keys ──
        keys_group = QGroupBox("API Keys & Credentials")
        keys_form = QFormLayout(keys_group)

        # Agnes Key
        agnes_key_row = QHBoxLayout()
        self._agnes_key_input = QLineEdit()
        self._agnes_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._agnes_key_input.setPlaceholderText("Stored securely in OS keychain")
        existing_agnes = get_agnes_api_key()
        if existing_agnes:
            self._agnes_key_input.setText(existing_agnes)

        self._toggle_agnes_btn = QPushButton("👁")
        self._toggle_agnes_btn.setFixedWidth(30)
        self._toggle_agnes_btn.clicked.connect(self._toggle_agnes_visibility)
        agnes_key_row.addWidget(self._agnes_key_input)
        agnes_key_row.addWidget(self._toggle_agnes_btn)

        agnes_status = "✓ Configured" if existing_agnes else "✗ Not set"
        agnes_label = QLabel(f"Agnes API Key: ({agnes_status})")
        keys_form.addRow(agnes_label, agnes_key_row)

        # Gemini Key
        gemini_key_row = QHBoxLayout()
        self._gemini_key_input = QLineEdit()
        self._gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key_input.setPlaceholderText("Stored securely in OS keychain")
        existing_gemini = get_gemini_api_key()
        if existing_gemini:
            self._gemini_key_input.setText(existing_gemini)

        self._toggle_gemini_btn = QPushButton("👁")
        self._toggle_gemini_btn.setFixedWidth(30)
        self._toggle_gemini_btn.clicked.connect(self._toggle_gemini_visibility)
        gemini_key_row.addWidget(self._gemini_key_input)
        gemini_key_row.addWidget(self._toggle_gemini_btn)

        gemini_status = "✓ Configured" if existing_gemini else "✗ Not set"
        gemini_label = QLabel(f"Gemini API Key: ({gemini_status})")
        keys_form.addRow(gemini_label, gemini_key_row)

        layout.addWidget(keys_group)

        # ── Models & Endpoints ──
        models_group = QGroupBox("Models & Endpoints")
        models_form = QFormLayout(models_group)

        self._agnes_model_input = QLineEdit(self._settings.llm.agnes_model)
        models_form.addRow("Agnes Model:", self._agnes_model_input)

        self._gemini_live_input = QLineEdit(self._settings.llm.live_model)
        models_form.addRow("Gemini Live Model:", self._gemini_live_input)

        self._gemini_turn_input = QLineEdit(self._settings.llm.gemini_model)
        models_form.addRow("Gemini Turn Model:", self._gemini_turn_input)

        self._ollama_url_input = QLineEdit(self._settings.llm.ollama_base_url)
        models_form.addRow("Ollama Base URL:", self._ollama_url_input)

        layout.addWidget(models_group)
        layout.addStretch()

    def _toggle_agnes_visibility(self) -> None:
        if self._agnes_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._agnes_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._agnes_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _toggle_gemini_visibility(self) -> None:
        if self._gemini_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._gemini_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def apply_to(self, settings: NovaSettings) -> None:
        """Apply page values to configuration."""
        settings.llm.enabled = self._enabled_cb.isChecked()
        settings.llm.provider = str(self._provider_combo.currentData())
        settings.llm.cascade_fallback = self._fallback_cb.isChecked()
        settings.llm.agnes_model = self._agnes_model_input.text().strip() or "agnes-3.0-flash"
        settings.llm.live_model = self._gemini_live_input.text().strip() or "gemini-3.8-live"
        settings.llm.gemini_model = self._gemini_turn_input.text().strip() or "gemini-2.0-flash"
        settings.llm.ollama_base_url = (
            self._ollama_url_input.text().strip() or "http://localhost:11434"
        )

        # Save keys if changed
        agnes_key = self._agnes_key_input.text().strip()
        if agnes_key:
            set_agnes_api_key(agnes_key)

        gemini_key = self._gemini_key_input.text().strip()
        if gemini_key:
            set_gemini_api_key(gemini_key)
