-- Migration 006: Add TOC and page metadata to document_chunks
-- Purpose: Enable context-aware chunking with chapter names and page tracking
-- Date: 2026-01-19

-- Rename existing columns for clarity
ALTER TABLE document_chunks 
    RENAME COLUMN source_page_from TO page_start;

ALTER TABLE document_chunks 
    RENAME COLUMN source_page_to TO page_end;

ALTER TABLE document_chunks 
    RENAME COLUMN source_section TO chapter_name;

-- Add new column for section hierarchy level
ALTER TABLE document_chunks 
    ADD COLUMN IF NOT EXISTS section_level INTEGER DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN document_chunks.chapter_name IS 'Chapter or section name from TOC (e.g., "2. Elméleti háttér")';
COMMENT ON COLUMN document_chunks.page_start IS 'Starting page number in source document';
COMMENT ON COLUMN document_chunks.page_end IS 'Ending page number in source document';
COMMENT ON COLUMN document_chunks.section_level IS 'Hierarchy level (1=H1/Chapter, 2=H2/Section, etc.)';

-- Create index for filtering by chapter
CREATE INDEX IF NOT EXISTS idx_document_chunks_chapter 
    ON document_chunks(document_id, chapter_name);

-- Create index for page range queries
CREATE INDEX IF NOT EXISTS idx_document_chunks_pages 
    ON document_chunks(document_id, page_start, page_end);
