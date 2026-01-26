"""
Test fixtures for the meeting notes agent.
Contains sample meeting notes for testing.
"""

# Sample 1: Clear next meeting with all details
SAMPLE_NOTES_CLEAR = """
Product Review Meeting - January 15, 2026

Participants: Alice (PM), Bob (Dev Lead), Carol (Design), David (QA)

Agenda:
1. Sprint 23 Review
2. Feature prioritization
3. Timeline discussion

DISCUSSION NOTES:

Alice opened the meeting by reviewing Sprint 23 deliverables. The authentication module 
is complete and passed QA. The dashboard redesign is 80% done.

Bob mentioned the API refactoring is ahead of schedule. He proposes moving the deadline 
from Feb 1 to Jan 25.

DECISIONS:
- We will release v2.1 on January 28th
- The new pricing page will be postponed to v2.2
- Carol will lead the mobile redesign initiative

ACTION ITEMS:
- Alice: Prepare release notes by Jan 24
- Bob: Finalize API documentation by Jan 22
- Carol: Create mobile wireframes by Jan 20
- David: Complete regression testing by Jan 26

OPEN QUESTIONS:
- Do we need additional load testing before release?
- Should we involve marketing earlier in the process?

NEXT MEETING:
The next sprint planning will be on Tuesday, January 20, 2026 at 10:00 AM.
Location: Conference Room B
Duration: 1 hour
Attendees: alice@company.com, bob@company.com, carol@company.com, david@company.com
Agenda: Sprint 24 planning and v2.2 scope discussion

Video link: https://meet.google.com/abc-defg-hij
"""

# Sample 2: Ambiguous next meeting
SAMPLE_NOTES_AMBIGUOUS = """
Weekly Sync - January 16, 2026

Team: Engineering

Quick sync to discuss ongoing work.

Updates:
- Backend team is working on the new caching layer
- Frontend is blocked on API specs
- DevOps completed the Kubernetes migration

Issues raised:
- We need more clarity on the Q1 roadmap
- The testing environment is unstable
- Documentation is falling behind

Decisions:
- Sarah will reach out to product about roadmap
- Mike will investigate test env issues
- Everyone should document their work better

Next steps:
- Sarah: talk to product by end of week
- Mike: file infrastructure ticket
- Team: update wiki pages

We should meet again sometime next week to follow up on these items.
Maybe Tuesday or Wednesday afternoon would work.
"""

# Sample 3: No next meeting mentioned
SAMPLE_NOTES_NO_MEETING = """
Architecture Review - January 14, 2026

Present: Tech leads from all teams

Topic: Microservices migration strategy

Summary:
We reviewed the current monolith architecture and discussed the path forward.
The team agreed that a gradual migration approach is best.

Key points:
- Start with the user service
- Implement API gateway first
- Keep the database monolithic for now
- Plan for 6-month migration timeline

Decisions:
- Approved microservices migration project
- Budget allocated for additional cloud resources
- New DevOps hire approved

Risks:
- Timeline may slip if we hit unexpected dependencies
- Team needs training on Kubernetes
- Data migration could be complex

No follow-up meeting scheduled - will coordinate via Slack.
"""

# Sample 4: Multiple potential meeting times
SAMPLE_NOTES_MULTIPLE_TIMES = """
Client Meeting Notes - January 17, 2026

Client: Acme Corp
Our team: Sales (John), Engineering (Mary), Support (Tom)

Discussion:
- Client wants to renew contract
- Requesting additional features
- Timeline concerns for Q2 delivery

Client mentioned several possible times for the next meeting:
- Option 1: January 22 at 2 PM
- Option 2: January 23 at 11 AM  
- Option 3: January 24 at 3 PM

They prefer Option 2 but need to confirm with their CTO.

Action items:
- John: Send contract renewal proposal by Monday
- Mary: Provide technical feasibility assessment
- Tom: Prepare support SLA options

We're tentatively planning for January 23 at 11 AM pending confirmation.
Meeting will be via Zoom: https://zoom.us/j/123456789
Duration: approximately 90 minutes
"""
