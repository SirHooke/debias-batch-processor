import sys
import time
import json
import logging
import requests
import functools
import configparser
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# --- Init logging ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    filename="debias.log",
    encoding="utf-8",
    filemode="w+",
    level=logging.DEBUG,
    format="%(asctime)s - %(module)s - %(levelname)s: %(message)s",
)
print = functools.partial(print, flush=True)
BASE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

# --- Load config ---
logger.info("Parsing settings...")
config = configparser.ConfigParser()
config.read(BASE_DIR / "config.ini")

settings = config["settings"]
INPUT_FOLDER = Path(settings["INPUT_FOLDER"])
OUTPUT_FOLDER = Path(settings["OUTPUT_FOLDER"])
MAX_RETRIES = int(settings["MAX_RETRIES"])
USE_NER = config.getboolean("settings", "USE_NER")
USE_LLM = config.getboolean("settings", "USE_LLM")
SUPPORTED_LANGUAGES = {"nl", "en", "de", "it", "fr"}

API_URL = " https://debias-api.ails.ece.ntua.gr/simple"  # Replace with your API URL


def call_api(values: list, language: str) -> requests.Response:
    logger.info("Calling De-bias API.")
    payload = {
        "language": language,
        "useNER": USE_NER,
        "useLLM": USE_LLM,
        "values": values,
    }
    response = requests.post(API_URL, json=payload)
    response.raise_for_status()
    return response


def generate_pdf_report(file_path: Path, response_text: str) -> None:
    logger.info(f"Generating PDF for {file_path.name}")
    results = json.loads(response_text).get("results", [])

    # Filter to only entries with non-empty tags
    flagged = [r for r in results if r.get("tags")]
    if not flagged:
        print(f"[{file_path.name}] No flagged entries, skipping PDF report.")
        return

    pdf_path = OUTPUT_FOLDER / file_path.with_suffix(".pdf").name
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 8
    styles["Normal"].leading = 11
    story = []

    story.append(Paragraph(f"De-bias Report: {file_path.name}", styles["Title"]))
    story.append(Spacer(1, 6 * mm))

    # Table header
    col_widths = [25 * mm, 60 * mm, 177 * mm]
    table_data = [
        [
            Paragraph("<b>Record #</b>", styles["Normal"]),
            Paragraph("<b>Literal</b>", styles["Normal"]),
            Paragraph("<b>Tag details</b>", styles["Normal"]),
        ]
    ]

    for result in flagged:
        raw_literal = result.get("literal", "")
        # Split on first comma to get record number vs. the rest
        parts = raw_literal.split(",", 1)
        record_num = parts[0].strip()
        literal_text = parts[1].strip() if len(parts) > 1 else ""

        for i, tag in enumerate(result["tags"]):
            tag_text = (
                f"<b>Literal:</b> {tag.get('literal', '')}<br/>"
                f"<b>Issue:</b> {tag.get('issue', '')}<br/>"
                f"<b>Source:</b> {tag.get('source', '')}"
            )
            table_data.append(
                [
                    Paragraph(record_num if i == 0 else "", styles["Normal"]),
                    Paragraph(literal_text if i == 0 else "", styles["Normal"]),
                    Paragraph(tag_text, styles["Normal"]),
                ]
            )

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a4a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f0f0f8")],
                ),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(table)
    doc.build(story)
    logger.info(f"[{file_path.name}] PDF report written to {pdf_path}")
    print(f"[{file_path.name}] PDF report written to {pdf_path}")


def process_file(file_path: Path, language: str) -> None:
    logger.info(f"Processing started for {file_path.name}")
    output_path = OUTPUT_FOLDER / (file_path.stem + '-output.json')

    values = [
        line
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{language}/{file_path.name}] Attempt {attempt}/{MAX_RETRIES}...")
            response = call_api(values, language)

            output_path.write_text(response.text, encoding="utf-8")
            generate_pdf_report(file_path, response.text)
            print(
                f"[{language}/{file_path.name}] Success. Output written to {output_path}"
            )
            logger.info(
                f"[{language}/{file_path.name}] Success. Output written to {output_path}"
            )
            return

        except requests.RequestException as e:
            logger.warning(f"Error calling API for {file_path.name}: {e}")
            print(f"[{language}/{file_path.name}] Attempt {attempt} failed")
            if attempt < MAX_RETRIES:
                wait = 2**attempt
                print(f"[{language}/{file_path.name}] Retrying in {wait}s...")
                time.sleep(wait)
    logger.error(
        f"Calling API for {file_path.name} failed after all {MAX_RETRIES} attempts."
    )
    print(f"[{language}/{file_path.name}] All {MAX_RETRIES} attempts failed. Skipping.")


def main():
    logger.info("Starting processing...")
    print("Starting processing...")
    if not INPUT_FOLDER.exists():
        raise FileNotFoundError(f"Input folder not found: {INPUT_FOLDER}")
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    for lang_folder in INPUT_FOLDER.iterdir():
        if not lang_folder.is_dir() or lang_folder.name not in SUPPORTED_LANGUAGES:
            continue

        files = [f for f in lang_folder.iterdir() if f.is_file()]
        if not files:
            print(f"[{lang_folder.name}] Empty folder, skipping.")
            continue

        for file_path in files:
            process_file(file_path, lang_folder.name)
    print("DONE. Processing finished.")
    logger.info("DONE. Processing finished.")


if __name__ == "__main__":
    main()
