"""Approval rules; executed by the application, never by the model."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

APPROVAL_TTL_SECONDS = 600
MAX_RECORDS = 1000


class TicketDraft(BaseModel):
    """Propose a synthetic support ticket; this does not create a ticket."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    content: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    category: Literal["access", "network", "software", "hardware", "other"] = "other"
    priority: Literal["low", "normal", "high"] = "normal"

    @model_validator(mode="after")
    def default_title(self):
        if self.title is None:
            self.title = self.content[:80]
        return self


class DecisionConflict(Exception):
    pass


def next_status(status: str, *, approve: bool, expires_at: float, now: float) -> str:
    requested = "approved" if approve else "denied"
    if status == requested:
        return status
    if status != "pending":
        raise DecisionConflict("This approval has already been decided.")
    if expires_at <= now:
        raise DecisionConflict("This approval has expired. Request a new proposal.")
    return requested
