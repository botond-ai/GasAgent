"""
Jira MCP Server for SupportAI.

This MCP server exposes Jira operations as tools that can be used by AI agents.
Implements the Model Context Protocol (MCP) specification.
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from .jira_client import JiraClient

logger = logging.getLogger(__name__)

# Initialize MCP server
server = Server("jira-supportai")

# Jira client instance (initialized on first use)
_jira_client: JiraClient | None = None


def get_jira_client() -> JiraClient:
    """Get or create Jira client."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient()
    return _jira_client


# Define available tools
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Jira tools."""
    return [
        Tool(
            name="jira_get_issue",
            description="Get a Jira issue by its key (e.g., PROJ-123). Returns issue details including summary, description, status, priority, and more.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key (e.g., PROJ-123)",
                    }
                },
                "required": ["issue_key"],
            },
        ),
        Tool(
            name="jira_search_issues",
            description="Search for Jira issues using JQL (Jira Query Language). Returns a list of matching issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string (e.g., 'project = PROJ AND status = Open')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["jql"],
            },
        ),
        Tool(
            name="jira_add_comment",
            description="Add a comment to a Jira issue. Useful for posting AI analysis results or responses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key (e.g., PROJ-123)",
                    },
                    "body": {
                        "type": "string",
                        "description": "The comment text to add",
                    },
                },
                "required": ["issue_key", "body"],
            },
        ),
        Tool(
            name="jira_get_comments",
            description="Get all comments for a Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key (e.g., PROJ-123)",
                    },
                },
                "required": ["issue_key"],
            },
        ),
        Tool(
            name="jira_update_issue",
            description="Update fields on a Jira issue (summary, description, priority, labels).",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key (e.g., PROJ-123)",
                    },
                    "summary": {
                        "type": "string",
                        "description": "New summary (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description (optional)",
                    },
                    "priority": {
                        "type": "string",
                        "description": "New priority name (optional)",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New labels (optional)",
                    },
                },
                "required": ["issue_key"],
            },
        ),
        Tool(
            name="jira_transition_issue",
            description="Transition a Jira issue to a new status (e.g., 'In Progress', 'Done').",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key (e.g., PROJ-123)",
                    },
                    "transition_name": {
                        "type": "string",
                        "description": "Name of the transition (e.g., 'In Progress', 'Done')",
                    },
                },
                "required": ["issue_key", "transition_name"],
            },
        ),
        Tool(
            name="jira_create_issue",
            description="Create a new Jira issue in a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Project key (e.g., PROJ)",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Issue summary/title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Issue description",
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Issue type (default: Task)",
                        "default": "Task",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority name (optional)",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Issue labels (optional)",
                    },
                },
                "required": ["project_key", "summary", "description"],
            },
        ),
        Tool(
            name="jira_get_projects",
            description="List all accessible Jira projects.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="jira_analyze_and_comment",
            description="Analyze a Jira issue using SupportAI and post the analysis as a comment. This combines getting the issue, running AI analysis, and posting results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "The Jira issue key to analyze (e.g., PROJ-123)",
                    },
                },
                "required": ["issue_key"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    client = get_jira_client()

    if not client.is_configured:
        return [
            TextContent(
                type="text",
                text="Error: Jira is not configured. Please set JIRA_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN environment variables.",
            )
        ]

    try:
        result = await _execute_tool(client, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _execute_tool(client: JiraClient, name: str, args: dict[str, Any]) -> dict:
    """Execute a tool and return results."""

    if name == "jira_get_issue":
        issue = await client.get_issue(args["issue_key"])
        return {
            "key": issue.key,
            "summary": issue.summary,
            "description": issue.description,
            "status": issue.status,
            "priority": issue.priority,
            "issue_type": issue.issue_type,
            "project": issue.project_key,
            "reporter": issue.reporter,
            "assignee": issue.assignee,
            "created": issue.created,
            "updated": issue.updated,
            "labels": issue.labels,
        }

    elif name == "jira_search_issues":
        issues = await client.search_issues(
            jql=args["jql"],
            max_results=args.get("max_results", 20),
        )
        return {
            "count": len(issues),
            "issues": [
                {
                    "key": i.key,
                    "summary": i.summary,
                    "status": i.status,
                    "priority": i.priority,
                    "issue_type": i.issue_type,
                }
                for i in issues
            ],
        }

    elif name == "jira_add_comment":
        comment = await client.add_comment(args["issue_key"], args["body"])
        return {
            "success": True,
            "comment_id": comment.id,
            "author": comment.author,
            "created": comment.created,
        }

    elif name == "jira_get_comments":
        comments = await client.get_comments(args["issue_key"])
        return {
            "count": len(comments),
            "comments": [
                {
                    "id": c.id,
                    "body": c.body,
                    "author": c.author,
                    "created": c.created,
                }
                for c in comments
            ],
        }

    elif name == "jira_update_issue":
        await client.update_issue(
            issue_key=args["issue_key"],
            summary=args.get("summary"),
            description=args.get("description"),
            priority=args.get("priority"),
            labels=args.get("labels"),
        )
        return {"success": True, "issue_key": args["issue_key"]}

    elif name == "jira_transition_issue":
        await client.transition_issue(args["issue_key"], args["transition_name"])
        return {
            "success": True,
            "issue_key": args["issue_key"],
            "transition": args["transition_name"],
        }

    elif name == "jira_create_issue":
        issue = await client.create_issue(
            project_key=args["project_key"],
            summary=args["summary"],
            description=args["description"],
            issue_type=args.get("issue_type", "Task"),
            priority=args.get("priority"),
            labels=args.get("labels"),
        )
        return {
            "success": True,
            "key": issue.key,
            "summary": issue.summary,
            "status": issue.status,
        }

    elif name == "jira_get_projects":
        projects = await client.get_projects()
        return {
            "count": len(projects),
            "projects": [
                {
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "id": p.get("id"),
                }
                for p in projects
            ],
        }

    elif name == "jira_analyze_and_comment":
        # This tool combines multiple operations
        # 1. Get the issue
        issue = await client.get_issue(args["issue_key"])

        # 2. Analyze with SupportAI (import here to avoid circular imports)
        from app.core.agent import SupportAIAgent

        agent = SupportAIAgent()
        ticket_text = f"{issue.summary}\n\n{issue.description or ''}"

        analysis = agent.analyze(
            ticket_text=ticket_text,
            session_id=f"jira-{issue.key}",
        )

        # 3. Format the analysis as a comment
        comment_body = _format_analysis_comment(analysis)

        # 4. Post the comment
        comment = await client.add_comment(issue.key, comment_body)

        return {
            "success": True,
            "issue_key": issue.key,
            "analysis": {
                "category": analysis.triage.category if analysis.triage else None,
                "priority": analysis.triage.priority if analysis.triage else None,
                "sentiment": analysis.triage.sentiment if analysis.triage else None,
            },
            "comment_id": comment.id,
        }

    else:
        raise ValueError(f"Unknown tool: {name}")


def _format_analysis_comment(analysis) -> str:
    """Format SupportAI analysis as a Jira comment."""
    lines = ["*SupportAI Analysis*", ""]

    if analysis.triage:
        triage = analysis.triage
        lines.extend([
            f"*Kategória:* {triage.category}",
            f"*Alkategória:* {triage.subcategory or 'N/A'}",
            f"*Prioritás:* {triage.priority}",
            f"*SLA:* {triage.sla_hours} óra",
            f"*Javasolt csapat:* {triage.suggested_team}",
            f"*Hangulat:* {triage.sentiment}",
            f"*Konfidencia:* {int(triage.confidence * 100)}%",
            "",
        ])

    if analysis.answer_draft:
        draft = analysis.answer_draft
        lines.extend([
            "*Javasolt válasz:*",
            "----",
            draft.greeting,
            "",
            draft.body,
            "",
            draft.closing,
            "----",
            "",
        ])

    if analysis.citations:
        lines.append("*Felhasznált források:*")
        for citation in analysis.citations:
            lines.append(f"- [{citation.id}] {citation.title} (relevancia: {int(citation.score * 100)}%)")
        lines.append("")

    if analysis.policy_check:
        pc = analysis.policy_check
        lines.extend([
            "*Policy Check:*",
            f"- Visszatérítés ígéret: {'Igen' if pc.refund_promise else 'Nem'}",
            f"- SLA említve: {'Igen' if pc.sla_mentioned else 'Nem'}",
            f"- Eszkaláció szükséges: {'Igen' if pc.escalation_needed else 'Nem'}",
            f"- Megfelelőség: {pc.compliance}",
        ])

    return "\n".join(lines)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
