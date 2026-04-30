Table ('{name}_l1', meta,
    Column('id_post', String, primary_key = True),
    Column('created_at', Integer),
    Column('description', String),
    Column('tags', String),
    Column('mentions', String)
)
