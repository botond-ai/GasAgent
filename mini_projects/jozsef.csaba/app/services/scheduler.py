"""Background scheduler for Jira polling.

Implements a periodic task that polls Jira for new tickets and processes them
through the triage workflow.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import Settings, get_settings
from app.core.dependencies import get_workflow
from app.models.schemas import JiraTicket, TicketInput
from app.services.jira import JiraService

logger = logging.getLogger(__name__)


class JiraPollingScheduler:
    """Background scheduler that polls Jira for new tickets."""

    def __init__(self, settings: Settings):
        """Initialize the scheduler.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.jira_service = JiraService(settings)
        self.workflow = get_workflow(settings)
        self.last_poll_time: datetime = datetime.now(timezone.utc)
        self._running = False
        self._task: asyncio.Task | None = None

    def _convert_to_ticket_input(self, jira_ticket: JiraTicket) -> TicketInput:
        """Convert a JiraTicket to TicketInput for the triage workflow.

        Args:
            jira_ticket: Jira ticket data

        Returns:
            TicketInput compatible with the triage workflow
        """
        return TicketInput(
            customer_name=jira_ticket.reporter_name or "Unknown",
            customer_email=jira_ticket.reporter_email or "unknown@jira.local",
            subject=jira_ticket.summary,
            message=jira_ticket.description or jira_ticket.summary,
            ticket_id=jira_ticket.key,
        )

    async def _poll_once(self) -> int:
        """Execute a single poll cycle.

        Returns:
            Number of tickets processed
        """
        try:
            tickets = await self.jira_service.fetch_new_tickets(self.last_poll_time)

            if not tickets:
                logger.debug("No new tickets found in Jira")
                return 0

            logger.info(f"Found {len(tickets)} new tickets in Jira")

            processed = 0
            for jira_ticket in tickets:
                try:
                    ticket_input = self._convert_to_ticket_input(jira_ticket)
                    response = self.workflow.process_ticket(ticket_input)
                    logger.info(
                        f"Processed Jira ticket {jira_ticket.key}: "
                        f"priority={response.triage.priority}, "
                        f"category={response.triage.category}"
                    )
                    processed += 1
                except Exception as e:
                    logger.error(f"Error processing ticket {jira_ticket.key}: {e}")

            # Update last poll time to the most recent ticket's creation time
            if tickets:
                self.last_poll_time = max(t.created for t in tickets)

            return processed

        except Exception as e:
            logger.error(f"Error polling Jira: {e}")
            return 0

    async def _run_loop(self) -> None:
        """Run the polling loop indefinitely."""
        logger.info(
            f"Starting Jira polling scheduler (interval: {self.settings.jira_poll_interval}s)"
        )

        while self._running:
            await self._poll_once()
            await asyncio.sleep(self.settings.jira_poll_interval)

    def start(self) -> asyncio.Task:
        """Start the polling scheduler.

        Returns:
            The asyncio Task running the scheduler
        """
        if self._running:
            logger.warning("Scheduler is already running")
            return self._task

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        return self._task

    def stop(self) -> None:
        """Stop the polling scheduler."""
        logger.info("Stopping Jira polling scheduler")
        self._running = False
        if self._task:
            self._task.cancel()


# Module-level scheduler instance
_scheduler: JiraPollingScheduler | None = None


async def start_jira_polling() -> asyncio.Task | None:
    """Start the Jira polling scheduler if enabled.

    Returns:
        The scheduler task if started, None if Jira is disabled
    """
    global _scheduler

    settings = get_settings()

    if not settings.jira_enabled:
        logger.info("Jira integration is disabled")
        return None

    if not settings.jira_url or not settings.jira_email or not settings.jira_api_token:
        logger.warning(
            "Jira is enabled but credentials are missing. "
            "Set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
        )
        return None

    _scheduler = JiraPollingScheduler(settings)

    # Test connection before starting
    jira_service = JiraService(settings)
    if await jira_service.test_connection():
        logger.info("Jira connection test successful")
        return _scheduler.start()
    else:
        logger.error("Jira connection test failed. Check your credentials.")
        return None


def stop_jira_polling() -> None:
    """Stop the Jira polling scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
