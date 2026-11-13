from datetime import datetime as dt, date
from decimal import Decimal
from enum import Enum
import secrets
import string

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column, selectinload, DeclarativeBase, Mapped
from sqlalchemy import inspect, select, func, DateTime, Integer, asc, desc


class Base(DeclarativeBase):
  created_at: Mapped[dt] = mapped_column(DateTime, server_default=func.now(), nullable=False)
  updated_at: Mapped[dt] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
  
  @property
  def created_ts(self):
    return int(self.created_at.timestamp())
  
  @property
  def updated_ts(self):
    return int(self.updated_at.timestamp())
  
  @classmethod
  def __build_filters(cls, **filters):
    simple, exps = {}, []
    for k, v in filters.items():
      if '__' in k:
        field, op = k.split('__', 1)
        col = getattr(cls, field)
        if op == 'gte': exps.append(col >= v)
        elif op == 'lte': exps.append(col <= v)
        elif op == 'gt': exps.append(col > v)
        elif op == 'lt': exps.append(col < v)
        elif op == 'like': exps.append(col.like(v))
        elif op == 'ilike': exps.append(col.ilike(f'%{v}%'))
        elif op == 'date': exps.append(func.date(col) == v if isinstance(v, date) else date.fromisoformat(v))
        elif op == 'notnull': exps.append(col.isnot(None))
        elif op == 'isnull': exps.append(col.is_(None))
      else:
        simple[k] = v
    return simple, exps
  
  @classmethod
  def __get_column(cls, field: str):
    col = getattr(cls, field, None)
    if col is None:
      raise AttributeError(f'There is no column: {field}')
    return col
  
  @classmethod
  def __build_order_by(cls, order_by: str | list[str] | None):
    if not order_by:
      return []
    
    if isinstance(order_by, str):
      order_by = [order_by]
    
    expressions = []
    for field in order_by:
      direction = desc if field.startswith('-') else asc
      field = field[1:] if field.startswith('-') else field
      expressions.append(direction(cls.__get_column(field)))
    return expressions
  
  @classmethod
  def __build_group_by(cls, group_by: str | list[str] | None):
    if not group_by:
      return []
    
    if isinstance(group_by, str):
      group_by = [group_by]
      
    return [cls.__get_column(field) for field in group_by]
  
  @staticmethod
  def __json_value(value):
    if isinstance(value, Decimal):
      return str(value)
    if isinstance(value, Enum):
      return value.value
    if isinstance(value, dt):
      return int(value.timestamp())
    if isinstance(value, date):
      return value.isoformat()
    return value

  @classmethod
  async def get(cls, session: AsyncSession, *, relationships: list[str] | None = None, **filters):
    order_by = filters.pop('order_by', None)
    group_by = filters.pop('group_by', None)
    
    query = select(cls)
    
    mapper = inspect(cls)
    relation_names = (
      [rel.key for rel in mapper.relationships] if relationships is None else relationships
    )
    for name in relation_names:
      if name not in mapper.relationships:
        raise AttributeError(f'{cls.__name__} has no relationship: {name}')
      query = query.options(selectinload(getattr(cls, name)))
    
    simple, expressions = cls.__build_filters(**filters)
    if simple:
      query = query.filter_by(**simple)
    if expressions:
      query = query.filter(*expressions)
    
    groups = cls.__build_group_by(group_by)
    if groups:
      query = query.group_by(*groups)
      
    ordering = cls.__build_order_by(order_by)
    if ordering:
      query = query.order_by(*ordering)
      
    result = await session.execute(query)
    return result.scalars()
  
  @classmethod
  async def get_multi(cls, session: AsyncSession, field: str, variables: list):
    if not getattr(cls, field, None):
      raise AttributeError(f'There is no column: {field}')
    query = select(cls).where(getattr(cls, field).in_(variables))
    result = await session.execute(query)
    return result.scalars().all()
  
  @classmethod
  async def all(cls, session, **filters):
    return (await cls.get(session, **filters)).all()
  
  @classmethod
  async def first(cls, session, **filters):
    return (await cls.get(session, **filters)).first()
  
  @classmethod
  async def grouped(cls, session: AsyncSession, group_by: str | list[str], aggregates: dict, **filters):
    groups = cls.__build_group_by(group_by)
    columns = [*groups]
    
    for name, expression in aggregates.items():
      columns.append(expression.label(name))
    query = select(*columns)
    
    simple, expressions = cls.__build_filters(**filters)
    if simple:
      query = query.filter_by(**simple)
    if expressions:
      query = query.filter(*expressions)
      
    query = query.group_by(*groups)
    result = await session.execute(query)
    return [
      {k: cls.__json_value(v) for k, v in row.items()}
      for row in result.mappings().all()
    ]
  
  @classmethod
  async def create_uid(cls, session: AsyncSession):
    existing = await session.execute(select(cls.uid))
    uids = set(existing.scalars().all())
    alp = string.ascii_letters + string.digits
    while True:
      uid = ''.join(secrets.choice(alp) for _ in range(cls.__table__.c.uid.type.length))
      if uid not in uids:
        return uid
  
  def edit(self, **kwargs):
    columns = {col.key for col in self.__table__.columns}
    for k, v in kwargs.items():
      if k not in columns:
        continue
      if isinstance(self.__table__.columns.get(k).type, DateTime):
        if isinstance(v, (int, float)):
          v = dt.fromtimestamp()
      if isinstance(self.__table__.columns.get(k).type, Integer):
        if isinstance(v, dt):
          v = int(v.timestamp())
      setattr(self, k, v)

  async def delete(self, session: AsyncSession):
    await session.delete(self)
