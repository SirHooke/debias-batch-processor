# De-bias Batch Processor

A Python tool for batch processing CSV files through the De-bias API. It annotates text values for potentially biased language, writes the API responses as JSON, and generates PDF reports highlighting flagged entries.
---
## Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Input Folder Structure](#input-folder-structure)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Command line](#command-line)
  - [GUI](#gui)
- [Standalone Executable (Windows)](#standalone-executable-windows)
- [Output](#output)
- [Requirements](#requirements)
- [Notes](#notes)
---

## Overview

The processor walks a structured input directory, sends each file's contents to the De-bias API, and writes results to an output directory. For any file containing flagged entries, a PDF report is generated alongside the JSON output. Processing can be launched either from the command line or via a browser-based GUI.

---

## Project Structure

```
./
├── input/               # Input files, organised by language (see below)
│   ├── nl/
│   ├── en/
│   ├── de/
│   ├── fr/
│   └── it/
├── output/              # JSON responses and PDF reports are written here
├── config.ini           # Runtime configuration
├── call-debias.py       # Batch processing script
└── gui.py               # Optional GUI launcher
```

---

## Input Folder Structure

Input files **must** be placed in a language subfolder directly under the input directory. The name of the subfolder determines the `language` parameter passed to the API. The supported languages are:

| Folder | Language    |
|--------|-------------|
| `nl`   | Dutch       |
| `en`   | English     |
| `de`   | German      |
| `fr`   | French      |
| `it`   | Italian     |

Each file should be a `.csv` where **every line is treated as a single value** sent to the API. No CSV parsing is performed — each raw line becomes one entry in the request payload. Empty lines are ignored.

Example layout:
```
input/
├── en/
│   ├── batch_001.csv
│   └── batch_002.csv
└── de/
    └── batch_003.csv
```

Empty language folders are silently skipped.

---

## Configuration

Settings are stored in `config.ini` at the project root:

```ini
#
#   Default config
#
[settings]
INPUT_FOLDER=./input
OUTPUT_FOLDER=./output
USE_NER=true
USE_LLM=false
MAX_RETRIES=5
```

| Setting         | Description                                                  |
|-----------------|--------------------------------------------------------------|
| `INPUT_FOLDER`  | Path to the root input directory                             |
| `OUTPUT_FOLDER` | Path to the output directory                                 |
| `USE_NER`       | Enable Named Entity Recognition in the API call              |
| `USE_LLM`       | Enable LLM-based analysis in the API call                    |
| `MAX_RETRIES`   | Number of retry attempts per file on API failure (with exponential backoff) |

The config file can be edited manually or via the GUI (see below).

---

## Usage

### Command line

```bash
python call-debias.py
```

The script will:

1. Read settings from `config.ini`
2. Iterate over all language subfolders in the input directory
3. For each `.csv` file, send its lines to the De-bias API
4. Write the raw JSON response to the output directory
5. If any entries in the response contain tags, generate a PDF report alongside the JSON

Output files share the same base name as their input file:
```
input/en/batch_001.csv  →  output/batch_001.json
                        →  output/batch_001.pdf   (only if flagged entries exist)
```

### GUI

```bash
python gui.py
```

This launches a local web server and opens a browser tab with a graphical interface. The GUI allows you to:

- View and edit all settings from `config.ini`
- Select input and output folders using a native folder picker, or open them directly in your file explorer
- Toggle NER and LLM options
- Save the current settings back to `config.ini`
- Start the processor and monitor its output in a live log view
- See a status indicator (spinner while running, green on success, red on error)

Changes made in the GUI are automatically saved to `config.ini` when you press **Start** or **Save config**.

---

## Output

### JSON
The raw API response for each file, written to the output folder.

### PDF Report
Generated for any file where at least one result contains a non-empty `tags` array. The report is a landscape A4 table with the following columns:

| Column       | Contents                                             |
|--------------|------------------------------------------------------|
| Record #     | The record identifier (first field of the CSV line)  |
| Literal      | The text that was analysed (remainder of the CSV line)|
| Tag details  | The issue description, affected literal, and source  |

If a single record has multiple tags, each tag gets its own row.

---

---

## Standalone Executable (Windows)

A pre-built `call-debias.exe` is available as a download in the [Releases](../../releases) section. It bundles the GUI, the processor, and all dependencies — no Python installation required.

To run it, extract the zip and launch `call-debias.exe`. The `input/`, `output/`, and `config.ini` files should be placed in the same directory as the executable.

### Building the executable yourself

If you prefer to build from source, install PyInstaller and run:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name call-debias gui.py
```

The resulting executable will be placed in the `dist/` folder. The `--noconsole` flag suppresses the background terminal window since the GUI has its own log output. If you want to keep the terminal visible (useful for debugging), omit that flag.

> **Note:** PyInstaller bundles only the packages installed in your current Python environment. Make sure all dependencies are installed before building.

---

## Requirements

Install dependencies with:

```bash
pip install requests reportlab nicegui
```

`tkinter` is also required for the folder picker in the GUI. It is included with most Python distributions; on minimal Linux installs it can be added with:

```bash
sudo apt install python3-tk
```

---

## Notes

- Files that exhaust all retry attempts are skipped without interrupting the rest of the run.
- The output directory is created automatically if it does not exist.
- Any folder inside the input directory that is not one of the five supported language codes is ignored.