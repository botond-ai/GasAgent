# Debug Guide - Jira Integration & Conversation History

## What to Look For

I've added extensive logging to help debug the issues you're experiencing. When you run the system, you'll see debug output showing:

### 1. Conversation History
Look for these log messages:
```
INFO - scripts.graph.nodes.generation - ===== Generate Answer node executing =====
INFO - scripts.graph.nodes.generation - Conversation history length: X
INFO - scripts.graph.nodes.generation - Updated conversation history: Y messages
INFO - scripts.application - ===== Application: Updated conversation history: Z messages =====
```

**What this tells you:**
- How many messages are in the history when generating
- Whether the history is being updated after each turn
- Whether the history is being saved in the application

### 2. Jira Evaluation
Look for these log messages:
```
INFO - scripts.graph.nodes.jira_evaluate - ===== Evaluate Jira Need node executing =====
INFO - scripts.graph.nodes.jira_evaluate - Query: ...
INFO - scripts.graph.nodes.jira_evaluate - Answer: ...
INFO - scripts.graph.nodes.jira_evaluate - Jira ticket suggested: ...
```

**What this tells you:**
- Whether the evaluation node is running
- What query/answer it's evaluating
- Whether it decided to suggest a ticket

### 3. Jira Suggestion in Response
Look for these log messages:
```
INFO - scripts.graph.nodes.response - ===== Format Response: jira_suggested=True =====
INFO - scripts.graph.nodes.response - Appending Jira offer: dept=DEV, priority=High
INFO - scripts.graph.nodes.response - Successfully appended Jira suggestion to answer
```

**What this tells you:**
- Whether the format node sees the Jira suggestion
- What department/priority was detected
- Whether the offer was added to the answer

### 4. DEBUG Output
At the end of each query, you'll see:
```
[DEBUG] jira_suggested: True/False
[DEBUG] conversation_history length: X
[DEBUG] pending_jira_suggestion: {...}
```

**What this tells you:**
- Whether a Jira ticket was suggested this turn
- How many messages are in the conversation history
- Whether there's a pending suggestion waiting for confirmation

## Common Issues & Solutions

### Issue 1: Jira Offer Not Showing

**Symptoms:**
- `[DEBUG] jira_suggested: False` even after reporting an issue
- No Jira offer in the generated answer

**Possible causes:**
1. **Evaluation node not running** - Look for "===== Evaluate Jira Need node executing ====="
   - If missing: Check if the graph is calling evaluate_jira node

2. **LLM deciding no ticket needed** - Look for the LLM's reasoning in logs
   - The LLM might be too conservative
   - Try a clearer bug report: "The login button is completely broken"

3. **Evaluation failing** - Look for "ERROR" messages
   - Check if LLM API is working
   - Check if the evaluation prompt is returning valid JSON

**Debug steps:**
1. Run the app: `python -m scripts.main`
2. Ask: "The authentication system is broken and users can't log in"
3. Check logs for "===== Evaluate Jira Need node executing ====="
4. Check if `jira_suggested: True` in DEBUG output
5. Check if "Appending Jira offer" appears in logs

### Issue 2: Conversation History Not Preserved

**Symptoms:**
- `[DEBUG] conversation_history length: 0` on second turn
- Bot doesn't remember previous conversation

**Possible causes:**
1. **History not being updated** - Look for "Updated conversation history: X messages"
   - If X doesn't increase: Generation node isn't updating history

2. **History not being saved** - Look for "Application: Updated conversation history"
   - If appears but length is 0 on next turn: Application isn't saving it

3. **History not being passed** - Check initial state setup
   - Verify `pending_jira_suggestion` and `conversation_history` are in initial state

**Debug steps:**
1. Run the app
2. First query: "What is the vacation policy?"
3. Check: "Updated conversation history: 2 messages" (user + assistant)
4. Second query: "How many days do I get?"
5. Check: "Conversation history length: 2" (should show previous messages)

### Issue 3: Jira Confirmation Not Working

**Symptoms:**
- Say "yes" but ticket isn't created
- Bot treats "yes" as a new query

**Possible causes:**
1. **No pending suggestion** - Look for `pending_jira_suggestion: None`
   - If None when you say "yes": Previous turn didn't suggest a ticket

2. **Confirmation not detected** - Look for "User confirmed Jira ticket creation"
   - If missing: Confirmation detection node isn't recognizing "yes"

3. **Jira not configured** - Look for "Jira integration not configured"
   - Check .env file has JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

## Test Scenario

Run this exact sequence and share the logs:

**Turn 1:**
```
User: "The deployment process fails with permission errors"
```
Expected logs:
- ✅ "Evaluate Jira Need node executing"
- ✅ "jira_suggested: True"
- ✅ "Appending Jira offer"
- ✅ "pending_jira_suggestion: {dept: ...}"

**Turn 2:**
```
User: "yes"
```
Expected logs:
- ✅ "User confirmed Jira ticket creation"
- ✅ "Create Jira Task node executing" OR "Jira integration not configured"
- ✅ "Jira task created: XXX-123" OR error message

**Turn 3:**
```
User: "What was the error again?"
```
Expected logs:
- ✅ "Conversation history length: 4" (turn 1 user+assistant, turn 2 user+assistant)
- ✅ Answer should reference "deployment process" and "permission errors"

## Share Your Logs

When reporting issues, please share:
1. The complete terminal output with all log messages
2. The `[DEBUG]` lines at the end of each turn
3. Which turn/query isn't working as expected

This will help identify exactly where the issue is in the graph flow.
