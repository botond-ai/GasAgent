"""
Agent nodes implementation.
Contains all node functions for the LangGraph workflow.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from app.agent.state import (
    AgentState,
    Step,
    StepStatus,
    EventDetails,
    CalendarEventResult,
    GuardrailResult,
    FinalAnswer,
    PlannerOutput,
    ExtractorOutput,
    SummarizerOutput,
)
from app.agent.prompts import (
    PLANNER_SYSTEM,
    PLANNER_PROMPT,
    SUMMARIZER_SYSTEM,
    SUMMARIZER_PROMPT,
    EXTRACTOR_SYSTEM,
    EXTRACTOR_PROMPT,
    FINAL_ANSWER_SYSTEM,
    FINAL_ANSWER_PROMPT,
    GUARDRAIL_SYSTEM,
    GUARDRAIL_PROMPT,
)
from app.llm.ollama_client import OllamaClient, OllamaError
from app.config import get_settings
from app.memory.store import MemoryStore, get_memory_store
from app.tools.google_calendar import GoogleCalendarTool, get_calendar_tool

logger = logging.getLogger(__name__)


class NodeExecutor:
    """
    Executor class containing all node implementations.
    Handles LLM calls, tool execution, and state management.
    """
    
    def __init__(
        self,
        llm_client: Optional[OllamaClient] = None,
        memory_store: Optional[MemoryStore] = None,
        calendar_tool: Optional[GoogleCalendarTool] = None,
        use_mock_calendar: bool = False,
    ):
        self.settings = get_settings()
        self.llm_client = llm_client or OllamaClient()
        self.memory_store = memory_store or get_memory_store()
        self.calendar_tool = calendar_tool or get_calendar_tool(use_mock=use_mock_calendar)
    
    def planner_node(self, state: AgentState) -> AgentState:
        """
        Planner node: Creates the step list for execution.
        Uses the planner model to generate an execution plan.
        """
        logger.info(f"[Planner] Starting planning for run {state.run_id}")
        
        try:
            model = self.settings.get_model_for_task("planner")
            prompt = PLANNER_PROMPT.format(
                notes_text=state.input.notes_text,
                timezone=state.input.user_timezone,
            )
            
            # Generate structured plan
            result = self.llm_client.generate_structured(
                model=model,
                prompt=prompt,
                response_model=PlannerOutput,
                system=PLANNER_SYSTEM,
            )
            
            # Set steps with proper status
            state.steps = []
            for step_data in result.steps:
                step = Step(
                    name=step_data.name,
                    tool_name=step_data.tool_name,
                    inputs=step_data.inputs,
                    status=StepStatus.PLANNED,
                    rationale=step_data.rationale,
                )
                state.steps.append(step)
            
            state.current_step_index = 0
            state.needs_replan = False
            
            logger.info(f"[Planner] Created {len(state.steps)} steps")
            
        except OllamaError as e:
            logger.error(f"[Planner] LLM error: {e}")
            # Create default plan on failure
            state.steps = self._get_default_steps()
            state.current_step_index = 0
            state.warnings.append(f"Planner used default steps due to: {str(e)[:100]}")
        
        return state
    
    def _get_default_steps(self) -> list[Step]:
        """Return default step list when planner fails."""
        return [
            Step(name="SummarizeNotes", tool_name=None, inputs={}, rationale="Default: summarize meeting notes"),
            Step(name="ExtractNextMeetingDetails", tool_name=None, inputs={}, rationale="Default: extract event details"),
            Step(name="ValidateAndNormalizeEventDetails", tool_name=None, inputs={}, rationale="Default: validate and normalize"),
            Step(name="GuardrailCheck", tool_name=None, inputs={}, rationale="Default: safety check before calendar"),
            Step(name="CreateGoogleCalendarEvent", tool_name="create_calendar_event", inputs={}, rationale="Default: create calendar event"),
            Step(name="ComposeFinalAnswer", tool_name=None, inputs={}, rationale="Default: compose final response"),
        ]
    
    def summarizer_node(self, state: AgentState) -> AgentState:
        """
        Summarizer node: Creates meeting summary with decisions and action items.
        """
        logger.info(f"[Summarizer] Starting summarization")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        try:
            model = self.settings.get_model_for_task("summarizer")
            prompt = SUMMARIZER_PROMPT.format(notes_text=state.input.notes_text)
            
            result = self.llm_client.generate_structured(
                model=model,
                prompt=prompt,
                response_model=SummarizerOutput,
                system=SUMMARIZER_SYSTEM,
            )
            
            state.summary = result.summary
            state.decisions = result.decisions
            state.action_items = result.action_items
            state.risks_open_questions = result.risks_open_questions
            
            # Store hint for extractor
            if step:
                step.result = {"next_meeting_hint": result.next_meeting_hint}
            
            state.mark_current_step_done(result.model_dump())
            logger.info(f"[Summarizer] Completed with {len(state.decisions)} decisions, {len(state.action_items)} actions")
            
        except OllamaError as e:
            logger.error(f"[Summarizer] LLM error: {e}")
            state.mark_current_step_failed(str(e))
            state.summary = "Failed to generate summary due to LLM error."
        
        return state
    
    def extractor_node(self, state: AgentState) -> AgentState:
        """
        Extractor node: Extracts next meeting details from notes.
        """
        logger.info(f"[Extractor] Starting extraction")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        # Get hint from previous step
        next_meeting_hint = ""
        for s in state.steps:
            if s.name == "SummarizeNotes" and s.result:
                next_meeting_hint = s.result.get("next_meeting_hint", "") or ""
                break
        
        try:
            model = self.settings.get_model_for_task("extractor")
            prompt = EXTRACTOR_PROMPT.format(
                notes_text=state.input.notes_text,
                next_meeting_hint=next_meeting_hint,
                current_date=datetime.now().strftime("%Y-%m-%d"),
                timezone=state.input.user_timezone,
            )
            
            result = self.llm_client.generate_structured(
                model=model,
                prompt=prompt,
                response_model=ExtractorOutput,
                system=EXTRACTOR_SYSTEM,
            )
            
            # Convert to EventDetails
            state.event_details = self._extractor_to_event_details(result, state.input.user_timezone)
            
            state.mark_current_step_done(result.model_dump())
            logger.info(f"[Extractor] Completed with confidence {result.confidence}")
            
        except OllamaError as e:
            logger.error(f"[Extractor] LLM error: {e}")
            state.mark_current_step_failed(str(e))
            state.event_details = EventDetails(
                extraction_warnings=["Extraction failed due to LLM error"],
                source_confidence=0.0,
            )
        
        return state
    
    def _extractor_to_event_details(self, result: ExtractorOutput, default_tz: str) -> EventDetails:
        """Convert ExtractorOutput to EventDetails."""
        start_dt = None
        end_dt = None
        
        if result.date and result.time:
            try:
                start_dt = datetime.strptime(f"{result.date} {result.time}", "%Y-%m-%d %H:%M")
                duration = result.duration_minutes or 30
                end_dt = start_dt + timedelta(minutes=duration)
            except ValueError as e:
                logger.warning(f"Failed to parse datetime: {e}")
        
        return EventDetails(
            title=result.title,
            start_datetime=start_dt,
            end_datetime=end_dt,
            timezone=result.timezone or default_tz,
            location=result.location,
            attendees=result.attendees,
            description=result.agenda,
            conference_link=result.conference_link,
            source_confidence=result.confidence,
            extraction_warnings=result.warnings,
        )
    
    def validator_node(self, state: AgentState) -> AgentState:
        """
        Validator node: Validates and normalizes event details.
        Applies defaults for missing optional fields.
        """
        logger.info(f"[Validator] Starting validation")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        if not state.event_details:
            state.event_details = EventDetails()
        
        event = state.event_details
        warnings = list(event.extraction_warnings)
        
        # Validate required fields
        if not event.title:
            warnings.append("Missing event title")
        
        if not event.start_datetime:
            warnings.append("Missing start datetime - cannot create event")
        
        if not event.end_datetime and event.start_datetime:
            # Default to 30 minutes
            event.end_datetime = event.start_datetime + timedelta(minutes=30)
            warnings.append("End time not specified, defaulting to 30 minutes")
        
        # Validate timezone
        if not event.timezone:
            event.timezone = state.input.user_timezone or self.settings.app_timezone
        
        # Update warnings
        event.extraction_warnings = warnings
        
        # Adjust confidence based on completeness
        if not event.is_complete():
            event.source_confidence = min(event.source_confidence, 0.3)
        
        state.mark_current_step_done({
            "is_complete": event.is_complete(),
            "warnings": warnings,
            "confidence": event.source_confidence,
        })
        
        logger.info(f"[Validator] Complete: {event.is_complete()}, Confidence: {event.source_confidence}")
        
        return state
    
    def guardrail_node(self, state: AgentState) -> AgentState:
        """
        Guardrail node: Safety and compliance check before tool execution.
        Checks for sufficient data, sensitive content, and user intent.
        """
        logger.info(f"[Guardrail] Starting safety check")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        result = GuardrailResult()
        event = state.event_details
        
        if not event:
            result.allow = False
            result.reasons.append("No event details available")
            state.guardrail_result = result
            state.mark_current_step_done(result.model_dump())
            return state
        
        # Check completeness
        if not event.is_complete():
            result.allow = False
            result.reasons.append("Event details incomplete (missing title, start, or end)")
            if not event.title:
                result.required_questions.append("What should be the title of the meeting?")
            if not event.start_datetime:
                result.required_questions.append("When should the meeting start? (date and time)")
        
        # Check confidence threshold
        if event.source_confidence < 0.6:
            result.allow = False
            result.reasons.append(f"Low extraction confidence ({event.source_confidence:.2f} < 0.6)")
            result.required_questions.append("Please confirm the meeting details are correct")
        
        # Check for sensitive content in description
        if event.description:
            sensitive_patterns = [
                r'password\s*[:=]',
                r'secret\s*[:=]',
                r'api[_-]?key\s*[:=]',
                r'token\s*[:=]',
            ]
            for pattern in sensitive_patterns:
                if re.search(pattern, event.description, re.IGNORECASE):
                    result.allow = False
                    result.reasons.append("Potential sensitive content detected in description")
                    break
        
        # Check for dry run
        if state.input.dry_run:
            result.allow = False
            result.reasons.append("Dry run mode - calendar event creation disabled")
        
        # Check for duplicates
        similar = self.memory_store.find_similar_event_candidate(event.model_dump())
        if similar and similar[0].similarity > 0.8:
            result.allow = False
            result.duplicate_risk = True
            result.similar_event_ids = [m.created_event_id for m in similar if m.created_event_id]
            result.reasons.append(f"Potential duplicate event detected (similarity: {similar[0].similarity:.2f})")
            result.required_questions.append("A similar event may already exist. Create anyway?")
        
        # If no issues found, allow
        if not result.reasons:
            result.allow = True
            result.reasons.append("All checks passed")
        
        state.guardrail_result = result
        state.mark_current_step_done(result.model_dump())
        
        logger.info(f"[Guardrail] Allow: {result.allow}, Reasons: {result.reasons}")
        
        return state
    
    def tool_node(self, state: AgentState) -> AgentState:
        """
        Tool node: Executes tool calls (Google Calendar).
        Implements retry logic for transient errors.
        """
        logger.info(f"[ToolNode] Starting tool execution")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        # Check guardrail result
        if state.guardrail_result and not state.guardrail_result.allow:
            logger.info(f"[ToolNode] Skipping due to guardrail block")
            if step:
                step.status = StepStatus.SKIPPED
                step.result = {"skipped": True, "reason": "Guardrail blocked"}
            state.current_step_index += 1
            return state
        
        if not state.event_details or not state.event_details.is_complete():
            logger.warning(f"[ToolNode] Event details incomplete, skipping")
            if step:
                step.status = StepStatus.SKIPPED
                step.result = {"skipped": True, "reason": "Incomplete event details"}
            state.current_step_index += 1
            return state
        
        try:
            result = self.calendar_tool.create_event(
                event=state.event_details,
                calendar_id=state.input.calendar_id,
            )
            
            state.calendar_event_result = result
            state.tool_observations.append({
                "tool": "create_calendar_event",
                "result": result.model_dump(),
            })
            
            if result.success:
                # Store in memory for deduplication
                self.memory_store.upsert_run(
                    run_id=state.run_id,
                    notes_hash=state.input.compute_hash(),
                    notes_text=state.input.notes_text,
                    summary=state.summary,
                    event_details=state.event_details.model_dump() if state.event_details else None,
                    created_event_id=result.event_id,
                )
                state.mark_current_step_done(result.model_dump())
                logger.info(f"[ToolNode] Event created: {result.event_id}")
            else:
                state.mark_current_step_failed(result.error or "Unknown error")
                logger.error(f"[ToolNode] Event creation failed: {result.error}")
                
        except Exception as e:
            logger.error(f"[ToolNode] Unexpected error: {e}")
            state.mark_current_step_failed(str(e))
            state.calendar_event_result = CalendarEventResult(
                success=False,
                error=str(e),
            )
        
        return state
    
    def final_answer_node(self, state: AgentState) -> AgentState:
        """
        Final answer node: Composes the final response.
        Combines summary, event details, and calendar result.
        """
        logger.info(f"[FinalAnswer] Composing final answer")
        
        step = state.get_current_step()
        if step:
            step.status = StepStatus.RUNNING
        
        # Determine questions and missing info
        questions = []
        missing = []
        
        if state.guardrail_result and state.guardrail_result.required_questions:
            questions.extend(state.guardrail_result.required_questions)
        
        if state.event_details:
            if not state.event_details.title:
                missing.append("Event title")
            if not state.event_details.start_datetime:
                missing.append("Start date and time")
            if not state.event_details.end_datetime:
                missing.append("End date and time")
        else:
            missing.append("All event details")
        
        # Build final answer
        final = FinalAnswer(
            run_id=state.run_id,
            success=not state.has_fatal_error() and not state.errors,
            summary=state.summary,
            decisions=state.decisions,
            action_items=state.action_items,
            risks_open_questions=state.risks_open_questions,
            event_details=state.event_details,
            calendar_event_result=state.calendar_event_result,
            questions_for_user=questions[:3],  # Max 3 questions
            missing_info=missing,
            errors=state.errors,
            warnings=state.warnings,
            dry_run=state.input.dry_run,
        )
        
        state.final_answer = final
        state.is_complete = True
        state.mark_current_step_done({"final_answer_ready": True})
        
        logger.info(f"[FinalAnswer] Complete. Success: {final.success}")
        
        return state
    
    def router_node(self, state: AgentState) -> str:
        """
        Router node: Determines the next node based on current step.
        Returns the name of the next node to execute.
        """
        step = state.get_current_step()
        
        if not step:
            return "final_answer"
        
        if state.has_fatal_error():
            return "final_answer"
        
        if state.needs_replan:
            return "planner"
        
        # Route based on step name
        step_routes = {
            "SummarizeNotes": "summarizer",
            "ExtractNextMeetingDetails": "extractor",
            "ValidateAndNormalizeEventDetails": "validator",
            "GuardrailCheck": "guardrail",
            "CreateGoogleCalendarEvent": "tool",
            "ComposeFinalAnswer": "final_answer",
        }
        
        return step_routes.get(step.name, "final_answer")
    
    def should_continue(self, state: AgentState) -> str:
        """
        Conditional edge: Determines if execution should continue.
        Returns 'continue' or 'end'.
        """
        if state.is_complete:
            return "end"
        
        if state.has_fatal_error():
            return "end"
        
        if state.all_steps_done():
            return "end"
        
        if state.needs_user_input:
            return "end"
        
        return "continue"


def create_node_executor(**kwargs) -> NodeExecutor:
    """Factory function to create NodeExecutor with dependencies."""
    return NodeExecutor(**kwargs)
