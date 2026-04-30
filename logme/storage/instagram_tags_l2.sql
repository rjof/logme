Table ('{name}_tags_l2', meta,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('id_post', String),
    Column('created_at', Integer),
    Column('tag', String)
)
