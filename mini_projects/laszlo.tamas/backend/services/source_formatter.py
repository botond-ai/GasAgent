"""
Helper utility for formatting RAG responses with source citations.

Provides functions to format retrieved chunks with chapter names and page numbers
for citation in LLM responses.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def format_sources_with_citations(chunks: List[Dict[str, Any]]) -> str:
    """
    Format document chunks into citation-friendly text.
    
    Args:
        chunks: List of chunk dictionaries with metadata (chapter_name, page_start, page_end)
    
    Returns:
        Formatted source citations string
        
    Example output:
        📚 Források:
        - 2. Elméleti háttér (23-31. oldal)
        - 4.2 Kísérletek (45-48. oldal)
    """
    if not chunks:
        return ""
    
    sources = []
    seen = set()  # Deduplicate by (chapter, pages)
    
    for chunk in chunks:
        chapter_name = chunk.get("chapter_name")
        page_start = chunk.get("page_start")
        page_end = chunk.get("page_end")
        
        # Build source citation
        if chapter_name and page_start:
            if page_end and page_end != page_start:
                source = f"{chapter_name} ({page_start}-{page_end}. oldal)"
            else:
                source = f"{chapter_name} ({page_start}. oldal)"
            
            # Deduplicate
            key = (chapter_name, page_start, page_end)
            if key not in seen:
                sources.append(source)
                seen.add(key)
        elif chapter_name:
            # Fallback: chapter without page numbers
            if chapter_name not in seen:
                sources.append(chapter_name)
                seen.add(chapter_name)
    
    if not sources:
        return ""
    
    return "\n\n📚 Források:\n" + "\n".join(f"- {s}" for s in sources)


def enrich_answer_with_sources(answer: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Append formatted source citations to LLM answer.
    
    Args:
        answer: Generated LLM response
        chunks: Retrieved document chunks with metadata
    
    Returns:
        Answer with appended source citations
    """
    citations = format_sources_with_citations(chunks)
    
    if citations:
        return answer + citations
    else:
        return answer


def build_context_with_metadata(chunks: List[Dict[str, Any]], max_length: int = 4000) -> str:
    """
    Build LLM context from chunks with chapter/page metadata inline.
    
    Includes chapter and page information in the context to help LLM
    understand document structure.
    
    Args:
        chunks: List of chunk dictionaries
        max_length: Maximum total characters
    
    Returns:
        Formatted context string for LLM prompt
        
    Example output:
        [Forrás: 2. Elméleti háttér, 23-31. oldal]
        Az elméleti háttér szerint...
        
        [Forrás: 3. Módszertan, 35. oldal]
        A kísérlet során...
    """
    context_parts = []
    current_length = 0
    
    for idx, chunk in enumerate(chunks, 1):
        content = chunk.get("content", "")
        chapter = chunk.get("chapter_name", "Ismeretlen")
        page_start = chunk.get("page_start")
        page_end = chunk.get("page_end")
        
        # Build source label
        if page_start:
            if page_end and page_end != page_start:
                source_label = f"[Forrás: {chapter}, {page_start}-{page_end}. oldal]"
            else:
                source_label = f"[Forrás: {chapter}, {page_start}. oldal]"
        else:
            source_label = f"[Forrás: {chapter}]"
        
        chunk_text = f"{source_label}\n{content}\n"
        
        # Check length limit
        if current_length + len(chunk_text) > max_length:
            logger.info(f"Context length limit reached at chunk {idx}/{len(chunks)}")
            break
        
        context_parts.append(chunk_text)
        current_length += len(chunk_text)
    
    return "\n".join(context_parts)
