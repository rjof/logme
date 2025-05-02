import pandas as pd, re
from sqlalchemy import (create_engine, MetaData, Table,Column, Integer, String, sql)
from pathlib import Path
import shutil
import logging
import os
import configparser
import sys
from logme import CONFIG_FILE_PATH, now_ts
import logme.storage.database as db
from filecmp import cmp
from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
import json, csv, typer

logger = logging.getLogger('ProcessingUtils')

if config.CONFIG_FILE_PATH.exists():
    db_path = db.get_database_path(config.CONFIG_FILE_PATH)
else:
    typer.secho(
        'Config file not found. Please, run "logme init"',
        fg=typer.colors.RED,
    )
    raise typer.Exit(1)
if not db_path.exists():
    typer.secho(
        'Database not found. Please, run "logme init"',
        fg=typer.colors.RED,
    )
    print(f'db_path: {db_path}')
    raise typer.Exit(1)
_db_handler = db.DatabaseHandler(db_path)

def _are_headers_correct(files, conf) -> bool:
    correct_headers = False
    for file in files:
        with open(file, mode='r', encoding='utf-8-sig') as f:
            if _is_csv(conf):
                reader = csv.reader(f)
                header = next(reader)
                if header == conf["fields"]:
                    correct_headers = True
                else:
                    correct_headers = False
                logger.info(f'{correct_headers}: Correct headers in {file}')
        f.close()
    return correct_headers

def _are_field_types_correct() -> int:
    return SUCCESS

def _table_exists(table_name: str) -> bool:
    exists = False
    df, err = _db_handler._list_tables()
    if err != SUCCESS:
        msg = f"Database was not found or readable."
        raise Exception(msg)
    if df[df['name']==table_name].shape[0] > 0:
        return True
    else:
        return False
    
def _create_table(sql_query: str) -> int:
    logger.info(f'Creating table: {sql_query}')
    try:
        sqlite_db = f"sqlite:///{db_path}"
        engine = create_engine(sqlite_db, echo=True)
        # sqlite_connection = engine.connect()
        meta = MetaData()
        tbl = exec(sql_query)
        meta.create_all(engine)
        return SUCCESS
    except OSError:
        return DB_WRITE_ERROR
        
    return True

def _query_from_list_of_fields(src: str, type: str, fields: list[str]) -> str:
    query = f"Table('{src}_{type}', meta,\n"
    for field in fields:
        query += f"  Column('{field}', String),\n"
    query += "  Column('src_file', String, primary_key = True),\n"
    query += "  Column('ingest_timestamp', String, primary_key = True),\n"
    query += "  Column('hash', String, primary_key = True),\n"
    query += ')'
    return query

def _is_csv(conf) -> bool:
    return conf['format'] == "csv"

def _ingest_file_to_db(file:str, table: str, conf: dict) -> pd.DataFrame:
    if _is_csv(conf):
        df = pd.read_csv(file)
        df = _add_hash(df)
        df['src_file'] = file
        df['ingest_timestamp'] = now_ts
        res = _db_handler.df_to_db(df, table)
        return df
    return DB_WRITE_ERROR

def _add_hash(df: pd.DataFrame) -> pd.DataFrame:
    df['hash'] = pd.util.hash_pandas_object(df).apply(str)
    return df

def _raw_to_l1_types(df: pd.DataFrame, conf: dict, confTransformations: dict) -> pd.DataFrame:

    for field in conf['fields']:
        field_index = conf['fields'].index(field)
        match(conf['fields_type'][field_index]):
            case "int":
                df = _col_to_int(field_index, df)
            case "datetime":
                df = _col_to_datetime(field_index, conf['fields_format'][field_index], df)
            case "str":
                index = conf['fields_type'].index("str")
            case "time":
                df = _time_to_seconds(field_index, conf['fields_format'][field_index], df)
            case _:
                raise Exception("Data type not yet implemented")
    for col in confTransformations.keys():
        print(f'col: {col} confT: {confTransformations[col]}')
        try:
            df = df.rename(columns={col : confTransformations[col]})
        except:
            logger.info(f'Column {col} not in raw df')
    df = df[confTransformations.values()]
    df = _add_hash(df)
    return df

def _col_to_int(idx: int, df: pd.DataFrame) -> pd.DataFrame:
    df.iloc[:,[idx]] =  df.iloc[:,[idx]].astype("int")
    return df

def _col_to_datetime(idx: int, format: str, df: pd.DataFrame) -> pd.DataFrame:
    this_col = df.iloc[:,idx]
    new_date = pd.to_datetime(this_col, format=format).dt.tz_localize('America/Mexico_City')
    df.iloc[:,[idx]] = new_date.map(pd.Timestamp.timestamp)
    return df

def _time_to_seconds(idx: int, format: str, df: pd.DataFrame):
    to_remove = re.findall(r'\[(.*)\]', format)
    hms = format.split(":")
    this_col = df.iloc[:,idx]
    for char in to_remove:
        this_col = this_col.map(lambda x: x.strip(char))
    if len(hms) == 3: # contains h, m & s
        format = '%H:%M:%S'
    elif len(hms) == 2: # contains m & s
        format = '%M:%S'
    as_date = pd.to_datetime(this_col, format = format)
    secs = as_date.dt.hour * 3600 + as_date.dt.minute * 60 + as_date.dt.second
    df.iloc[:, idx] = secs
    return df

