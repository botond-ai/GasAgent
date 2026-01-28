from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import uuid

from .domain.models import MeetingSummary as MeetingSummaryModel, Task as TaskModel
from .services import llm

app = FastAPI(title="MeetingAI - Backend")


class SummarizeRequest(BaseModel):
    transcript: str
    title: Optional[str] = None
    date: Optional[str] = None
    participants: Optional[List[str]] = None


class ExtractTasksRequest(BaseModel):
    transcript: str
    meeting_reference: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/summarize", response_model=MeetingSummaryModel)
def summarize(req: SummarizeRequest):
    meeting_id = f"MTG-{uuid.uuid4().hex[:8]}"
    result = llm.analyze_transcript(req.transcript)
    return MeetingSummaryModel(
        meeting_id=meeting_id,
        title=req.title or result.get("title") or "Untitled Meeting",
        date=req.date,
        participants=req.participants or result.get("participants", []),
        summary=result.get("summary", ""),
        key_decisions=result.get("key_decisions", []),
        next_steps=result.get("next_steps", []),
        tasks=[TaskModel(**t) if isinstance(t, dict) else t for t in result.get("tasks", [])],
    )


@app.post("/extract_tasks", response_model=List[TaskModel])
def extract_tasks(req: ExtractTasksRequest):
    result = llm.analyze_transcript(req.transcript)
    tasks = result.get("tasks", [])
    return [TaskModel(**t) if isinstance(t, dict) else t for t in tasks]
