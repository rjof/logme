import json
import os
import shutil
from sqlalchemy import create_engine, text
from os import makedirs
import typer
from pathlib import Path
import pandas as pd
import logging
import time
from logme import config, SUCCESS, date_time, DB_READ_ERROR
from logme.utils.Utils import get_database_path, get_source_conf
from logme.storage.database import DatabaseHandler
from logme.connectors.GoogleDrive import GoogleDriveDownloader


class KoreaderStatistics:
    """
    Class to process sqlite files from Koreader
    """

    def __init__(self, src: str, dst: Path, conf: dict = None) -> None:
        self.src_name = src
        self.dst = dst
        self.conf = conf if conf else get_source_conf(src, src)
        self.logger = logging.getLogger(self.__class__.__name__)

        db_path = get_database_path(config.CONFIG_FILE_PATH)
        if not db_path.exists():
            # If database doesn't exist, we'll let DatabaseHandler init it later if needed,
            # but usually it should be there.
            pass
        self._db_handler = DatabaseHandler(db_path)

    def ingest(self):
        """Download files if needed and backup them."""
        downloaded_files = []
        if self.conf.get("connection") == "GoogleDrive":
            # Get the path from the landing_to_raw section
            section_name = f"{self.src_name}_landing_to_raw"
            landing_conf = get_source_conf(self.src_name, section_name)
            gdrive_src_path = landing_conf.get("google_drive_src_path")

            if not gdrive_src_path:
                self.logger.error(f"google_drive_src_path not found in [{section_name}]")
                return []

            downloader = GoogleDriveDownloader(self.src_name, self.dst)
            downloaded_files = downloader.download_latest(gdrive_src_path)
        else:
            # Handle local file system if needed, or assume files are already in landing
            src_file = self.conf.get("src_file")
            if src_file:
                files = [i.strip(" ") for i in src_file.split(",")]
                for f in files:
                    src_path = Path(f)
                    if src_path.exists():
                        dst_file = self.dst / src_path.name
                        if not self.dst.exists():
                            makedirs(self.dst)
                        shutil.copy(src_path, dst_file)
                        downloaded_files.append(dst_file)

        # Backup to external HDD
        external_hdd = self.conf.get("external_hdd")
        if external_hdd and downloaded_files:
            backup_path = Path(external_hdd) / self.src_name / date_time
            if not backup_path.exists():
                makedirs(backup_path)
            for f in downloaded_files:
                shutil.copy(f, backup_path / f.name)
            self.logger.info(f"Backup created at: {backup_path}")

        return downloaded_files

    def landing_to_raw(self, files: list[Path]):
        """Copy specified tables from landing files to raw database."""
        # Re-load specifically to get the landing_to_raw section
        from logme.utils.Utils import _get_config_parser

        parser = _get_config_parser(config.CONFIG_FILE_PATH)
        section_name = f"{self.src_name}_landing_to_raw"
        if not parser.has_section(section_name):
            self.logger.warning(f"No section [{section_name}] found in config.")
            return

        section_conf = dict(parser.items(section_name))
        db_to_process = section_conf.get("database_to_process", "").strip()

        # Mapping of original names to target names
        table_mappings = []
        if (
            "table_original_book_name" in section_conf
            and "table_name_book" in section_conf
        ):
            table_mappings.append(
                (
                    section_conf["table_original_book_name"].strip(),
                    section_conf["table_name_book"].strip(),
                )
            )
        if (
            "table_original_page_stat_name" in section_conf
            and "table_name_page_stat" in section_conf
        ):
            table_mappings.append(
                (
                    section_conf["table_original_page_stat_name"].strip(),
                    section_conf["table_name_page_stat"].strip(),
                )
            )

        if not table_mappings:
            self.logger.warning(
                f"No table mappings (e.g. table_original_book_name) found in [{section_name}]."
            )
            return

        main_db_path = get_database_path(config.CONFIG_FILE_PATH)
        engine = create_engine(f"sqlite:///{main_db_path}")

        for f in files:
            # If database_to_process is specified, skip other files
            if db_to_process and f.name != db_to_process:
                continue

            if f.suffix not in [".sqlite3", ".sqlite", ".db"]:
                continue

            self.logger.info(f"Processing file: {f}")
            with engine.connect() as conn:
                # Attach the source database
                # Using a fresh connection and transaction
                conn.execute(text(f"ATTACH DATABASE '{f}' AS source_db"))

                for orig_table, target_table in table_mappings:
                    # Overwrite target table with data from source
                    try:
                        # Check if source table exists
                        check_q = text(
                            f"SELECT name FROM source_db.sqlite_master WHERE type='table' AND name='{orig_table}'"
                        )
                        res = conn.execute(check_q)
                        if not res.fetchone():
                            # Debug: List what's in source_db
                            all_tables_q = text(
                                "SELECT name FROM source_db.sqlite_master WHERE type='table'"
                            )
                            all_tables = [r[0] for r in conn.execute(all_tables_q).fetchall()]
                            self.logger.warning(
                                f"Table '{orig_table}' not found in source {f}. "
                                f"Found tables: {all_tables}"
                            )
                            continue

                        # Drop existing target table
                        conn.execute(text(f"DROP TABLE IF EXISTS {target_table}"))

                        # Create and copy data
                        conn.execute(
                            text(
                                f"CREATE TABLE {target_table} AS SELECT * FROM source_db.{orig_table}"
                            )
                        )
                        self.logger.info(
                            f"Refreshed table {target_table} from {orig_table} in {f}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error refreshing {target_table} from {orig_table}: {e}"
                        )

                conn.execute(text("DETACH DATABASE source_db"))

    def process(self):
        """Full workflow for koreaderStatistics."""
        files = self.ingest()
        if not files:
            self.logger.warning("No files to process.")
            return

        self.landing_to_raw(files)
        # Original process logic for reading activities (logme table)
        # self.reading_activities_to_logme(files)

    def reading_activities_to_logme(self, files: list[Path]):
        # ... (rest of the original process logic if still needed)
        pass
