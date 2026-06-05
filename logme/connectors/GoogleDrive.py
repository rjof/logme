import io
from os import makedirs
from logme.storage.database import DatabaseHandler
from logme import DB_READ_ERROR, ID_ERROR, creds_dict, SCOPES, CONFIG_FILE_PATH, FILE_ERROR, SUCCESS, date_time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pathlib import Path
from typing import List
import logging
import json

logger = logging.getLogger(__name__)


class GoogleDriveDownloader:
    """Class to download log files from Google Drive."""

    def __init__(self, src: str, dst: Path, creds_dict: dict = None) -> None:
        self.src = src
        self.dst = Path(dst)
        self.creds_dict = creds_dict
        logger.info(f'GoogleDriveDownloader __init__ self.src: {self.src}')
        logger.info(f'GoogleDriveDownloader __init__ self.dst: {self.dst}')

    def _get_service(self):
        from logme import creds_dict as global_creds, SCOPES
        creds_info = self.creds_dict if self.creds_dict else global_creds
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)

    def download_latest(self, gdrive_path: str) -> List[Path]:
        """
        Download files from the latest date folder under the given gdrive_path.
        gdrive_path is like 'path/to/folder'
        """
        service = self._get_service()
        
        # 1. Find the target folder ID
        # Instead of strict path traversal from root, let's look for the specific folder name globally first
        # as Service Accounts often only see what is explicitly shared with them.
        parts = [p for p in gdrive_path.split('/') if p]
        target_folder_name = parts[-1]
        
        logger.info(f"Searching for target folder: '{target_folder_name}'")
        q = f"name = '{target_folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=q, fields="files(id, name)").execute()
        items = results.get('files', [])
        if not items:
            logger.error(f"Folder '{target_folder_name}' not found via global search.")
            return []
        
        # Take the first folder found with that name
        target_folder = items[0]
        parent_id = target_folder['id']
        logger.info(f"Found target folder '{target_folder_name}' with ID: {parent_id}")

        # 2. List subfolders/files to find the latest date
        # Assuming subfolders are named by date or we look at modifiedTime
        results = service.files().list(
            q=f"'{parent_id}' in parents and trashed = false",
            orderBy="name desc", # Assuming names like YYYY-MM-DD
            fields="files(id, name, mimeType, modifiedTime)"
        ).execute()
        items = results.get('files', [])
        if not items:
            logger.info("No items found in target folder.")
            return []

        # Find the latest subfolder (or if it's files directly, we might need different logic)
        # Based on user description: "files of the latest date under gogle_drive_src_path"
        # If it's folders like YYYY-MM-DD, the first one after 'name desc' is the latest.
        latest_folder = items[0]
        logger.info(f"Latest item found: {latest_folder['name']} ({latest_folder['id']})")

        downloaded_files = []
        
        # If it's a folder, download its content
        if latest_folder['mimeType'] == 'application/vnd.google-apps.folder':
            folder_id = latest_folder['id']
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="files(id, name)"
            ).execute()
            files_to_download = results.get('files', [])
        else:
            # If the path itself contains the files, just download the items from the latest date
            # But the prompt says "files of the latest date under", implying a date folder.
            files_to_download = [latest_folder]

        if not self.dst.exists():
            makedirs(self.dst)

        for file in files_to_download:
            file_id = file['id']
            file_name = file['name']
            logger.info(f"Downloading {file_name}...")
           
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download {file_name} {int(status.progress() * 100)}%.")
                print(f"Download {file_name} {int(status.progress() * 100)}%.")
            
            dst_file = self.dst / file_name
            with open(dst_file, "wb") as f:
                f.write(fh.getvalue())
            downloaded_files.append(dst_file)

        return downloaded_files

    def download(self) -> int:
        creds = service_account. \
            Credentials. \
            from_service_account_info(creds_dict, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)

        dst_path = self.dst / self.src  / date_time
        logger.info(f'dst_path: {dst_path}')
        if not dst_path.exists():
            makedirs(dst_path)

        try:
            # Call the Drive v3 API
            results = service.files().list(
                q=f"name contains '{self.src}'",
                pageSize=30, fields="nextPageToken, "
                                    "files(id, name, modifiedTime, parents)").execute()
            items = results.get('files', [])
            if not items:
                logger.info('No files found.')
                return 1
            logger.info('Files:')
            for item in items:
                logger.info(item)
                request = service.files().get(fileId=item['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                status, done = downloader.next_chunk()
                logger.info("Download %d%%." % int(status.progress() * 100))
                dst_file = dst_path / f"{item['id']}_metadata.txt"
                logger.info(f'dst_file: {dst_file}')
                fileText = fh.getbuffer()
                fileTextJson = json.loads(fileText.tobytes())
                if(fileTextJson['mimeType']=='application/vnd.google-apps.spreadsheet'):
                    with open(dst_file, "wb") as f:
                        f.write(fileText)

                # request = service.files().export_media(fileId=item['id'], mimeType='text/csv')
                request = service.files().get(fileId=item['id']).executeMediaAndDownloadTo();
                # request = service.files().get_media(fileId=item['id'])
                # request = service.files().export_media(fileId=item['id'], mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                # fh = io.FileIO(item['name'], mode='wb')
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fd=fh, request=request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    logger.info("Download %d%%." % int(status.progress() * 100))
                fh.seek(0)
                dst_file = dst_path / f"{item['id']}_file.csv"
                with open(dst_file, "wb") as f:
                    f.write(fh.read())
                    f.close()
            exit(0)
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            logger.error(f'An error occurred: {error}')
        return 1
