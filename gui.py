import configparser
import subprocess
import sys
import threading
import os
from pathlib import Path
from nicegui import ui, app

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
    """Open a folder in the OS file explorer."""
    resolved = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(resolved)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", resolved])
    else:
        subprocess.Popen(["xdg-open", resolved])


def pick_folder(current: str, callback) -> None:
    """Open a native folder picker via tkinter (runs in a thread to avoid blocking)."""
    def _pick():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(initialdir=current or ".")
        root.destroy()
        if chosen:
            callback(chosen)
    threading.Thread(target=_pick, daemon=True).start()


# --- Build UI ---

settings = load_config()

ui.dark_mode().enable()

with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-6"):

    ui.label("De-bias Processor").classes("text-2xl font-bold")

    # --- Settings card ---
    with ui.card().classes("w-full"):
        ui.label("Settings").classes("text-lg font-semibold mb-2")

        # Input folder
        with ui.row().classes("items-center gap-2 w-full"):
            ui.label("Input folder").classes("w-28 shrink-0")
            input_folder_field = ui.input(value=settings["input_folder"]).classes("flex-1")
            ui.button("Select", icon="folder_open",
                      on_click=lambda: pick_folder(
                          input_folder_field.value,
                          lambda p: input_folder_field.set_value(p)
                      )).props("flat dense")
            ui.button("Open", icon="launch",
                      on_click=lambda: open_folder(input_folder_field.value)).props("flat dense")

        # Output folder
        with ui.row().classes("items-center gap-2 w-full"):
            ui.label("Output folder").classes("w-28 shrink-0")
            output_folder_field = ui.input(value=settings["output_folder"]).classes("flex-1")
            ui.button("Select", icon="folder_open",
                      on_click=lambda: pick_folder(
                          output_folder_field.value,
                          lambda p: output_folder_field.set_value(p)
                      )).props("flat dense")
            ui.button("Open", icon="launch",
                      on_click=lambda: open_folder(output_folder_field.value)).props("flat dense")

        ui.separator()

        # Toggles
        with ui.row().classes("gap-8 items-center"):
            use_ner_toggle = ui.switch("Use NER", value=settings["use_ner"])
            use_llm_toggle = ui.switch("Use LLM", value=settings["use_llm"])

        # Max retries
        with ui.row().classes("items-center gap-4"):
            ui.label("Max retries")
            max_retries_field = ui.number(value=settings["max_retries"], min=1, max=20, precision=0).classes("w-24")

        ui.separator()

        def on_save():
            save_config({
                "input_folder":  input_folder_field.value,
                "output_folder": output_folder_field.value,
                "use_ner":       use_ner_toggle.value,
                "use_llm":       use_llm_toggle.value,
                "max_retries":   int(max_retries_field.value),
            })
            ui.notify("Config saved.", type="positive")

        ui.button("Save config", icon="save", on_click=on_save).props("outline")

    # --- Run card ---
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Run").classes("text-lg font-semibold")

            # Status indicator
            with ui.row().classes("items-center gap-2"):
                status_label = ui.label("Idle").classes("text-sm text-gray-400")
                spinner = ui.spinner(size="sm").classes("hidden")
                status_dot = ui.icon("circle", size="sm").classes("text-gray-400")

        log_area = (
            ui.log()
            .classes("w-full h-64 font-mono text-xs")
        )

        def set_status(state: str) -> None:
            """state: idle | running | done | error"""
            if state == "idle":
                spinner.classes("hidden", remove="")
                status_dot.classes("text-gray-400", remove="text-green-500 text-red-500 hidden")
                status_label.set_text("Idle")
            elif state == "running":
                spinner.classes(remove="hidden")
                status_dot.classes("hidden", remove="")
                status_label.set_text("Running…")
            elif state == "done":
                spinner.classes("hidden", remove="")
                status_dot.classes("text-green-500", remove="text-gray-400 text-red-500 hidden")
                status_label.set_text("Done")
            elif state == "error":
                spinner.classes("hidden", remove="")
                status_dot.classes("text-red-500", remove="text-gray-400 text-green-500 hidden")
                status_label.set_text("Error")

        with ui.row().classes("gap-2"):
            start_button = ui.button("Start", icon="play_arrow")
            ui.button("Exit", icon="power_settings_new", color="negative",
                    on_click=lambda: (ui.navigate.to("about:blank"), app.shutdown())
                    ).props("outline")

        def run_processor() -> None:
            # Persist current settings before running
            on_save()

            log_area.clear()
            set_status("running")
            start_button.disable()

            def _run():
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-u", "call-debias.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    fatal = False
                    for line in process.stdout:
                        log_area.push(line.rstrip())
                        if "exception" in line.lower() or "error" in line.lower():
                            fatal = True
                    process.wait()
                    if process.returncode != 0 or fatal:
                        set_status("error")
                    else:
                        set_status("done")
                except Exception as e:
                    log_area.push(f"Failed to launch: {e}")
                    set_status("error")
                finally:
                    start_button.enable()

            threading.Thread(target=_run, daemon=True).start()

        start_button.on_click(run_processor)


ui.run(title="De-bias Processor", reload=False)