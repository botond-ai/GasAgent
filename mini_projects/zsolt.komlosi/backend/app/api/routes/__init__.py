"""
API routes package.
"""

from .chat import router as chat_router
from .tickets import router as tickets_router
from .jira import router as jira_router
from .documents import router as documents_router

__all__ = [
    "chat_router",
    "tickets_router",
    "jira_router",
    "documents_router",
]
