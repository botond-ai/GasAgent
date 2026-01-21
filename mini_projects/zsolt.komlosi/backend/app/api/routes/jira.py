"""
Jira webhook API endpoint.
"""

import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks

from app.config import get_settings, Settings
from app.models import JiraWebhookResponse
from app.api.deps import get_agent
from app.integrations.jira_client import JiraClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["jira"])


def _format_customer_response(analysis: dict) -> str:
    """Format customer-facing response (only the answer draft)."""
    draft = analysis.get("answer_draft")
    if not draft:
        return ""

    lines = [
        draft.get("greeting", ""),
        "",
        draft.get("body", ""),
        "",
        draft.get("closing", ""),
    ]

    return "\n".join(lines)


def _format_internal_note(analysis: dict) -> str:
    """Format internal analysis note (not visible to customer)."""
    lines = ["🤖 *SupportAI Automatikus Elemzés*", ""]

    triage = analysis.get("triage")
    if triage:
        lines.extend([
            "*📊 Triage Információ:*",
            f"• Nyelv: {triage.get('language', 'N/A')}",
            f"• Kategória: {triage.get('category', 'N/A')}",
            f"• Alkategória: {triage.get('subcategory') or 'N/A'}",
            f"• Prioritás: {triage.get('priority', 'N/A')}",
            f"• SLA: {triage.get('sla_hours', 'N/A')} óra",
            f"• Javasolt csapat: {triage.get('suggested_team', 'N/A')}",
            f"• Ügyfél hangulat: {triage.get('sentiment', 'N/A')}",
            f"• Konfidencia: {int(triage.get('confidence', 0) * 100)}%",
            "",
        ])

    citations = analysis.get("citations", [])
    if citations:
        lines.append("*📚 Felhasznált tudásbázis források:*")
        for citation in citations:
            cit_id = citation.get("id", "?")
            cit_title = citation.get("title", "N/A")
            cit_score = citation.get("score", 0)
            lines.append(f"• [{cit_id}] {cit_title} (relevancia: {int(cit_score * 100)}%)")
        lines.append("")

    pc = analysis.get("policy_check")
    if pc:
        compliance = pc.get("compliance", "passed")
        status_emoji = "✅" if compliance == "passed" else "❌" if compliance == "failed" else "⚠️"
        lines.extend([
            f"*{status_emoji} Policy Check:*",
            f"• Visszatérítés ígéret: {'Igen' if pc.get('refund_promise') else 'Nem'}",
            f"• SLA említve: {'Igen' if pc.get('sla_mentioned') else 'Nem'}",
            f"• Eszkaláció szükséges: {'Igen' if pc.get('escalation_needed') else 'Nem'}",
            "",
        ])

    # Add should_auto_respond recommendation
    should_auto = analysis.get("should_auto_respond", False)
    confidence = triage.get("confidence", 0) if triage else 0
    lines.append("*🎯 Javaslat:*")
    if should_auto and confidence >= 0.85:
        lines.append("• ✅ Az automatikus válasz javasolt (magas konfidencia)")
    else:
        lines.append("• ⚠️ Manuális ellenőrzés javasolt a válasz előtt")

    return "\n".join(lines)


async def _process_and_comment(
    issue_key: str,
    ticket_text: str,
    reporter_name: str,
    agent,
    settings: Settings,
):
    """Background task to process ticket and post comment."""
    try:
        # Analyze the ticket
        result = agent.analyze(
            ticket_text=ticket_text,
            ip_address=None,
            session_id=f"jira-{issue_key}",
            customer_name=reporter_name,
        )

        # Post comments back to Jira if configured
        if settings.jira_configured:
            client = JiraClient()

            # Get confidence level
            triage = result.get("triage") if isinstance(result, dict) else None
            confidence = triage.get("confidence", 0) if triage else 0
            high_confidence = confidence >= 0.85

            # 1. Add internal note with full analysis (always internal)
            internal_note = _format_internal_note(result)
            await client.add_comment(issue_key, internal_note, internal=True)
            logger.info(f"Added internal analysis note to {issue_key}")

            # 2. Handle customer response based on confidence
            customer_response = _format_customer_response(result)
            if customer_response.strip():
                if high_confidence:
                    # High confidence: Send directly to customer as public comment
                    await client.add_comment(issue_key, customer_response, internal=False)
                    logger.info(f"Sent auto-response to customer for {issue_key} (confidence: {confidence:.0%})")
                else:
                    # Low confidence: Add as internal draft for agent review
                    draft_note = f"📝 *Javasolt válasz (konfidencia: {confidence:.0%} - ellenőrizd és küld el manuálisan):*\n\n{customer_response}"
                    await client.add_comment(issue_key, draft_note, internal=True)
                    logger.info(f"Added draft response for {issue_key} (confidence: {confidence:.0%} - needs review)")

            # 3. Update issue fields based on analysis
            triage = result.get("triage") if isinstance(result, dict) else None
            sla_info = result.get("sla_info") if isinstance(result, dict) else None

            # Prepare labels
            labels_to_add = []
            if triage:
                priority_code = triage.get("priority", "P3").lower()
                sentiment = triage.get("sentiment", "neutral")
                labels_to_add.append(f"supportai-{priority_code}")
                labels_to_add.append(f"supportai-{sentiment}")

            # Map AI priority to Jira priority names
            priority_mapping = {
                "P1": "Highest",
                "P2": "Medium",
                "P3": "Low",
                "P4": "Lowest",
            }
            jira_priority = None
            if triage:
                ai_priority = triage.get("priority", "P3")
                jira_priority = priority_mapping.get(ai_priority, "Medium")

            # Get due date from SLA info
            duedate = None
            if sla_info and sla_info.get("deadline"):
                # deadline format: "2024-01-15T14:00:00" - extract date part
                deadline_str = sla_info.get("deadline", "")
                if "T" in deadline_str:
                    duedate = deadline_str.split("T")[0]
                elif deadline_str:
                    duedate = deadline_str[:10]  # Take first 10 chars (YYYY-MM-DD)

            # Update issue with labels, priority, and due date
            issue = await client.get_issue(issue_key)
            existing_labels = getattr(issue, 'labels', []) or []
            new_labels = list(set(existing_labels + labels_to_add)) if labels_to_add else None

            await client.update_issue(
                issue_key,
                labels=new_labels,
                priority=jira_priority,
                duedate=duedate,
            )
            logger.info(f"Updated issue {issue_key}: priority={jira_priority}, duedate={duedate}")

            await client.close()

            logger.info(f"Posted analysis to Jira issue {issue_key}")

    except Exception as e:
        logger.exception(f"Failed to process Jira issue {issue_key}: {e}")


@router.post(
    "/webhook",
    response_model=JiraWebhookResponse,
)
async def jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    agent=Depends(get_agent),
    settings: Settings = Depends(get_settings),
    x_atlassian_token: str = Header(None, alias="X-Atlassian-Token"),
):
    """
    Handle Jira webhook events.

    Processes new ticket creation events and runs SupportAI analysis.
    Posts analysis results back to Jira as a comment.
    """
    # Verify webhook secret if configured
    if settings.jira_webhook_secret:
        if x_atlassian_token != settings.jira_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        payload = await request.json()

        # Check for webhookEvent (standard Jira) or just process if issue exists (JSM)
        event_type = payload.get("webhookEvent", "")

        # If no webhookEvent but issue exists, treat as issue_created (JSM format)
        if not event_type and "issue" in payload:
            event_type = "jira:issue_created"
            logger.info("No webhookEvent field, assuming JSM format - treating as issue_created")

        if event_type not in ["jira:issue_created", "jira:issue_updated"]:
            return JiraWebhookResponse(
                status="ignored",
                message=f"Event type {event_type} not handled",
            )

        # Extract issue data
        issue = payload.get("issue", {})
        issue_key = issue.get("key", "")
        fields = issue.get("fields", {})

        summary = fields.get("summary", "")
        description = fields.get("description", "") or ""

        # Extract reporter name
        reporter = fields.get("reporter") or {}
        reporter_name = reporter.get("displayName") or reporter.get("name") or "Ügyfelünk"

        # Handle Atlassian Document Format for description
        if isinstance(description, dict):
            # Extract text from ADF
            content = description.get("content", [])
            text_parts = []
            for block in content:
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
            description = "\n".join(text_parts)

        # Combine summary and description for analysis
        ticket_text = f"{summary}\n\n{description}".strip()

        if not ticket_text:
            return JiraWebhookResponse(
                status="ignored",
                message="No ticket content found",
            )

        # Process in background to respond quickly to webhook
        background_tasks.add_task(
            _process_and_comment,
            issue_key,
            ticket_text,
            reporter_name,
            agent,
            settings,
        )

        return JiraWebhookResponse(
            status="processing",
            ticket_id=issue_key,
            message="Ticket analysis started",
        )

    except Exception as e:
        logger.exception("Jira webhook error")
        return JiraWebhookResponse(
            status="error",
            message=str(e),
        )


@router.get("/status")
async def jira_status(settings: Settings = Depends(get_settings)):
    """Check Jira integration status."""
    return {
        "configured": settings.jira_configured,
        "url": settings.jira_url if settings.jira_configured else None,
    }
