from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def find_by_identifier(
        self, *, email: str | None = None, username: str | None = None
    ) -> Optional[User]:
        if email:
            return self.get_by_email(email)
        if username:
            return self.get_by_username(username)
        return None

    def add(self, user: User) -> None:
        self.db.add(user)
