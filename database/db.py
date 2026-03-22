from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import Config
from database.models import Base

_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(Config.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine
