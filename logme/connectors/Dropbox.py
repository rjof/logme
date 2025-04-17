from __future__ import print_function
import argparse
import contextlib
import datetime
from os import path, makedirs
import six
import sys
import time
import unicodedata
from pathlib import Path
from logme import creds_dict, date_time
import json
import logging
if sys.version.startswith('2'):
    input = raw_input  # noqa: E501,F821; pylint: disable=redefined-builtin,undefined-variable,useless-suppression
import dropbox
from os import makedirs
from logme.utils.Utils import isFileInHistory, areFilesEqual

class DropboxConnector:
    """Download the contents from Dropbox.

    This is an example app for API v2.
    """

    def __init__(self, src: Path, dst: Path, conf: dict) -> None:
        self.conf = conf
        self.src = src
        self.dst = dst
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dropboxConnection = dropbox.Dropbox(app_key=creds_dict['dropbox_appkey'], app_secret=creds_dict['dropbox_secret'], oauth2_refresh_token=creds_dict['dropbox_refresh_token'])
        # self.dropboxConnection = dropbox.Dropbox(creds_dict["dropbox_token"])
        # self.dropboxConnection.close()
    
    def checkSrc(self):
        folder = self.conf['src']
        # dst_path = path.expanduser(Path(self.dst) / self.src / f"{date_time}")
        listing = self.list_folder()
        files_downloaded = []

        # TODO: Does not search in subdirectories
        #  only in the directory stated in the config.ini
        for name in listing:
            if self.isFile(listing[name]):
                fullname = f'{folder}/{name}'
                if not isinstance(name, six.text_type):
                    name = name.decode('utf-8')
                nname = unicodedata.normalize('NFC', name)
                if name.startswith('.'):
                    print('Skipping dot file:', name)
                elif name.startswith('@') or name.endswith('~'):
                    print('Skipping temporary file:', name)
                elif name.endswith('.pyc') or name.endswith('.pyo'):
                    print('Skipping generated file:', name)
                elif nname in listing:
                    md = listing[nname]
                    # mtime = md.client_modified.strftime("%Y%m%d%H%M%S")
                    mtime = md.server_modified.strftime("%Y%m%d%H%M%S")
                    mtime_dt = int(mtime)
                    size = md.size
                    self.logger.info(f'Downloading {nname}')
                    res = self.download(folder, name)

                    in_history = isFileInHistory(nname, self.src)
                    if not in_history:
                        makedirs(self.dst)
                        dst_full_name = f'{self.dst}/{nname}'
                        with open(dst_full_name, "wb") as f:
                            self.logger.info(f'Writing to {dst_full_name}')
                            files_downloaded.append(dst_full_name)
                            f.write(res)
                        f.close()
        return files_downloaded


    def list_folder(self, subfolder = ''):
        """List a folder.

        Return a dict mapping unicode filenames to
        FileMetadata|FolderMetadata entries.
        """
        subfolder = ''
        local_path = '/%s/%s' % (self.conf['src'], subfolder.replace(path.sep, '/'))
        while '//' in local_path:
            local_path = local_path.replace('//', '/')
        local_path = local_path.rstrip('/')
        try:
            with self.stopwatch('list_folder'):
                res = self.dropboxConnection.files_list_folder(local_path)
        except dropbox.exceptions.ApiError as err:
            print('Folder listing failed for', path, '-- assumed empty:', err)
            return {}
        else:
            rv = {}
            for entry in res.entries:
                rv[entry.name] = entry
            return rv
        
    def oauth_manual(self):
        from dropbox import DropboxOAuth2FlowNoRedirect
        auth_flow = DropboxOAuth2FlowNoRedirect(creds_dict['dropbox_appkey'], use_pkce=True, token_access_type='offline')

        authorize_url = auth_flow.start()
        print("1. Go to: " + authorize_url)
        print("2. Click \"Allow\" (you might have to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()
        # auth_code = creds_dict['dropbox_access_code']

        try:
            oauth_result = auth_flow.finish(auth_code)
        except Exception as e:
            print('Error: %s' % (e,))
            exit(1)

        with dropbox.Dropbox(oauth2_refresh_token=oauth_result.refresh_token, app_key=creds_dict['dropbox_appkey']) as dbx:
            print("*")
            print(oauth_result.refresh_token)
            print("*")
            dbx.users_get_current_account()
            print("Successfully set up client!")
        exit(0)

    def isFile(self,dropboxMeta):
        return isinstance(dropboxMeta,dropbox.files.FileMetadata)

    def download(self, folder, name):
        """Download a file.

        Return the bytes of the file, or None if it doesn't exist.
        """
        path = '/%s/%s' % (folder, name)
        while '//' in path:
            path = path.replace('//', '/')
        with self.stopwatch('download'):
            try:
                md, res = self.dropboxConnection.files_download(path)
            except dropbox.exceptions.HttpError as err:
                print('*** HTTP error', err)
                return None
        data = res.content
        print(len(data), 'bytes; md:', md)
        return data

    def upload(dbx, fullname, folder, subfolder, name, overwrite=False):
        """Upload a file.

        Return the request response, or None in case of error.

        NOT IN USE
        """
        path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
        while '//' in path:
            path = path.replace('//', '/')
        mode = (dropbox.files.WriteMode.overwrite
                if overwrite
                else dropbox.files.WriteMode.add)
        mtime = os.path.getmtime(fullname)
        with open(fullname, 'rb') as f:
            data = f.read()
        with stopwatch('upload %d bytes' % len(data)):
            try:
                res = dbx.files_upload(
                    data, path, mode,
                    client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                    mute=True)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        print('uploaded as', res.name.encode('utf8'))
        return res

    @contextlib.contextmanager
    def stopwatch(self,message):
        """Context manager to print how long a block of code took."""
        t0 = time.time()
        try:
            yield
        finally:
            t1 = time.time()
            print('Total elapsed time for %s: %.3f' % (message, t1 - t0))
