# Query Processing - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A query processing rendszer optimalizálja és feldolgozza a user queryket mielőtt a workflow futna. Tartalmazza a query rewriting, intent classification, és context enhancement funkciókat.

## Használat

### Query preprocessing
```python
from services.query_processor import QueryProcessor

processor = QueryProcessor()

# Query feldolgozás
result = await processor.process_query(
    original_query="szabályzat távmunka", 
    user_context=user_context,
    session_id="session-123"
)

print(f"Original: {result.original_query}")
print(f"Processed: {result.processed_query}")
print(f"Intent: {result.intent}")
```

## Technikai implementáció

### Query Processing Pipeline
```python
class QueryProcessor:
    def __init__(self):
        self.rewriter = QueryRewriter()
        self.intent_classifier = IntentClassifier()
        self.context_enhancer = ContextEnhancer()
    
    async def process_query(
        self,
        original_query: str,
        user_context: UserContext,
        session_id: Optional[str] = None
    ) -> ProcessedQuery:
        """Complete query processing pipeline."""
        
        # Step 1: Query validation and sanitization
        sanitized_query = self._sanitize_query(original_query)
        
        # Step 2: Context enhancement from session
        context_enhanced_query = await self.context_enhancer.enhance_with_session_context(
            sanitized_query, session_id
        )
        
        # Step 3: Query rewriting if needed
        if self._should_rewrite_query(context_enhanced_query):
            rewritten_query = await self.rewriter.rewrite_query(
                context_enhanced_query, user_context
            )
        else:
            rewritten_query = context_enhanced_query
        
        # Step 4: Intent classification
        intent = await self.intent_classifier.classify(rewritten_query)
        
        return ProcessedQuery(
            original_query=original_query,
            sanitized_query=sanitized_query,
            context_enhanced_query=context_enhanced_query,
            processed_query=rewritten_query,
            intent=intent,
            processing_metadata={
                "rewritten": rewritten_query != original_query,
                "context_enhanced": len(context_enhanced_query) > len(sanitized_query),
                "language": user_context.language
            }
        )

class QueryRewriter:
    async def rewrite_query(
        self,
        query: str,
        user_context: UserContext
    ) -> str:
        """Rewrite query for better processing."""
        
        system_prompt = f"""
        You are a query optimization assistant. Rewrite the user's query to be more specific and searchable.
        
        User language: {user_context.language}
        User context: {user_context.name}
        
        Guidelines:
        - Make vague queries more specific
        - Expand abbreviations
        - Add context if missing
        - Keep the intent unchanged
        - Respond in the same language
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Rewrite this query: {query}"}
            ],
            temperature=0.2,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()

class IntentClassifier:
    def __init__(self):
        self.intents = {
            "document_search": ["szabályzat", "policy", "dokumentum", "kézikönyv"],
            "memory_recall": ["emlék", "remember", "jegyezd meg", "what did I"],
            "general_question": ["mi az", "what is", "hogyan", "how to"],
            "task_request": ["készíts", "create", "generate", "csinálj"]
        }
    
    async def classify(self, query: str) -> str:
        """Simple rule-based intent classification."""
        
        query_lower = query.lower()
        
        for intent, keywords in self.intents.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent
        
        return "general_question"  # Default intent
```

## Funkció-specifikus konfiguráció

```ini
# Query processing
ENABLE_QUERY_REWRITING=true
ENABLE_INTENT_CLASSIFICATION=true
ENABLE_CONTEXT_ENHANCEMENT=true
MAX_QUERY_LENGTH=1000

# Rewriting settings
QUERY_REWRITE_THRESHOLD_WORDS=3
LLM_REWRITE_TIMEOUT_SEC=10
REWRITE_TEMPERATURE=0.2
```