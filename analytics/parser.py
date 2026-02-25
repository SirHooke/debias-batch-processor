# analytics/parser.py

import json
from pathlib import Path
import pandas as pd


def load_results(output_folder: str) -> pd.DataFrame:
    """
    Returns a dataframe with:
    file | language | record_literal | issue_literal | tag_count_per_record
    """

    records = []

    for file_path in Path(output_folder).glob("*-output.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_name = file_path.name

        for result in data.get("results", []):
            language = result.get("language")
            record_literal = result.get("literal")
            tags = result.get("tags", [])

            tag_count = len(tags)

            # Add row for distribution per record
            records.append({
                "file": file_name,
                "language": language,
                "record_literal": record_literal,
                "issue_literal": None,
                "tag_count_per_record": tag_count
            })

            # Add rows for issue distribution
            for tag in tags:
                records.append({
                    "file": file_name,
                    "language": language,
                    "record_literal": record_literal,
                    "issue_literal": tag.get("literal"),
                    "tag_count_per_record": tag_count
                })

    df = pd.DataFrame(records)
    return df