from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.models.database import Base


class ShareLink(Base):
    """스캔 결과 공유용 임시 링크 (추측 불가능한 토큰 + 만료시간)"""

    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    record_id = Column(Integer, nullable=False)
    user_id = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
