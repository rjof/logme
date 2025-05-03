Table ('{name}_l2', meta,
    Column('in_group', String),
    Column('activity', String),
    Column('comment', String),
    Column('duration_sec', Integer),
    Column('ts_from', Integer),
    Column('ts_to', Integer),
    Column('src', String),
    Column('ts_added', Integer),
    Column('hash', String, primary_key = True)
)