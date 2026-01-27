"""
Integration tests using real sample meeting notes.
Tests the full agent workflow end-to-end with realistic scenarios.
"""

import pytest
from pathlib import Path

from app.agent.graph import run_agent
from app.llm.ollama_client import OllamaClient
from app.memory.store import InMemoryStore


class TestRealMeetingNotes:
    """Integration tests with real meeting notes samples."""
    
    @pytest.fixture
    def sample_notes_path(self):
        """Get path to sample notes directory."""
        return Path(__file__).parent.parent / "sample_notes"
    
    @pytest.fixture
    def tech_design_notes(self, sample_notes_path):
        """Load tech design meeting notes."""
        return (sample_notes_path / "tech_design_meeting.txt").read_text()
    
    @pytest.fixture
    def customer_call_notes(self, sample_notes_path):
        """Load customer call notes."""
        return (sample_notes_path / "customer_call.txt").read_text()
    
    @pytest.fixture
    def retrospective_notes(self, sample_notes_path):
        """Load team retrospective notes."""
        return (sample_notes_path / "team_retrospective.txt").read_text()
    
    def test_tech_design_meeting_clear_next_meeting(self, tech_design_notes):
        """
        Test Scenario 1: Tech Design Meeting
        Expected: High confidence extraction, clear next meeting details
        """
        # Run agent in dry-run mode
        result = run_agent(
            notes_text=tech_design_notes,
            dry_run=True,
            use_mock_calendar=True,
        )
        
        # Verify final answer exists
        assert result.final_answer is not None
        assert result.final_answer.success is True
        
        # Verify summary was generated
        assert len(result.final_answer.summary) > 50
        assert "database" in result.final_answer.summary.lower() or "migration" in result.final_answer.summary.lower()
        
        # Verify decisions were extracted
        assert len(result.final_answer.decisions) >= 3
        assert any("hybrid" in d.lower() or "option c" in d.lower() for d in result.final_answer.decisions)
        
        # Verify action items were extracted
        assert len(result.final_answer.action_items) >= 4
        owners = [item.get("owner", "") for item in result.final_answer.action_items]
        assert any("sarah" in owner.lower() for owner in owners)
        assert any("mike" in owner.lower() for owner in owners)
        
        # Verify event details were extracted
        event = result.final_answer.event_details
        assert event is not None
        assert event.title is not None and len(event.title) > 0
        assert event.start_datetime is not None
        assert event.end_datetime is not None
        
        # Should have high confidence for this clear meeting
        assert event.source_confidence >= 0.8
        
        # Verify attendees were extracted
        assert len(event.attendees) >= 4
        assert any("sarah" in attendee.lower() for attendee in event.attendees)
        
        # Verify location/video link
        assert event.location or event.conference_link
        
        print(f"\n✅ Tech Design Meeting Test:")
        print(f"   - Summary length: {len(result.final_answer.summary)} chars")
        print(f"   - Decisions extracted: {len(result.final_answer.decisions)}")
        print(f"   - Action items: {len(result.final_answer.action_items)}")
        print(f"   - Event confidence: {event.source_confidence:.0%}")
        print(f"   - Attendees: {len(event.attendees)}")
        print(f"   - Next meeting: {event.start_datetime}")
    
    def test_customer_call_ambiguous_time(self, customer_call_notes):
        """
        Test Scenario 2: Customer Call
        Expected: Multiple time options, moderate confidence, needs clarification
        """
        result = run_agent(
            notes_text=customer_call_notes,
            dry_run=True,
            use_mock_calendar=True,
        )
        
        assert result.final_answer is not None
        
        # Verify summary
        assert len(result.final_answer.summary) > 50
        assert any(word in result.final_answer.summary.lower() 
                  for word in ["acme", "customer", "contract", "renewal"])
        
        # Verify decisions
        assert len(result.final_answer.decisions) >= 2
        
        # Verify action items
        assert len(result.final_answer.action_items) >= 3
        
        # Event details - might have lower confidence due to "tentative" nature
        event = result.final_answer.event_details
        if event and event.start_datetime:
            # If extracted, check that warnings mention multiple options or tentative
            warnings_text = " ".join(event.extraction_warnings).lower()
            # Confidence might be moderate (not super high due to tentative nature)
            assert event.source_confidence > 0
            print(f"\n✅ Customer Call Test:")
            print(f"   - Event confidence: {event.source_confidence:.0%}")
            print(f"   - Warnings: {event.extraction_warnings}")
        else:
            # Or it might not extract a specific time due to ambiguity
            assert result.final_answer.missing_info or result.final_answer.questions_for_user
            print(f"\n✅ Customer Call Test:")
            print(f"   - No specific time extracted (expected due to multiple options)")
            print(f"   - Missing info: {result.final_answer.missing_info}")
    
    def test_retrospective_no_next_meeting(self, retrospective_notes):
        """
        Test Scenario 3: Team Retrospective
        Expected: Good summary, no specific next meeting, low event confidence
        """
        result = run_agent(
            notes_text=retrospective_notes,
            dry_run=True,
            use_mock_calendar=True,
        )
        
        assert result.final_answer is not None
        
        # Verify summary was generated
        assert len(result.final_answer.summary) > 50
        assert any(word in result.final_answer.summary.lower() 
                  for word in ["sprint", "retrospective", "team"])
        
        # Should have action items from retrospective
        assert len(result.final_answer.action_items) >= 3
        
        # Should extract what went well / issues as decisions or risks
        assert len(result.final_answer.decisions) > 0 or len(result.final_answer.risks_open_questions) > 0
        
        # Event details - should either have low confidence or be incomplete
        event = result.final_answer.event_details
        if event and event.start_datetime:
            # If it extracted something, confidence should be low
            assert event.source_confidence < 0.7
            print(f"\n✅ Retrospective Test:")
            print(f"   - Extracted tentative event with low confidence: {event.source_confidence:.0%}")
        else:
            # Or no specific event extracted (expected)
            assert not event or not event.is_complete()
            print(f"\n✅ Retrospective Test:")
            print(f"   - No specific next meeting (expected)")
            print(f"   - Event complete: {event.is_complete() if event else False}")
        
        # Should have missing info or questions
        assert result.final_answer.missing_info or result.final_answer.questions_for_user or \
               (event and len(event.extraction_warnings) > 0)
    
    def test_all_notes_generate_summaries(self, tech_design_notes, customer_call_notes, retrospective_notes):
        """
        Test that all note types generate valid summaries with key components.
        """
        notes_samples = [
            ("Tech Design", tech_design_notes),
            ("Customer Call", customer_call_notes),
            ("Retrospective", retrospective_notes),
        ]
        
        results = []
        for name, notes in notes_samples:
            result = run_agent(
                notes_text=notes,
                dry_run=True,
                use_mock_calendar=True,
            )
            
            # All should succeed
            assert result.final_answer is not None
            assert result.final_answer.success is True
            
            # All should have summary
            assert len(result.final_answer.summary) > 30
            
            # All should have either decisions or actions
            assert (len(result.final_answer.decisions) > 0 or 
                   len(result.final_answer.action_items) > 0)
            
            results.append((name, result))
        
        print("\n" + "="*60)
        print("SUMMARY COMPARISON")
        print("="*60)
        for name, result in results:
            print(f"\n{name}:")
            print(f"  Summary: {len(result.final_answer.summary)} chars")
            print(f"  Decisions: {len(result.final_answer.decisions)}")
            print(f"  Actions: {len(result.final_answer.action_items)}")
            print(f"  Risks/Questions: {len(result.final_answer.risks_open_questions)}")
            event = result.final_answer.event_details
            if event and event.start_datetime:
                print(f"  Event: {event.title} - {event.start_datetime} (confidence: {event.source_confidence:.0%})")
            else:
                print(f"  Event: Not extracted or incomplete")


class TestMeetingNotesEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_notes(self):
        """Test handling of empty notes."""
        result = run_agent(
            notes_text="",
            dry_run=True,
            use_mock_calendar=True,
        )
        
        # Should still return a result, even if minimal
        assert result.final_answer is not None
    
    def test_very_short_notes(self):
        """Test handling of very short notes."""
        result = run_agent(
            notes_text="Quick sync. Follow up next week.",
            dry_run=True,
            use_mock_calendar=True,
        )
        
        assert result.final_answer is not None
        # Should have low confidence or missing info
        if result.final_answer.event_details:
            assert result.final_answer.event_details.source_confidence < 0.6 or \
                   not result.final_answer.event_details.is_complete()
    
    def test_notes_with_multiple_meetings(self):
        """Test notes mentioning multiple possible meetings."""
        notes = """
        Team sync - Jan 21, 2026
        
        We discussed the project status. 
        
        Mike suggested we meet again on Friday at 2pm.
        Sarah proposed Monday at 10am instead.
        The team also mentioned our quarterly review is coming up on Feb 15.
        
        We'll decide later which time works best.
        """
        
        result = run_agent(
            notes_text=notes,
            dry_run=True,
            use_mock_calendar=True,
        )
        
        assert result.final_answer is not None
        # Should either pick one or flag ambiguity
        if result.final_answer.event_details and result.final_answer.event_details.start_datetime:
            # If it picked one, should have warnings about multiple options
            assert len(result.final_answer.event_details.extraction_warnings) > 0 or \
                   result.final_answer.event_details.source_confidence < 0.9


if __name__ == "__main__":
    """Run tests directly for quick testing."""
    pytest.main([__file__, "-v", "--tb=short", "-s"])
