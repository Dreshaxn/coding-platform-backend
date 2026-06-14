from typing import Optional

from sqlalchemy.orm import Session

from app.models.language import Language


class LanguageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, language_id: int) -> Optional[Language]:
        return self.db.query(Language).filter(Language.id == language_id).first()

    def get_active_or_default(self, language_id: int | None = None) -> Optional[Language]:
        query = self.db.query(Language).filter(Language.is_active.is_(True))
        if language_id is not None:
            query = query.filter(Language.id == language_id)
        return query.order_by(Language.id.asc()).first()
