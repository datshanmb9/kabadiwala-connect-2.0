from datetime import datetime

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    notification_id: str
    type: str
    title_key: str
    message_key: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    read: bool
    created_at: datetime
    read_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    has_more: bool


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked_count: int
    unread_count: int
