Table ('{name}_mentions_l2', meta,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('id_post', String),
    Column('created_at', Integer),
    Column('mention', String)
)
