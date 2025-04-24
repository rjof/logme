from pathlib import Path
import shutil
import logging
import os
import configparser
import sys
from logme import CONFIG_FILE_PATH, history_path, CONFIG_DIR_PATH
from filecmp import cmp
import re, json

logger = logging.getLogger('Utils')

def move_file_in_local_system(src_file: Path, dst_file: Path):
    logger.info(f"Moving file {src_file} to {dst_file}")
    # dst_file = Path(dst_path / os.path.basename(src_file))
    # source file exists?
    if not src_file.exists():
        logger.info(f"{src_file} not present")
        return 2
    
    # destination file exists?
    if dst_file.is_file():
        # as the dst file exists, get modification time of file
        if os.path.getmtime(src_file) > os.path.getmtime(dst_file):
            shutil.move(src_file, dst_file)
        else:
            msg = f"Source file {src_file} is older than {dst_file}"
            raise Exception(msg)
    else:
        dst_path = Path(str(dst_file).replace(str(os.path.basename(dst_file)),""))
        if not dst_path.exists():
            logger.info(f"Creates directory: {dst_path}")
            os.makedirs(dst_path)
        shutil.move(src_file, dst_file)


def get_local_storage_path(config_file: Path) -> Path:
    """Return the local path to the downloaded files."""
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file)
    return Path(config_parser["LocalPaths"]["storage"])


def get_source_conf(src: str = None, section: str = None) -> dict:
    config_parser = configparser.ConfigParser()
    config_parser.optionxform=str
    file = CONFIG_DIR_PATH / f'{src}.ini'
    config_parser.read(file)
    # options = [option for option in config_parser[section]]
    thedict0 = {}
    for key, val in config_parser.items(section):
        if key == 'days_to_retrieve_api':
            thedict0[key] = float(val)
        else:
            thedict0[key] = val
    thedict = {}
    for key, value in thedict0.items():
        if key == 'fields':
            thedict[key] = [ f.strip() for f in value.split(",") ]
        elif key == 'fields_type':
            thedict[key] = [ f.strip() for f in value.split(",") ]
        elif key == 'fields_format':
            thedict[key] = re.findall(r'"([^"]*)"', value)
        else:
            thedict[key] = value
    logger.info(f'Configuration of source {src}.ini: [{section}]:\n{json.dumps(thedict, indent=4)}')
    return thedict

def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)

def areFilesEqual(path_file1: Path, path_file2) -> bool:
    cmp(path_file1,path_file2, shallow=true)

def isFileInHistory(file_name: str, src_type: str, sub_folder: str = '') -> bool:
    path = Path(f'{history_path}/{sub_folder}/{src_type}')
    for dirpath, dirnames, filenames in os.walk(path):
        found = [f for f in filenames if f == file_name]
    if len(found) > 0:
        logger.info(f'File {file_name} found in {dirpath}')
        return True
    else:
        logger.info(f'File {file_name} not found in {dirpath}')
        return False
    
def get_src_conf(config_file: Path) -> Path:
    """Return the configparser object of the source to ingest & process."""
    config_parser = configparser.ConfigParser()
    return config_parser.read(config_file)

    if not config.CONFIG_FILE_PATH.exists():
        typer.secho(
            'Config file not found.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

