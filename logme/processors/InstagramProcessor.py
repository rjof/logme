import logging
import re
import os
import json
import pandas as pd
from logme.utils import Utils as u
from logme import config, now_ts, SUCCESS
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

    def process_txt_file(self, txt_file_path: str, post_hash: str):
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
        
        # Extract emojis as tags (using a common emoji unicode range)
        # This regex matches common emojis in the BMP and beyond
        emojis = re.findall(r'[\U0001f300-\U0001f9ff\U0001f600-\U0001f64f]', content)
        if emojis:
            self.logger.info(f"Found {len(emojis)} emojis to treat as tags")
            tags.extend(emojis)
        
        # Extract mentions: ascii words prefixed by @. Accounts can have dots.
        mentions = re.findall(r'@([\w.]+)', content)
        # Remove trailing dot if it's likely end of sentence
        mentions = [m.rstrip('.') for m in mentions]
        
        # created_at = execution_timestamp (using now_ts from logme)
        created_at = now_ts
        
        data = {
            'id_post': post_hash,
            'created_at': created_at,
            'description': content,
            'tags': json.dumps(tags),
            'mentions': json.dumps(mentions)
        }
        
        table_name = self.conf_raw_to_l1.get('table_name', 'instagram_l1')
        
        if not self.ProcessingUtils._table_exists(table_name=table_name):
            self.logger.info(f'Creating l1 table {table_name}')
            from importlib import resources as impresources
            import logme.storage
            ddl_file = impresources.files(logme.storage) / f'instagram_l1.sql'
            query = open(ddl_file, "rt").read().format(name=self.src)
            if self.ProcessingUtils._create_table(query) != SUCCESS:
                self.logger.error(f"Error creating {table_name}")
                return

        df = pd.DataFrame([data])
        
        if self._db_handler:
            self.logger.info(f"Saving processed data to table: {table_name}")
            self._db_handler.df_to_db(df=df, table_name=table_name)
            
            # Process Tags L2
            self.process_tags_l2(post_hash, created_at, tags)
            
            # Process Mentions L2
            self.process_mentions_l2(post_hash, created_at, mentions)
        else:
            self.logger.error("Database handler not available. Cannot save processed data.")

    def process_tags_l2(self, id_post: str, created_at: int, tags: list):
        try:
            conf = u.get_source_conf(self.src, f'{self.src}_l1_to_tags_l2')
            table_name = conf.get("table_name", "instagram_tags_l2")
        except Exception:
            table_name = "instagram_tags_l2"

        if not tags:
            return

        if not self.ProcessingUtils._table_exists(table_name=table_name):
            self.logger.info(f'Creating tags l2 table {table_name}')
            from importlib import resources as impresources
            import logme.storage
            ddl_file = impresources.files(logme.storage) / f'instagram_tags_l2.sql'
            query = open(ddl_file, "rt").read().format(name=self.src)
            if self.ProcessingUtils._create_table(query) != SUCCESS:
                self.logger.error(f"Error creating {table_name}")
                return

        rows = []
        for tag in tags:
            rows.append({
                'id_post': id_post,
                'created_at': created_at,
                'tag': tag
            })
        
        df = pd.DataFrame(rows)
        if self._db_handler:
            self.logger.info(f"Saving tags to {table_name}")
            self._db_handler.df_to_db(df=df, table_name=table_name)

    def process_mentions_l2(self, id_post: str, created_at: int, mentions: list):
        try:
            conf = u.get_source_conf(self.src, f'{self.src}_l1_to_mentions_l2')
            table_name = conf.get("table_name", "instagram_mentions_l2")
        except Exception:
            table_name = "instagram_mentions_l2"

        if not mentions:
            return

        if not self.ProcessingUtils._table_exists(table_name=table_name):
            self.logger.info(f'Creating mentions l2 table {table_name}')
            from importlib import resources as impresources
            import logme.storage
            ddl_file = impresources.files(logme.storage) / f'instagram_mentions_l2.sql'
            query = open(ddl_file, "rt").read().format(name=self.src)
            if self.ProcessingUtils._create_table(query) != SUCCESS:
                self.logger.error(f"Error creating {table_name}")
                return

        rows = []
        for mention in mentions:
            rows.append({
                'id_post': id_post,
                'created_at': created_at,
                'mention': mention
            })
        
        df = pd.DataFrame(rows)
        if self._db_handler:
            self.logger.info(f"Saving mentions to {table_name}")
            self._db_handler.df_to_db(df=df, table_name=table_name)
