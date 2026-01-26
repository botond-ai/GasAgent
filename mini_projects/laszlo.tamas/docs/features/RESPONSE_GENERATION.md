# Response Generation - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A response generation a workflow végén formázza és finalizálja a választ. Kombinálja a RAG eredményeket, memóriákat, és egyéb tool output-okat egy koherens, citált válaszba.

## Használat

### Response formatting
```python
from services.response_generator import ResponseGenerator

generator = ResponseGenerator()

# Response generálás tool eredményekből
response = await generator.generate_response(
    query="Mi a távmunka szabályzat?",
    rag_results=document_chunks,
    memory_results=user_memories,
    user_context=user_context
)

print(f"Answer: {response.final_answer}")
print(f"Citations: {len(response.sources)}")
```

## Technikai implementáció

### Response Generator
```python
class ResponseGenerator:
    def __init__(self):
        self.llm_client = OpenAI()
        self.citation_formatter = CitationFormatter()
        
    async def generate_response(
        self,
        query: str,
        rag_results: List[DocumentChunk] = None,
        memory_results: List[Memory] = None,
        tool_outputs: Dict[str, Any] = None,
        user_context: UserContext = None
    ) -> GeneratedResponse:
        """Generate final response from all available information."""
        
        # Combine all information sources
        all_sources = []
        context_parts = []
        
        # Process RAG results
        if rag_results:
            for chunk in rag_results:
                context_parts.append(f"[DOC] {chunk.content}")
                all_sources.append(Source(
                    type="document",
                    title=chunk.source_title,
                    content=chunk.content,
                    page=chunk.page_start,
                    similarity_score=chunk.similarity_score
                ))
        
        # Process memory results  
        if memory_results:
            for memory in memory_results:
                context_parts.append(f"[MEM] {memory.content}")
                all_sources.append(Source(
                    type="memory", 
                    content=memory.content,
                    similarity_score=memory.similarity_score
                ))
        
        # Generate response using LLM
        answer = await self._generate_llm_response(
            query=query,
            context_parts=context_parts,
            user_context=user_context
        )
        
        # Format with citations
        formatted_answer = self.citation_formatter.add_citations(
            answer=answer,
            sources=all_sources,
            language=user_context.language if user_context else "en"
        )
        
        return GeneratedResponse(
            final_answer=formatted_answer,
            sources=all_sources,
            response_length=len(formatted_answer),
            source_count=len(all_sources)
        )
    
    async def _generate_llm_response(
        self,
        query: str,
        context_parts: List[str],
        user_context: UserContext
    ) -> str:
        """Generate response using LLM with context."""
        
        language = user_context.language if user_context else "en"
        
        system_prompt = self._build_response_system_prompt(language)
        
        user_prompt = f"""
        User Question: {query}
        
        Available Information:
        {chr(10).join(context_parts[:10])}  # Limit context to avoid token overflow
        
        Generate a comprehensive answer using the provided information.
        """
        
        response = await self.llm_client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        return response.choices[0].message.content.strip()

class CitationFormatter:
    def add_citations(
        self,
        answer: str,
        sources: List[Source],
        language: str = "en"
    ) -> str:
        """Add numbered citations to response."""
        
        if not sources:
            return answer
        
        # Add citations list
        citations_header = "**Források:**" if language == "hu" else "**Sources:**"
        citation_lines = [citations_header]
        
        for i, source in enumerate(sources, 1):
            if source.type == "document":
                line = f"[{i}] {source.title}"
                if source.page:
                    page_text = "oldal" if language == "hu" else "page"
                    line += f" ({page_text} {source.page})"
            else:
                mem_text = "Emlék" if language == "hu" else "Memory"
                line = f"[{i}] {mem_text}"
            
            citation_lines.append(line)
        
        return answer + "\n\n" + "\n".join(citation_lines)
```

## Funkció-specifikus konfiguráció

```ini
# Response generation
MAX_RESPONSE_LENGTH=1000
RESPONSE_TEMPERATURE=0.3
MAX_SOURCES_CITED=5
ENABLE_CITATION_FORMATTING=true

# Language settings
DEFAULT_RESPONSE_LANGUAGE=hu
ENABLE_MULTILINGUAL_RESPONSES=true
```