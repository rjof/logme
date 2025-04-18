Table ('{name}_l1', meta,
    Column('no', Integer),
    Column('ts', Integer),
    Column('name', String),
    Column('repeat', String),
    Column('action', String),
    Column('elapsed_sec', Integer),
    Column('duration_sec', Integer),
    Column('process_ts', Integer),
    Column('hash', String, primary_key = True)
)