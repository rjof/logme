import logging
import os
import json
import pandas as pd
import numpy as np
import time
from pathlib import Path
from logme.utils import Utils as u
from logme import config, now, SUCCESS
from logme.utils.Utils import get_database_path
from logme.storage.database import DatabaseHandler

class ATimeLoggerProcessor:
    """
    Class to process aTimeLogger json files and save them to the database.
    """

    def __init__(self, src_name: str = "aTimeLogger") -> None:
        from logme.utils import ProcessingUtils
        self.ProcessingUtils = ProcessingUtils
        self.src = src_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Starting {self.__class__.__name__}')
        
        if config.CONFIG_FILE_PATH.exists():
            db_path = get_database_path(config.CONFIG_FILE_PATH)
        else:
            db_path = None
            
        if db_path and db_path.exists():
            self._db_handler = DatabaseHandler(db_path)
        else:
            self._db_handler = None

    def process(self, landing_dir: Path) -> int:
        """
        Processes downloaded json files:
        1. Ingests raw intervals to aTimeLogger_raw (as strings).
        2. Syncs to aTimeLogger_l1.
        """
        self.logger.info(f"Processing data from {landing_dir}")
        
        # Check files activities.json & intervals.json exists
        input_files = {
            "activities_file": landing_dir / "activities.json",
            "intervals_file": landing_dir / "intervals.json",
        }

        # Load them
        loaded_data = {}
        for key, file_path in input_files.items():
            try:
                with open(file_path, "r") as f:
                    loaded_data[key] = json.load(f)
            except FileNotFoundError:
                msg = f"The file {file_path} was not found."
                self.logger.error(msg)
                raise Exception(msg)

        # 1. Ingest Raw Intervals
        self.ingest_raw_intervals(loaded_data["intervals_file"], input_files["intervals_file"].name)

        # 2. Sync to L1 (using existing logic but from JSON data)
        # Clean activities
        activities = pd.json_normalize(loaded_data["activities_file"]["types"])
        activities = activities[["guid", "name", "group", "parent"]]

        # Normalize intervals for L1
        intervals = pd.json_normalize(loaded_data["intervals_file"]["intervals"])
        intervals = intervals[["guid", "from", "to", "comment", "type.guid"]]
        intervals["duration_sec"] = intervals["to"] - intervals["from"]

        # Merge with activities to get human readable names
        activities_intervals = pd.merge(
            intervals, activities, right_on="guid", left_on="type.guid"
        )[["name", "comment", "duration_sec", "from", "to", "group", "parent"]]
        
        activities_intervals_select = pd.merge(
            activities_intervals, activities, left_on="parent", right_on="guid"
        )[["name_y", "name_x", "comment", "duration_sec", "from", "to"]]
        
        activities_intervals_select.rename(
            columns={
                "name_y": "in_group",
                "name_x": "activity",
                "from": "ts_from",
                "to": "ts_to",
            },
            inplace=True,
        )

        # Add a hash as index
        activities_intervals_select = self.ProcessingUtils._add_hash(activities_intervals_select)
        activities_intervals_select["hash"] = activities_intervals_select["hash"].astype(str)
        
        activities_intervals_select = activities_intervals_select[
            [
                "hash",
                "in_group",
                "activity",
                "comment",
                "duration_sec",
                "ts_from",
                "ts_to",
            ]
        ]
        
        # Add metadata for L1
        ts_added = int(time.mktime(now.timetuple()))
        activities_intervals_select = activities_intervals_select.copy()
        activities_intervals_select["src"] = self.src
        activities_intervals_select["ts_added"] = ts_added
        activities_intervals_select['comment'] = activities_intervals_select['comment'].astype(str)

        self.logger.info(f"Syncing to {self.src}_l1")
        self.raw_to_l1(activities_intervals_select)
        
        return SUCCESS

    def ingest_raw_intervals(self, intervals_json: dict, src_file: str):
        """
        Ingests all fields from intervals.json into aTimeLogger_raw as strings.
        """
        table_name = f"{self.src}_raw"
        df = pd.json_normalize(intervals_json["intervals"])
        df = df.astype(str).replace("nan", np.nan)
        df = self.ProcessingUtils._add_hash(df)
        
        from logme import now_ts
        df.insert(loc=0, column="ingest_timestamp", value=now_ts)
        df.insert(loc=0, column="src_file", value=src_file)

        if not self.ProcessingUtils._table_exists(table_name):
            self.logger.info(f"Creating raw table {table_name}")
            # We let df_to_db create it with the schema from the DataFrame
            self._db_handler.df_to_db(df=df, table_name=table_name)
        else:
            cols_in_db = self._db_handler.fields_in_table(table_name)
            df_cols = sorted(set(df.columns))
            if set(df.columns) != set(cols_in_db):
                new_columns = [key for key in df_cols if key not in cols_in_db]
                for new_col in new_columns:
                    self._db_handler.alter_table(table_name=table_name, new_col=new_col)
                cols_in_db = self._db_handler.fields_in_table(table_name)
            
            # Use row_to_raw_instagram (which is actually generic enough for raw rows) 
            # or a similar method for INSERT OR IGNORE
            for i in range(len(df)):
                row = df.iloc[[i]]
                placeholders = ", ".join(["?" for _ in cols_in_db])
                quoted_columns = ", ".join([f'"{col}"' for col in cols_in_db])
                values = [row[col].iloc[0] if col in df_cols else np.nan for col in cols_in_db]
                self._db_handler.row_to_raw_instagram(
                    table_name=table_name,
                    placeholders=placeholders,
                    quoted_columns=quoted_columns,
                    values=values,
                )


    def raw_to_l1(self, df: pd.DataFrame) -> int:
        """
        Saves the processed data to the l1 table, handling deduplication.
        """
        table_name = f"{self.src}_l1"
        
        if not self.ProcessingUtils._table_exists(table_name):
            self.logger.info(f'Creating l1 table {table_name}')
            from importlib import resources as impresources
            import logme.storage
            ddl_file = impresources.files(logme.storage) / f'ATimeLogger_l1.sql'
            
            try:
                query = open(ddl_file, "rt").read().format(name=self.src)
                if self.ProcessingUtils._create_table(query) != SUCCESS:
                    self.logger.error(f"Error creating {table_name}")
                    return 1
            except Exception as e:
                self.logger.error(f"Failed to create l1 table: {e}")
                return 1

        # Deduplication for l1
        try:
            existing_l1 = self._db_handler.load_table(table_name)
            if not existing_l1.empty:
                existing_hashes = existing_l1["hash"].astype(str).tolist()
                to_save = df[~df["hash"].isin(existing_hashes)]
            else:
                to_save = df
        except Exception as e:
            self.logger.warning(f"Could not load existing data from {table_name}: {e}")
            to_save = df

        if to_save.empty:
            self.logger.info(f"No new data to sync to {table_name}")
            return SUCCESS

        self.logger.info(f"Saving {len(to_save)} rows to {table_name}")
        return self._db_handler.df_to_db(df=to_save, table_name=table_name)

