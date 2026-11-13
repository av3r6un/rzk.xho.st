from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os

db_url = os.getenv('DB_URL')

connect_args = {'autocommit': False} if db_url and db_url.startswith('sqlite') else {}
engine = create_async_engine(
  db_url, echo=False, hide_parameters=True, pool_recycle=200, pool_pre_ping=True, connect_args=connect_args,
)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def dispose():
  await engine.dispose()
