import logging
import re
import os
import json
import pandas as pd
from logme.utils import Utils as u
from logme import config, now_ts
from logme.utils.Utils import get_database_path
from logme.storage.database import DatabaseHandler

class InstagramProcessor:
    """
    Class to process Instagram data, specifically analyzing post text files.
    """

    def __init__(self) -> None:
        from logme.utils import ProcessingUtils
        self.ProcessingUtils = ProcessingUtils
        self.src = "instagram"
        try:
            self.conf_raw_to_l1 = u.get_source_conf(self.src, f'{self.src}_raw_to_l1')
        except Exception:
            # Fallback if config section is missing
            self.conf_raw_to_l1 = {"table_name": "instagram_l1"}
            
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Starting InstagramProcessor')
        
        if config.CONFIG_FILE_PATH.exists():
            db_path = get_database_path(config.CONFIG_FILE_PATH)
        else:
            db_path = None
            
        if db_path and db_path.exists():
            self._db_handler = DatabaseHandler(db_path)
        else:
            self._db_handler = None

    def process_txt_file(self, txt_file_path: str):
        """
        Analyzes a text file to extract description, tags, and mentions,
        and saves the data to the configured database table.
        """
        if not os.path.exists(txt_file_path):
            self.logger.warning(f"Text file not found: {txt_file_path}")
            return
            
        try:
            with open(txt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.logger.error(f"Error reading text file {txt_file_path}: {e}")
            return
            
        # Extract tags: ascii words prefixed with #
        tags = re.findall(r'#(\w+)', content)
        
        # Extract mentions: ascii words prefixed by @. Accounts can have dots.
        mentions = re.findall(r'@([\w.]+)', content)
        # Remove trailing dot if it's likely end of sentence
        mentions = [m.rstrip('.') for m in mentions]
        
        # created_at = execution_timestamp (using now_ts from logme)
        created_at = now_ts
        
        data = {
            'created_at': created_at,
            'description': content,
            'tags': json.dumps(tags),
            'mentions': json.dumps(mentions)
        }
        
        table_name = self.conf_raw_to_l1.get('table_name', 'instagram_l1')
        
        df = pd.DataFrame([data])
        # Add hash column similar to other tables
        df = self.ProcessingUtils._add_hash(df)
        
        if self._db_handler:
            self.logger.info(f"Saving processed data to table: {table_name}")
            self._db_handler.df_to_db(df=df, table_name=table_name)
        else:
            self.logger.error("Database handler not available. Cannot save processed data.")
