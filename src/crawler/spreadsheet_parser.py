"""Spreadsheet and tabular data parser supporting multi-sheet XLSX and CSV."""

import logging
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from src.state.schemas import ExtractedTable

logger = logging.getLogger(__name__)

MAX_SPREADSHEET_BYTES = 50 * 1024 * 1024  # 50MB limit


class SpreadsheetParser:
    """Extracts, filters, and formats tabular data from Excel and CSV files."""

    def parse_file(
        self,
        file_path: str | Path,
        sheet_name: str | None = None,
        max_rows_per_table: int = 50,
        columns: list[str] | None = None,
    ) -> list[ExtractedTable]:
        """Parse an XLSX or CSV file and return structured ExtractedTable objects."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Spreadsheet file not found: {path}")

        if path.stat().st_size > MAX_SPREADSHEET_BYTES:
            raise ValueError(f"File size exceeds 50MB safety limit: {path.stat().st_size} bytes")

        if path.suffix.lower() == ".xlsm":
            raise ValueError("Macro-enabled Excel workbooks (.xlsm) are prohibited for security.")

        if path.suffix.lower() in [".xlsx", ".xls"]:
            return self._parse_excel(path, sheet_name, max_rows_per_table, columns)
        elif path.suffix.lower() == ".csv":
            return [self._parse_csv(path, max_rows_per_table, columns)]
        else:
            raise ValueError(f"Unsupported spreadsheet format: {path.suffix}")

    def _parse_excel(
        self,
        path: Path,
        target_sheet: str | None,
        max_rows: int,
        columns: list[str] | None,
    ) -> list[ExtractedTable]:
        """Parse all or selected sheets from an Excel workbook."""
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        wb.close()

        sheets_to_process = (
            [target_sheet] if target_sheet and target_sheet in sheet_names else sheet_names
        )
        extracted_tables: list[ExtractedTable] = []

        for s_name in sheets_to_process:
            try:
                df = pd.read_excel(path, sheet_name=s_name)
                if df.empty:
                    continue

                if columns:
                    matched_cols = [c for c in columns if c in df.columns]
                    if matched_cols:
                        df = df[matched_cols]

                table = self._dataframe_to_extracted_table(
                    df, title=f"{path.stem} - Sheet: {s_name}", max_rows=max_rows
                )
                extracted_tables.append(table)
            except Exception as e:
                logger.warning("Error reading sheet '%s' from %s: %s", s_name, path.name, str(e))

        return extracted_tables

    def _parse_csv(
        self,
        path: Path,
        max_rows: int,
        columns: list[str] | None,
    ) -> ExtractedTable:
        """Parse a standalone CSV file into an ExtractedTable."""
        df = pd.read_csv(path)
        if columns:
            matched_cols = [c for c in columns if c in df.columns]
            if matched_cols:
                df = df[matched_cols]

        return self._dataframe_to_extracted_table(df, title=f"{path.stem} (CSV)", max_rows=max_rows)

    def _dataframe_to_extracted_table(
        self,
        df: pd.DataFrame,
        title: str,
        max_rows: int = 50,
    ) -> ExtractedTable:
        """Convert a pandas DataFrame into our Pydantic ExtractedTable schema."""
        trimmed_df = df.head(max_rows)
        headers = [str(col) for col in trimmed_df.columns]
        rows: list[list[Any]] = trimmed_df.values.tolist()

        # Generate standard markdown table string with graceful fallback if tabulate is absent
        try:
            md_table = trimmed_df.to_markdown(index=False) or ""
        except ImportError:
            header_line = "| " + " | ".join(headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            row_lines = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
            md_table = "\n".join([header_line, sep_line, *row_lines])

        return ExtractedTable(
            id=f"table_{abs(hash(title))}",
            title=title,
            headers=headers,
            rows=rows,
            markdown_representation=md_table,
        )
