from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.settings import settings

# گ"گ>‘? ‘?گّگْ‘?گّگ+گ?‘'گَگٌ گٌ‘?گُگ? SQLite
DB_URL = settings.DB_URL

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# گ'گ?گ-گ?گ?: گٌگ?گُگ?‘?‘' گ?گ?گ?گçگ>گçگü گُگ?‘?گ>گç گ?گ+‘?‘?گ?گ>گçگ?گٌ‘? Base,
# ‘ط‘'گ?گ+‘< metadata گْگ?گّگ>گّ گُ‘?گ? گ?‘?گç ‘'گّگ+گ>گٌ‘إ‘<
from app import models  # noqa: E402,F401  - گٌگ?گُگ?‘?‘' گ?‘?‘'گّگ?گ>‘?گçگ? گ? گَگ?گ?‘إگç ‘"گّگüگ>گّ

# گِگ?گْگ?گّ‘'گ? ‘'گّگ+گ>گٌ‘إ‘< گ? گ'گ", گç‘?گ>گٌ گٌ‘: گç‘%‘' گ?گç‘'
Base.metadata.create_all(bind=engine)
