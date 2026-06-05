import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import os
import shutil
from logme.ingestors.KoreaderStatistics import KoreaderStatistics
from logme import SUCCESS

class TestKoreaderStatistics(unittest.TestCase):
    def setUp(self):
        self.src = "koreaderStatistics"
        self.dst = Path("/tmp/logme_test/landing")
        self.conf = {
            "connection": "file_system",
            "src_file": "/tmp/logme_test/src/stat.sqlite3",
            "external_hdd": "/tmp/logme_test/backup",
            "google_drive_src_path": "test/path"
        }
        
        # Create dummy source file
        os.makedirs("/tmp/logme_test/src", exist_ok=True)
        with open("/tmp/logme_test/src/stat.sqlite3", "w") as f:
            f.write("dummy sqlite content")

    def tearDown(self):
        if os.path.exists("/tmp/logme_test"):
            shutil.rmtree("/tmp/logme_test")

    @patch("logme.ingestors.KoreaderStatistics.get_database_path")
    @patch("logme.ingestors.KoreaderStatistics.DatabaseHandler")
    def test_ingest_local(self, mock_db_handler, mock_get_db_path):
        mock_get_db_path.return_value = Path("/tmp/logme_test/main.db")
        
        ks = KoreaderStatistics(self.src, self.dst, self.conf)
        files = ks.ingest()
        
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].exists())
        self.assertTrue(Path("/tmp/logme_test/backup/koreaderStatistics").exists())

    @patch("logme.ingestors.KoreaderStatistics.GoogleDriveDownloader")
    @patch("logme.ingestors.KoreaderStatistics.get_database_path")
    def test_ingest_gdrive(self, mock_get_db_path, mock_gdrive):
        mock_get_db_path.return_value = Path("/tmp/logme_test/main.db")
        self.conf["connection"] = "GoogleDrive"
        
        mock_instance = mock_gdrive.return_value
        mock_instance.download_latest.return_value = [self.dst / "gstat.sqlite3"]
        
        # Create dummy landing file
        os.makedirs(self.dst, exist_ok=True)
        with open(self.dst / "gstat.sqlite3", "w") as f:
            f.write("dummy gdrive content")
            
        ks = KoreaderStatistics(self.src, self.dst, self.conf)
        files = ks.ingest()
        
        mock_instance.download_latest.assert_called_with("test/path")
        self.assertEqual(len(files), 1)
        self.assertTrue(Path("/tmp/logme_test/backup/koreaderStatistics").exists())

    @patch("logme.ingestors.KoreaderStatistics.create_engine")
    @patch("logme.utils.Utils._get_config_parser")
    @patch("logme.ingestors.KoreaderStatistics.get_database_path")
    def test_landing_to_raw(self, mock_get_db_path, mock_get_parser, mock_create_engine):
        mock_get_db_path.return_value = Path("/tmp/logme_test/main.db")
        
        # Mock config parser for tables
        mock_parser = MagicMock()
        mock_parser.has_section.return_value = True
        mock_parser.items.return_value = [("book", ""), ("page_stat", "")]
        mock_get_parser.return_value = mock_parser
        
        # Mock sqlalchemy engine and connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock fetchone to simulate table exists in source
        mock_conn.execute.return_value.fetchone.return_value = ("book",)
        
        ks = KoreaderStatistics(self.src, self.dst, self.conf)
        test_file = Path("/tmp/logme_test/landing/stat.sqlite3")
        ks.landing_to_raw([test_file])
        
        # Verify ATTACH and CREATE TABLE calls
        calls = [str(c[0][0]) for c in mock_conn.execute.call_args_list]
        self.assertIn(f"ATTACH DATABASE '{test_file}' AS source_db", calls)
        self.assertIn("CREATE TABLE IF NOT EXISTS book AS SELECT * FROM source_db.book WHERE 1=0", calls)
        self.assertIn("INSERT INTO book SELECT * FROM source_db.book", calls)

if __name__ == "__main__":
    unittest.main()
