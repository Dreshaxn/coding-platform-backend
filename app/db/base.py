
from sqlalchemy.orm import declarative_base

   
Base = declarative_base()
 # Import your models here so Alembic can see them
from app.models.user import User  