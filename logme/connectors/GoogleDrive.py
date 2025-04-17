import io
from os import makedirs
from logme.storage.database import DatabaseHandler
from logme import DB_READ_ERROR, ID_ERROR, creds_dict, SCOPES, CONFIG_FILE_PATH, FILE_ERROR, SUCCESS, date_time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)


class GoogleDriveDownloader:
    """Class to download log files from Google Drive."""

    def __init__(self, src: str, dst: Path) -> None:
        self.src = src
        self.dst = Path(dst)
        logger.info(f'GoogleDriveDownloader __init__ self.src: {self.src}')
        logger.info(f'GoogleDriveDownloader __init__ serlf.dst: {self.dst}')


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
