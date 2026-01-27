"""
LangGraph Meeting Notes Agent
=============================

A production-ready AI agent that processes meeting notes,
creates summaries, and schedules Google Calendar events.

Architecture layers:
1. Reasoning layer - LLM decisions, prompting, routing
2. Operational layer - LangGraph workflow, state management
3. Tool execution layer - External APIs (Google Calendar)
4. Memory layer - Deduplication, context handling
"""

__version__ = "1.0.0"
