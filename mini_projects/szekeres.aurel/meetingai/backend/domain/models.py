from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Short task title")
    assignee: Optional[str] = Field(None, description="Person responsible")
    due_date: Optional[str] = Field(None, description="Optional due date (YYYY-MM-DD)")
    priority: Optional[str] = Field(None, description="Priority e.g. P1, P2")
    status: Optional[str] = Field("to-do", description="Task status")
    meeting_reference: Optional[str] = Field(None, description="Related meeting id")


class MeetingSummary(BaseModel):
    meeting_id: str = Field(..., description="Unique meeting id")
    title: Optional[str] = Field(None, description="Meeting title")
    date: Optional[str] = Field(None, description="Meeting date (YYYY-MM-DD)")
    participants: List[str] = Field(default_factory=list, description="Participants list")
    summary: str = Field(..., description="Executive summary of the meeting")
    key_decisions: List[str] = Field(default_factory=list, description="Key decisions made")
    next_steps: List[str] = Field(default_factory=list, description="Next steps / action items")
    tasks: List[Task] = Field(default_factory=list, description="Optional extracted tasks")
