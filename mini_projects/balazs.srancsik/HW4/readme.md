This folder contains a modified version of the AI Chat sample which I've been previously working on. 

📰 This version remarkably changes the flow of different tools, rather than using a tool router, it forces a predefined sequence of tools in a particular order. It connects to a local SQLite database, stores the data there, attachments are saved to PCloud online storage, user is notified via GMail's IMAP once a new ticket is created.

The tool will perform the following steps:
1. ❓ Understand the user's issue - Documents tool
2. 😊 Run a sentiment analysis on your message - Sentiment analysis tool
3. 🌐 Will respond to user's question in his/her own language - Translator tool
   ☀️ Weather tool is also used to get the current weather and use it for small talk start of the conversation - Weather tool
4. 📖 Provide user with information based on the available knowledge base - Documents tool
5. 🏷️ Classify the urgency of the request - Documents tool
6. ⏰ Commit deadline till when the issue will get solved - Documents tool
7. 💰 Calculate the cost involved and convert to other currencies - Documents tool + FX_rates tool
8. 🏗️ Structure the conversation data - JSON_creator tool
9. 💾 Store the chat history and shared documents - SQLite_save tool + Photo_upload tool
10. 📧 Forward the issue to the team - Email_tool
11. 📊 Create dashboard to report the saved tickets - Dashboard

⚙️ Forced sequence of tools:

  User Message
     │
     ▼
┌─────────────────────┐
│ Detect Support Issue│ ◄── Keyword matching + short message detection
└──────────┬──────────┘
           │ YES
           ▼
┌─────────────────────┐
│ 1. Translator       │ ◄── Translate to English if needed
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. Sentiment        │ ◄── Analyze emotional tone
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. Weather          │ ◄── Get weather for greeting
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. Documents (RAG)  │ ◄── Identify issue type from knowledge base
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 5. FX Rates USD→EUR │ ◄── Convert cost to EUR
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 6. FX Rates USD→HUF │ ◄── Convert cost to HUF
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 7. Final Response   │ ◄── Generate warm, helpful response, in the user's language
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 8. JSON Creator     │ ◄── Create structured ticket
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 9. Photo Upload     │ ◄── Upload attachments to pCloud (if any)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 10. SQLite Save     │ ◄── Save ticket to database
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 11. Email Send      │ ◄── Notify team via email
└──────────┴──────────┘
           ▼
┌─────────────────────┐
│ 12. Dashboard       │ ◄── Create dashboard to report saved tickets
└──────────┴──────────┘

📈 Entire Langraph description and details can be found in the langraph.md file
🧪 Pytest, Unit test, Pydentic API test scripts and test reports have been added into Test_Scripts_And_Logs folder

📊 **Prometheus & Grafana Monitoring**

The application includes comprehensive monitoring with Prometheus and Grafana:

**Access URLs:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin / supportai123)

**Metrics Tracked:**
- 🎫 Ticket statistics (total, by priority, sentiment, issue type)
- 💰 Cost analytics (OpenAI API costs, ticket costs to customers)
- 🔧 Tool performance (invocations, execution time, success rate)
- 📡 HTTP request metrics (rate, latency, status codes)
- 🌐 Language & sentiment distribution
- 🔢 Token usage tracking

**Dashboard Sections:**
1. Overview - Key metrics at a glance
2. Ticket Analytics - Priority, sentiment, issue type distribution
3. Tool Performance - Invocations, execution time, success rates
4. Cost Analytics - OpenAI costs, token usage, ticket costs
5. Language & Sentiment - Message languages, translations
6. HTTP Requests - Request rates, latencies, status codes

**To start monitoring:**
```bash
cd Application
docker-compose up -d
```

Screenshots of the application can be beside this readme file:
  1. Chat Window
  2. Chat Response
  3. Quick View into similar issues
  4. View Tickets/Dashboard
  5. PCloud Storage
  6. Email Notification
  7. Pytest Selenium test results
  8. Unit test results
  9. Pydentic API test results
  10. Prometheus Metrics
  11. Grafana Dashboard


