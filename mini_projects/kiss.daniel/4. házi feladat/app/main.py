"""
CLI entry point for the Meeting Notes Agent.
Provides command-line interface for processing meeting notes.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings
from app.llm.ollama_client import OllamaClient, OllamaError
from app.agent.graph import run_agent
from app.agent.state import FinalAnswer


def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)


def validate_ollama_models() -> bool:
    """Validate that configured Ollama models are available."""
    try:
        client = OllamaClient()
        report = client.validate_configured_models()
        
        print("\n📋 Model Validation Report:")
        print(f"   Available models: {', '.join(report['available_models'])}")
        print(f"   Profile: {get_settings().agent_profile.value}")
        print()
        
        for task, info in report['configured'].items():
            status = "✅" if info['valid'] else "⚠️"
            msg = f"   {status} {task}: {info['model']}"
            if info['fallback']:
                msg += f" → fallback: {info['fallback']}"
            print(msg)
        
        if report['warnings']:
            print("\n⚠️  Warnings:")
            for warning in report['warnings']:
                print(f"   - {warning}")
        
        if report['errors']:
            print("\n❌ Errors:")
            for error in report['errors']:
                print(f"   - {error}")
            return False
        
        print()
        client.close()
        return True
        
    except OllamaError as e:
        print(f"\n❌ Failed to connect to Ollama: {e}")
        print(f"   Make sure Ollama is running at {get_settings().ollama_base_url}")
        return False


def format_final_answer(answer: FinalAnswer) -> str:
    """Format the final answer for human-readable output."""
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("🤖 MEETING NOTES AGENT - FINAL ANSWER")
    lines.append("=" * 60)
    lines.append(f"Run ID: {answer.run_id}")
    lines.append(f"Status: {'✅ Success' if answer.success else '❌ Failed'}")
    if answer.dry_run:
        lines.append("Mode: 🧪 DRY RUN (no calendar event created)")
    lines.append("")
    
    # Summary
    if answer.summary:
        lines.append("📝 SUMMARY")
        lines.append("-" * 40)
        lines.append(answer.summary)
        lines.append("")
    
    # Decisions
    if answer.decisions:
        lines.append("📌 DECISIONS")
        lines.append("-" * 40)
        for decision in answer.decisions:
            lines.append(f"  • {decision}")
        lines.append("")
    
    # Action Items
    if answer.action_items:
        lines.append("✅ ACTION ITEMS")
        lines.append("-" * 40)
        for item in answer.action_items:
            task = item.get('task', 'N/A')
            owner = item.get('owner', 'N/A')
            due = item.get('due', 'N/A')
            lines.append(f"  • {task}")
            lines.append(f"    Owner: {owner} | Due: {due}")
        lines.append("")
    
    # Risks/Questions
    if answer.risks_open_questions:
        lines.append("⚠️  RISKS & OPEN QUESTIONS")
        lines.append("-" * 40)
        for item in answer.risks_open_questions:
            lines.append(f"  • {item}")
        lines.append("")
    
    # Event Details
    if answer.event_details:
        lines.append("📅 EXTRACTED EVENT DETAILS")
        lines.append("-" * 40)
        event = answer.event_details
        lines.append(f"  Title: {event.title or 'N/A'}")
        lines.append(f"  Start: {event.start_datetime or 'N/A'}")
        lines.append(f"  End: {event.end_datetime or 'N/A'}")
        lines.append(f"  Timezone: {event.timezone}")
        lines.append(f"  Location: {event.location or 'N/A'}")
        lines.append(f"  Attendees: {', '.join(event.attendees) if event.attendees else 'N/A'}")
        lines.append(f"  Confidence: {event.source_confidence:.0%}")
        if event.extraction_warnings:
            lines.append(f"  Warnings: {', '.join(event.extraction_warnings)}")
        lines.append("")
    
    # Calendar Result
    if answer.calendar_event_result:
        result = answer.calendar_event_result
        lines.append("📆 CALENDAR EVENT")
        lines.append("-" * 40)
        if result.success:
            lines.append(f"  ✅ Event created successfully!")
            lines.append(f"  Event ID: {result.event_id}")
            lines.append(f"  Link: {result.html_link}")
        else:
            lines.append(f"  ❌ Event creation failed: {result.error}")
        lines.append("")
    
    # Questions for User
    if answer.questions_for_user:
        lines.append("❓ QUESTIONS FOR YOU")
        lines.append("-" * 40)
        for i, question in enumerate(answer.questions_for_user, 1):
            lines.append(f"  {i}. {question}")
        lines.append("")
    
    # Missing Info
    if answer.missing_info:
        lines.append("📋 MISSING INFORMATION")
        lines.append("-" * 40)
        for item in answer.missing_info:
            lines.append(f"  • {item}")
        lines.append("")
    
    # Warnings
    if answer.warnings:
        lines.append("⚠️  WARNINGS")
        lines.append("-" * 40)
        for warning in answer.warnings:
            lines.append(f"  • {warning}")
        lines.append("")
    
    # Errors
    if answer.errors:
        lines.append("❌ ERRORS")
        lines.append("-" * 40)
        for error in answer.errors:
            lines.append(f"  • {error}")
        lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Process meeting notes and create calendar events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process notes from command line
  python -m app.main --notes "Meeting notes text here..."
  
  # Process notes from file
  python -m app.main --notes-file meeting.txt
  
  # Dry run (don't create calendar event)
  python -m app.main --notes "..." --dry-run
  
  # Output as JSON
  python -m app.main --notes "..." --json
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--notes", "-n",
        help="Meeting notes text"
    )
    input_group.add_argument(
        "--notes-file", "-f",
        type=Path,
        help="Path to file containing meeting notes"
    )
    
    # Options
    parser.add_argument(
        "--calendar-id", "-c",
        default="primary",
        help="Google Calendar ID (default: primary)"
    )
    parser.add_argument(
        "--timezone", "-t",
        default="Europe/Budapest",
        help="Timezone (default: Europe/Budapest)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Don't create calendar event, just extract and validate"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output result as JSON"
    )
    parser.add_argument(
        "--mock-calendar",
        action="store_true",
        help="Use mock calendar (for testing)"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip Ollama model validation"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    settings = get_settings()
    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    
    # Get notes text
    if args.notes:
        notes_text = args.notes
    else:
        try:
            notes_text = args.notes_file.read_text()
        except Exception as e:
            print(f"❌ Failed to read notes file: {e}")
            sys.exit(1)
    
    # Validate Ollama models
    if not args.skip_validation:
        print("🔍 Validating Ollama models...")
        if not validate_ollama_models():
            print("\n💡 Tip: Use --skip-validation to skip this check")
            sys.exit(1)
    
    # Run the agent
    print("\n🚀 Processing meeting notes...\n")
    
    try:
        final_state = run_agent(
            notes_text=notes_text,
            user_timezone=args.timezone,
            calendar_id=args.calendar_id,
            dry_run=args.dry_run,
            use_mock_calendar=args.mock_calendar or args.dry_run,
        )
        
        # Output result
        if args.json:
            if final_state.final_answer:
                output = final_state.final_answer.model_dump(mode="json")
            else:
                output = {"error": "No final answer generated", "errors": final_state.errors}
            print(json.dumps(output, indent=2, default=str))
        else:
            if final_state.final_answer:
                print(format_final_answer(final_state.final_answer))
            else:
                print("❌ No final answer generated")
                for error in final_state.errors:
                    print(f"   Error: {error}")
        
        # Exit with appropriate code
        if final_state.final_answer and final_state.final_answer.success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except OllamaError as e:
        logger.error(f"Ollama error: {e}")
        print(f"\n❌ Ollama error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
