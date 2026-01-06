from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from itertools import dropwhile, takewhile


Base = declarative_base()


class InstagramRow(Base):
    __tablename__ = "instagram_raw"
    created_at = Column(Integer)
    text = Column(String)
    shortcode = Column(String)
    comment_count = Column(Integer)
    edge_liked_by = Column(Integer)
    owner_id = Column(Integer)
    username = Column(String)
    edge_followed_by = Column(Integer)
    src_file = Column(String)
    ingest_timestamp = Column(Integer)
    hash = Column(String, primary_key=True)

    def __repr__(self):
                return f"<created_at: {self.created_at}, text: {self.text}, shortcode: {self.shortcode}, \
                comment_count: {self.comment_count}, edge_liked_by: {self.edge_liked_by}, \
                owner_id: {self.owner_id}, username: {self.username}, \
                edge_followed_by: {self.edge_followed_by}, src_file: {self.src_file}, \
                ingest_timestamp: {self.ingest_timestamp} ,hash: {self.hash}>"
