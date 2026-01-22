# Jira Integration for RAG System

## Overview

The RAG system intelligently suggests creating Jira tasks when appropriate. After answering your question, the system evaluates whether the issue warrants a Jira ticket and offers to create one for you.

**Smart Workflow:**
1. User asks any question → System generates answer
2. LLM evaluates if a Jira ticket would be helpful
3. If yes, system offers: "Would you like to create a Jira ticket?"
4. User accepts/declines → Ticket created automatically with smart defaults

## Setup

### 1. Generate Jira API Token

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a name (e.g., "RAG System Integration")
4. Copy the generated token

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Jira Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_jira_api_token_here

# Optional: Custom department mapping
JIRA_DEPARTMENT_MAPPING=hr:HR,dev:DEV,support:SUP,management:MGT
```

**Important:** All three settings (BASE_URL, EMAIL, API_TOKEN) must be provided for Jira integration to be enabled.

### 3. Set Up Jira Projects

Ensure you have Jira projects created for each department:
- **HR** - HR project key (e.g., "HR")
- **DEV** - Development project key (e.g., "DEV")
- **SUP** - Support project key (e.g., "SUP")
- **MGT** - Management project key (e.g., "MGT")

Update `JIRA_DEPARTMENT_MAPPING` if your project keys differ.

## Usage Examples

### Example 1: Bug Report

```
User: "The authentication system keeps timing out after 5 minutes"

🤖 GENERATED ANSWER:
Based on the system documentation, the authentication timeout is configured
to 30 minutes by default. A 5-minute timeout suggests a misconfiguration
or a bug in the session management...

============================================================
📋 JIRA TICKET SUGGESTION
============================================================
Reason: User reports a system bug that requires investigation
Suggested Department: DEV
Suggested Priority: High
Suggested Summary: Authentication system timing out after 5 minutes...
============================================================

Would you like to create a Jira ticket? (yes/no): yes

Creating Jira ticket...

============================================================
✓ JIRA TICKET CREATED SUCCESSFULLY!
============================================================
Task Key: DEV-456
View at: https://your-company.atlassian.net/browse/DEV-456
============================================================
```

### Example 2: Feature Request

```
User: "It would be great if we could export reports to PDF"

🤖 GENERATED ANSWER:
Currently, the system supports CSV and Excel export formats. PDF export
is not available but could be a valuable addition...

============================================================
📋 JIRA TICKET SUGGESTION
============================================================
Reason: User suggests a feature enhancement
Suggested Department: DEV
Suggested Priority: Medium
Suggested Summary: Add PDF export functionality for reports...
============================================================

Would you like to create a Jira ticket? (yes/no): yes
```

### Example 3: No Ticket Needed

```
User: "What is the vacation policy?"

🤖 GENERATED ANSWER:
Full-time employees receive 20 days of paid vacation annually...

[No Jira suggestion - informational query with complete answer]
```

## When Tickets Are Suggested

The LLM suggests tickets for:

✅ **Bug Reports** - "The login page is broken"
✅ **Feature Requests** - "We need a dark mode"
✅ **Issues** - "The API is too slow"
✅ **Improvements** - "The UI could be more intuitive"
✅ **Investigations** - "Why is the database query failing?"

The LLM does NOT suggest tickets for:

❌ **Informational Queries** - "What is the vacation policy?"
❌ **Complete Answers** - Questions with no action needed
❌ **General Knowledge** - "How does OAuth work?"

## Automatic Detail Extraction

When a ticket is suggested, the system automatically determines:

- **Department**: hr, dev, support, or management
- **Summary**: Concise title (generated from query)
- **Description**: Includes user query and context
- **Priority**: High, Medium, or Low

All fields can be reviewed before confirmation.

## Architecture

### Graph Flow

The LangGraph handles the entire multi-turn Jira workflow:

```
START → preprocess → detect_jira_confirmation
                            ↓
              [Has pending suggestion?]
                YES ↓              NO ↓
          [User said yes/no?]    Continue RAG
            ↙        ↓      ↘         ↓
    YES: create  NO: skip  NEW: RAG  embed → retrieve
         ↓           ↓       ↓               ↓
       format     format   generate    build_context
                              ↓               ↓
                       evaluate_jira      generate
                              ↓               ↓
                          format        evaluate_jira
                                             ↓
                                          format
                                             ↓
                                           END
```

**Key Feature:** The graph itself detects "yes/no" responses to pending Jira suggestions and routes accordingly. No CLI interaction code needed!

### Nodes

1. **detect_jira_confirmation_node** - Detects if query is "yes/no" to pending suggestion
2. **generate_answer_node** - Generates answer with RAG
3. **evaluate_jira_need_node** - LLM evaluates if ticket would help
4. **format_response_node** - Appends Jira offer to answer if suggested
5. **create_jira_task_node** - Creates ticket via API (triggered by "yes")

### State Fields

```python
# Multi-turn state (persists across queries)
pending_jira_suggestion: dict     # Previous suggestion waiting for confirmation
conversation_history: list        # Previous messages for context

# Confirmation detection
jira_confirmation_detected: bool  # True if query is yes/no response
create_jira_task: bool           # True if user confirmed with "yes"

# Suggestion phase
jira_suggested: bool              # True if ticket should be offered
jira_suggestion_reason: str       # Why ticket is/isn't suggested
jira_department: str              # Suggested department
jira_summary: str                 # Suggested title
jira_description: str             # Suggested description
jira_priority: str                # Suggested priority

# Creation phase (after confirmation)
jira_task_key: str                # Created task key (e.g., "HR-123")
jira_task_url: str                # Full task URL
```

### How It Works

**Turn 1:**
1. User asks question about an issue
2. Graph generates answer using RAG
3. evaluate_jira_need_node determines ticket would help
4. format_response_node appends Jira offer to answer
5. System stores pending suggestion in app._pending_jira_suggestion

**Turn 2:**
1. User replies "yes" or "no"
2. Graph receives pending_jira_suggestion in initial state
3. detect_jira_confirmation_node detects yes/no response
4. If "yes": routes to create_jira_task_node → creates ticket → formats success message
5. If "no": routes to format → returns "Okay, I won't create a ticket"
6. If neither: treats as new query → normal RAG flow

**Multi-turn Example:**
```
Turn 1:
User: "The authentication times out after 5 minutes"
Bot: "[Answer about auth]...

📋 Jira Ticket Suggestion
I can create a Jira ticket for this issue:
- Department: DEV
- Priority: High
- Summary: Authentication system timing out...

Would you like me to create this ticket? (Reply 'yes' or 'no')"

Turn 2:
User: "yes"
Bot: "✓ Jira ticket created successfully!
Task Key: DEV-456
View at: https://..."

Turn 3:
User: "What's the vacation policy?"
Bot: "[Normal RAG answer about vacation]"
```

## Evaluation Prompt

The system uses this criteria to evaluate if a ticket should be suggested:

```
A ticket should be suggested if:
- User reports a problem, bug, or issue
- User requests a new feature or enhancement
- User suggests an improvement
- User describes something that needs investigation
- The answer indicates something should be fixed

A ticket should NOT be suggested for:
- Simple informational questions
- Questions with complete answers that require no action
- General knowledge queries
```

## Department Routing

The LLM automatically determines the appropriate department:

- **hr** → HR project (vacation, benefits, policies)
- **dev** → DEV project (bugs, features, technical issues)
- **support** → SUP project (user support, help requests)
- **management** → MGT project (process improvements, strategic)

Default: `support`

## Priority Assignment

The LLM assigns priority based on severity:

- **High** - Critical bugs, security issues, urgent matters
- **Medium** - Standard features, non-urgent bugs
- **Low** - Nice-to-have improvements, minor issues

Default: `Medium`

## Troubleshooting

### "Jira integration not configured"

**Cause:** Missing environment variables

**Solution:** Ensure `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` are all set in `.env`

### No tickets are being suggested

**Cause:** Jira config might be missing OR queries don't warrant tickets

**Solution:**
1. Check Jira credentials are configured
2. Try a clear bug report: "The login button is broken"
3. Check logs for evaluation errors

### "No Jira project for department"

**Cause:** Department not mapped to a project

**Solution:** Update `JIRA_DEPARTMENT_MAPPING` with correct project keys

### "Jira API error: 401 Unauthorized"

**Cause:** Invalid credentials or expired API token

**Solution:**
1. Verify email matches your Jira account
2. Regenerate API token if expired
3. Check token is copied correctly (no extra spaces)

### LLM suggests tickets too often

**Cause:** Evaluation prompt may need tuning

**Solution:** Edit the evaluation prompt in `scripts/graph/nodes/jira_evaluate.py` to be more restrictive

### LLM never suggests tickets

**Cause:** Evaluation prompt may be too restrictive OR LLM temperature too low

**Solution:**
1. Try more explicit bug reports
2. Check LLM temperature in config (0.7 recommended)
3. Review evaluation logs for reasoning

## Security Notes

- **API Token Security**: Never commit `.env` file to git. The token grants full access to your Jira account.
- **Permission Scope**: The token has the same permissions as your user account. Use a dedicated service account for production.
- **HTTPS Only**: Ensure `JIRA_BASE_URL` uses HTTPS.
- **Data Privacy**: User queries and answers are included in ticket descriptions. Ensure no sensitive data is leaked.

## Benefits of This Approach

**Graph-Native**: Entire workflow handled by LangGraph - no CLI interaction code
**Conversational**: Natural multi-turn dialog ("yes"/"no" responses)
**Proactive**: System suggests tickets without user explicitly requesting
**Smart**: LLM decides when tickets are appropriate
**User Control**: User always confirms before creation
**Context-Rich**: Tickets include full query and answer context
**Zero Friction**: No manual copy-paste or switching to Jira UI
**Stateful**: Conversation history and pending suggestions persist across turns

## Future Enhancements

Potential improvements:
- **Custom Fields**: Support project-specific custom fields
- **Assignee Support**: Auto-assign to appropriate team members
- **Issue Linking**: Link related Jira issues
- **Attachments**: Include retrieved document chunks as attachments
- **Issue Types**: Support Bug, Story, Epic (currently only Task)
- **Watchers**: Auto-add stakeholders
- **Labels/Components**: Tag with relevant labels
- **Edit Before Creation**: Allow user to modify details before creating

## API Reference

### Jira REST API v3

The integration uses Jira Cloud REST API v3:
- **Endpoint**: `POST /rest/api/3/issue`
- **Authentication**: Basic Auth (email:token)
- **Documentation**: [Atlassian Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

### Rate Limits

Jira Cloud API has rate limits:
- ~10,000 requests per hour for standard plans
- Each query triggers 1 evaluation (no API call) + 1 creation (if confirmed)
- Evaluation uses OpenAI API only
