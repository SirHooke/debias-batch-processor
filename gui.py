import configparser
import os
import subprocess
import sys
from pathlib import Path
import io
import contextlib
import traceback
import call_debias

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QSpinBox, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget, QCheckBox, QSizePolicy
)
from analytics.dashboard_widget import AnalyticsDashboard

CONFIG_PATH = "config.ini"


# --- Config helpers ---

def load_config() -> dict:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    s = config["settings"]
    return {
        "input_folder":  s.get("INPUT_FOLDER", "./input"),
        "output_folder": s.get("OUTPUT_FOLDER", "./output"),
        "use_ner":       s.getboolean("USE_NER", True),
        "use_llm":       s.getboolean("USE_LLM", False),
        "max_retries":   s.getint("MAX_RETRIES", 5),
    }


def save_config(settings: dict) -> None:
    config = configparser.ConfigParser()
    config["settings"] = {
        "INPUT_FOLDER":  settings["input_folder"],
        "OUTPUT_FOLDER": settings["output_folder"],
        "USE_NER":       str(settings["use_ner"]).lower(),
        "USE_LLM":       str(settings["use_llm"]).lower(),
        "MAX_RETRIES":   str(settings["max_retries"]),
    }
    with open(CONFIG_PATH, "w") as f:
        f.write("#\n#   Default config\n#\n")
        config.write(f)


def open_folder(path: str) -> None:
    resolved = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(resolved)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", resolved])
    else:
        subprocess.Popen(["xdg-open", resolved])


# --- Worker thread ---

class ProcessorThread(QThread):
    line_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def run(self):
        success = True

        # Custom stream object to forward writes
        class StreamEmitter(io.StringIO):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal

            def write(self, msg):
                if msg.strip():
                    self.signal.emit(msg.rstrip())
                super().write(msg)

        stdout_stream = StreamEmitter(self.line_ready)
        stderr_stream = StreamEmitter(self.line_ready)

        try:
            with contextlib.redirect_stdout(stdout_stream), \
                 contextlib.redirect_stderr(stderr_stream):

                call_debias.main()

        except Exception:
            success = False
            err = traceback.format_exc()
            self.line_ready.emit(err)

        self.finished.emit(success)

# --- Main window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("De-bias Processor")
        self.setMinimumWidth(700)
        self.settings = load_config()
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_ui()

    def _build_ui(self):
    # --- batch tab ---
        batch = QWidget()
        layout = QVBoxLayout(batch)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(self._build_settings_group())
        layout.addWidget(self._build_run_group())
        self.tabs.addTab(batch, "Batch Processing")
    # --- analytics tab ---
        analytics_tab = AnalyticsDashboard("output")
        self.tabs.addTab(analytics_tab, "Analytics")

    # --- Settings group ---

    def _build_settings_group(self) -> QGroupBox:
        group = QGroupBox("Settings")
        vbox = QVBoxLayout(group)

        # Input folder
        self.input_field = QLineEdit(self.settings["input_folder"])
        vbox.addWidget(QLabel("Input folder"))
        vbox.addLayout(self._folder_row(self.input_field))

        # Output folder
        self.output_field = QLineEdit(self.settings["output_folder"])
        vbox.addWidget(QLabel("Output folder"))
        vbox.addLayout(self._folder_row(self.output_field))

        # Toggles
        toggle_row = QHBoxLayout()
        self.ner_checkbox = QCheckBox("Use NER")
        self.ner_checkbox.setChecked(self.settings["use_ner"])
        self.llm_checkbox = QCheckBox("Use LLM")
        self.llm_checkbox.setChecked(self.settings["use_llm"])
        toggle_row.addWidget(self.ner_checkbox)
        toggle_row.addWidget(self.llm_checkbox)
        toggle_row.addStretch()
        vbox.addLayout(toggle_row)

        # Max retries
        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("Max retries"))
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 20)
        self.retries_spin.setValue(self.settings["max_retries"])
        self.retries_spin.setFixedWidth(70)
        retry_row.addWidget(self.retries_spin)
        retry_row.addStretch()
        vbox.addLayout(retry_row)

        # Save button
        save_btn = QPushButton("Save config")
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._on_save)
        vbox.addWidget(save_btn)

        return group

    def _folder_row(self, field: QLineEdit) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(field)
        select_btn = QPushButton("Select…")
        select_btn.setFixedWidth(80)
        select_btn.clicked.connect(lambda: self._pick_folder(field))
        open_btn = QPushButton("Open")
        open_btn.setFixedWidth(60)
        open_btn.clicked.connect(lambda: open_folder(field.text()))
        row.addWidget(select_btn)
        row.addWidget(open_btn)
        return row

    def _pick_folder(self, field: QLineEdit) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select folder", field.text())
        if chosen:
            field.setText(chosen)

    def _on_save(self) -> None:
        save_config(self._current_settings())
        self.statusBar().showMessage("Config saved.", 3000)

    def _current_settings(self) -> dict:
        return {
            "input_folder":  self.input_field.text(),
            "output_folder": self.output_field.text(),
            "use_ner":       self.ner_checkbox.isChecked(),
            "use_llm":       self.llm_checkbox.isChecked(),
            "max_retries":   self.retries_spin.value(),
        }

    # --- Run group ---

    def _build_run_group(self) -> QGroupBox:
        group = QGroupBox("Run")
        vbox = QVBoxLayout(group)

        # Status row
        status_row = QHBoxLayout()
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: grey; font-size: 18px;")
        self.status_label = QLabel("Idle")
        status_row.addWidget(self.status_indicator)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        vbox.addLayout(status_row)

        # Log output
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFontFamily("Courier New")
        self.log_view.setFontPointSize(9)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_view.setMinimumHeight(250)
        vbox.addWidget(self.log_view)

        # Buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setFixedWidth(100)
        self.start_btn.clicked.connect(self._on_start)
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedWidth(80)
        exit_btn.setStyleSheet("color: red;")
        exit_btn.clicked.connect(self.close)
        btn_row.addWidget(self.start_btn)
        btn_row.addStretch()
        btn_row.addWidget(exit_btn)
        vbox.addLayout(btn_row)

        return group

    def _set_status(self, state: str) -> None:
        colours = {"idle": "grey", "running": "orange", "done": "green", "error": "red"}
        labels  = {"idle": "Idle", "running": "Running…", "done": "Done", "error": "Error"}
        self.status_indicator.setStyleSheet(
            f"color: {colours[state]}; font-size: 18px;"
        )
        self.status_label.setText(labels[state])

    def _on_start(self) -> None:
        self._on_save()
        self.log_view.clear()
        self._set_status("running")
        self.start_btn.setEnabled(False)

        self.thread = ProcessorThread()
        self.thread.line_ready.connect(self._append_log)
        self.thread.finished.connect(self._on_finished)
        self.thread.start()

    def _append_log(self, line: str) -> None:
        self.log_view.append(line)

    def _on_finished(self, success: bool) -> None:
        self._set_status("done" if success else "error")
        self.start_btn.setEnabled(True)


# --- Entry point ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())