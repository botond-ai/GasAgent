# Document Processing - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A dokumentum feldolgozó rendszer feltöltött fájlokat intelligensen darabolja, indexeli és kereshetővé teszi. Támogatja a PDF, DOCX, TXT formátumokat, és automatikusan kivonatolja a metadata-t (címek, fejezetek, oldalszámok).

## Használat

### Dokumentum feltöltés és feldolgozás
```python
# Dokumentum feltöltés API-n keresztül
import requests

# Fájl feltöltés
with open("szabalyzat.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/workflows/document-processing",
        files={"file": f},
        data={
            "tenant_id": 1,
            "user_id": 1,
            "visibility": "tenant"  # vagy "private"
        }
    )

result = response.json()
print(f"Dokumentum ID: {result['document_id']}")
print(f"Chunks létrehozva: {result['chunks_created']}")
```

### Programmatic document processing
```python
# Backend service közvetlen használata
from services.document_processing_service import DocumentProcessingService

processor = DocumentProcessingService()

# Dokumentum feldolgozás
result = await processor.process_document(
    file_content=pdf_bytes,
    filename="policy_manual.pdf",
    tenant_id=1,
    user_id=1,
    visibility="tenant"
)

print(f"Document chunks: {len(result.chunks)}")
for chunk in result.chunks:
    print(f"  - Chapter: {chunk.chapter_name}")
    print(f"  - Pages: {chunk.page_start}-{chunk.page_end}")
```

### Batch document processing
```python
# Több dokumentum feldolgozása
documents = [
    ("hr_manual.pdf", pdf_content_1),
    ("it_policy.docx", docx_content_2),
    ("safety_rules.txt", txt_content_3)
]

results = []
for filename, content in documents:
    result = await processor.process_document(
        file_content=content,
        filename=filename,
        tenant_id=1,
        visibility="tenant"
    )
    results.append(result)

print(f"Processed {len(results)} documents")
print(f"Total chunks: {sum(len(r.chunks) for r in results)}")
```

## Technikai implementáció

### Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                   DOCUMENT UPLOAD & VALIDATION                 │
│  • File type detection and validation                          │
│  • Size and security checks                                    │
│  • Tenant/user authorization                                   │
│  • Virus scanning (if configured)                              │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TEXT EXTRACTION                              │
│  • PDF text extraction (pypdf, pdfplumber)                     │
│  • DOCX content extraction (python-docx)                       │
│  • Plain text processing                                       │  
│  • OCR for scanned documents (optional)                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    METADATA EXTRACTION                          │
│  • Document structure analysis (headers, TOC)                  │
│  • Page number mapping                                         │
│  • Chapter/section detection                                   │
│  • Semantic structure inference                                │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT CHUNKING                         │
│  • Semantic boundary detection                                 │
│  • Respect paragraph/section boundaries                        │
│  • Maintain context overlap between chunks                     │
│  • Preserve metadata in each chunk                             │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EMBEDDING GENERATION                         │
│  • OpenAI text-embedding-3-large                               │
│  • Batch processing for efficiency                             │
│  • Error handling and retry logic                              │
│  • Embedding quality validation                                │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL STORAGE PERSISTENCE                     │
│  • PostgreSQL: Document & chunk metadata                       │
│  • Qdrant: Vector embeddings for semantic search              │
│  • Transactional consistency between stores                    │
│  • Tenant isolation at storage level                           │
└─────────────────────────────────────────────────────────────────┘
```

### Document Processing Service

#### Core Processing Service
```python
class DocumentProcessingService:
    def __init__(self):
        self.text_extractors = {
            '.pdf': PDFTextExtractor(),
            '.docx': DOCXTextExtractor(),
            '.txt': PlainTextExtractor()
        }
        self.chunker = IntelligentChunker()
        self.embedder = OpenAIEmbedder()
        self.db = PostgreSQLDocumentStore()
        self.vector_store = QdrantVectorStore()
    
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        visibility: str = "tenant"
    ) -> DocumentProcessingResult:
        """
        Complete document processing pipeline.
        
        Args:
            file_content: Binary file content
            filename: Original filename with extension
            tenant_id: Tenant for isolation
            user_id: User for private documents (None for tenant-wide)
            visibility: "private" or "tenant"
            
        Returns:
            DocumentProcessingResult with document ID and chunk information
        """
        
        # Input validation
        self._validate_document_input(
            file_content, filename, tenant_id, user_id, visibility
        )
        
        # File type detection
        file_extension = Path(filename).suffix.lower()
        if file_extension not in self.text_extractors:
            raise UnsupportedFileTypeError(f"Unsupported file type: {file_extension}")
        
        try:
            # Step 1: Text extraction
            extraction_result = await self._extract_text_with_metadata(
                file_content, filename, file_extension
            )
            
            # Step 2: Create document record
            document_id = await self._create_document_record(
                filename=filename,
                content=extraction_result.full_text,
                tenant_id=tenant_id,
                user_id=user_id,
                visibility=visibility,
                metadata=extraction_result.metadata
            )
            
            # Step 3: Intelligent chunking
            chunks = await self._create_semantic_chunks(
                text=extraction_result.full_text,
                document_id=document_id,
                tenant_id=tenant_id,
                metadata=extraction_result.metadata
            )
            
            # Step 4: Generate embeddings and store
            await self._process_chunks_with_embeddings(chunks, document_id)
            
            return DocumentProcessingResult(
                document_id=document_id,
                filename=filename,
                chunks_created=len(chunks),
                total_characters=len(extraction_result.full_text),
                processing_time_ms=int(time.time() * 1000) - start_time,
                extraction_metadata=extraction_result.metadata
            )
            
        except Exception as e:
            # Cleanup on failure
            if 'document_id' in locals():
                await self._cleanup_failed_processing(document_id)
            raise DocumentProcessingError(f"Document processing failed: {str(e)}")
```

#### Text Extraction Implementations

**PDF Text Extractor:**
```python
class PDFTextExtractor:
    def __init__(self):
        self.fallback_extractors = [
            self._extract_with_pypdf,
            self._extract_with_pdfplumber,
            self._extract_with_ocr  # Only if OCR is configured
        ]
    
    async def extract(self, pdf_content: bytes, filename: str) -> TextExtractionResult:
        """Extract text from PDF with multiple fallback strategies."""
        
        # Try extractors in order of preference
        for extractor in self.fallback_extractors:
            try:
                result = await extractor(pdf_content)
                if result.full_text.strip():  # Successfully extracted text
                    return result
            except Exception as e:
                log_warning(f"PDF extraction method failed: {extractor.__name__}", error=str(e))
                continue
        
        raise TextExtractionError("All PDF extraction methods failed")
    
    async def _extract_with_pypdf(self, pdf_content: bytes) -> TextExtractionResult:
        """Extract using PyPDF library (fastest, basic)."""
        
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        
        full_text = ""
        page_texts = {}
        toc_structure = []
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            full_text += page_text + "\n"
            page_texts[page_num + 1] = page_text
            
            # Extract headings (basic heuristic)
            headings = self._extract_headings_from_page(page_text)
            for heading in headings:
                toc_structure.append({
                    'title': heading,
                    'page': page_num + 1,
                    'level': self._infer_heading_level(heading)
                })
        
        return TextExtractionResult(
            full_text=full_text,
            page_texts=page_texts,
            toc_structure=toc_structure,
            metadata={
                'total_pages': len(pdf_reader.pages),
                'extraction_method': 'pypdf',
                'has_toc': bool(toc_structure)
            }
        )
    
    async def _extract_with_pdfplumber(self, pdf_content: bytes) -> TextExtractionResult:
        """Extract using pdfplumber (better layout preservation)."""
        
        import pdfplumber
        
        full_text = ""
        page_texts = {}
        tables = []
        
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text with layout preservation
                page_text = page.extract_text(layout=True)
                if page_text:
                    full_text += page_text + "\n"
                    page_texts[page_num] = page_text
                
                # Extract tables
                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append({
                        'page': page_num,
                        'data': table,
                        'bbox': None  # Could extract bounding box if needed
                    })
        
        return TextExtractionResult(
            full_text=full_text,
            page_texts=page_texts,
            tables=tables,
            metadata={
                'total_pages': len(pdf.pages),
                'extraction_method': 'pdfplumber',
                'tables_found': len(tables),
                'layout_preserved': True
            }
        )

class DOCXTextExtractor:
    async def extract(self, docx_content: bytes, filename: str) -> TextExtractionResult:
        """Extract text and structure from DOCX files."""
        
        from docx import Document
        
        doc = Document(io.BytesIO(docx_content))
        
        full_text = ""
        paragraphs = []
        headings = []
        tables = []
        
        for para in doc.paragraphs:
            para_text = para.text.strip()
            if para_text:
                full_text += para_text + "\n"
                paragraphs.append({
                    'text': para_text,
                    'style': para.style.name if para.style else 'Normal',
                    'is_heading': para.style.name.startswith('Heading') if para.style else False
                })
                
                # Track headings for TOC
                if para.style and para.style.name.startswith('Heading'):
                    level = int(para.style.name.replace('Heading ', ''))
                    headings.append({
                        'title': para_text,
                        'level': level,
                        'paragraph_index': len(paragraphs) - 1
                    })
        
        # Extract tables
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            tables.append({'data': table_data})
        
        return TextExtractionResult(
            full_text=full_text,
            paragraphs=paragraphs,
            toc_structure=headings,
            tables=tables,
            metadata={
                'paragraphs_count': len(paragraphs),
                'headings_count': len(headings),
                'tables_count': len(tables),
                'extraction_method': 'python-docx'
            }
        )
```

#### Intelligent Chunking

**Semantic Chunking Strategy:**
```python
class IntelligentChunker:
    def __init__(self):
        self.max_chunk_size = 1500  # Characters
        self.overlap_size = 200     # Overlap between chunks
        self.min_chunk_size = 100   # Minimum viable chunk size
        
    async def create_semantic_chunks(
        self, 
        text: str, 
        document_id: int, 
        tenant_id: int,
        metadata: dict
    ) -> List[DocumentChunk]:
        """Create semantically meaningful chunks from document text."""
        
        # Step 1: Identify semantic boundaries
        boundaries = self._identify_semantic_boundaries(text, metadata)
        
        # Step 2: Create initial chunks respecting boundaries
        initial_chunks = self._create_boundary_respecting_chunks(
            text, boundaries, metadata
        )
        
        # Step 3: Optimize chunk sizes
        optimized_chunks = self._optimize_chunk_sizes(initial_chunks)
        
        # Step 4: Create DocumentChunk objects
        chunks = []
        for i, chunk_data in enumerate(optimized_chunks):
            chunk = DocumentChunk(
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_index=i,
                content=chunk_data['content'],
                start_offset=chunk_data['start_offset'],
                end_offset=chunk_data['end_offset'],
                source_title=metadata.get('filename'),
                chapter_name=chunk_data.get('chapter_name'),
                page_start=chunk_data.get('page_start'),
                page_end=chunk_data.get('page_end'),
                section_level=chunk_data.get('section_level')
            )
            chunks.append(chunk)
        
        return chunks
    
    def _identify_semantic_boundaries(self, text: str, metadata: dict) -> List[dict]:
        """Identify natural breaking points in the document."""
        
        boundaries = []
        
        # Method 1: Use TOC structure if available
        if 'toc_structure' in metadata:
            for heading in metadata['toc_structure']:
                position = text.find(heading['title'])
                if position != -1:
                    boundaries.append({
                        'position': position,
                        'type': 'heading',
                        'level': heading['level'],
                        'title': heading['title'],
                        'page': heading.get('page')
                    })
        
        # Method 2: Paragraph boundaries
        paragraphs = text.split('\n\n')
        current_pos = 0
        for para in paragraphs:
            if len(para.strip()) > 50:  # Substantial paragraph
                boundaries.append({
                    'position': current_pos,
                    'type': 'paragraph',
                    'content': para.strip()
                })
            current_pos += len(para) + 2  # +2 for \n\n
        
        # Method 3: Sentence boundaries (fallback)
        sentences = self._split_into_sentences(text)
        current_pos = 0
        for sentence in sentences:
            if len(sentence) > 20:
                boundaries.append({
                    'position': current_pos,
                    'type': 'sentence',
                    'content': sentence
                })
            current_pos += len(sentence)
        
        # Sort boundaries by position
        boundaries.sort(key=lambda x: x['position'])
        return boundaries
    
    def _create_boundary_respecting_chunks(
        self, 
        text: str, 
        boundaries: List[dict], 
        metadata: dict
    ) -> List[dict]:
        """Create chunks that respect semantic boundaries."""
        
        chunks = []
        current_chunk_start = 0
        current_content = ""
        
        for boundary in boundaries:
            # Check if adding this boundary would exceed max chunk size
            boundary_end = self._find_boundary_end(boundary, text)
            potential_content = text[current_chunk_start:boundary_end]
            
            if len(potential_content) > self.max_chunk_size and current_content:
                # Save current chunk and start new one
                chunks.append(self._create_chunk_data(
                    content=current_content,
                    start_offset=current_chunk_start,
                    end_offset=current_chunk_start + len(current_content),
                    boundaries_included=self._get_boundaries_in_range(
                        boundaries, current_chunk_start, 
                        current_chunk_start + len(current_content)
                    )
                ))
                
                # Start new chunk with overlap
                overlap_start = max(0, current_chunk_start + len(current_content) - self.overlap_size)
                current_chunk_start = overlap_start
                current_content = text[overlap_start:boundary_end]
            else:
                # Add to current chunk
                current_content = potential_content
        
        # Add final chunk
        if current_content and len(current_content) >= self.min_chunk_size:
            chunks.append(self._create_chunk_data(
                content=current_content,
                start_offset=current_chunk_start,
                end_offset=current_chunk_start + len(current_content),
                boundaries_included=self._get_boundaries_in_range(
                    boundaries, current_chunk_start, 
                    current_chunk_start + len(current_content)
                )
            ))
        
        return chunks
    
    def _create_chunk_data(
        self, 
        content: str, 
        start_offset: int, 
        end_offset: int, 
        boundaries_included: List[dict]
    ) -> dict:
        """Create chunk data structure with metadata."""
        
        # Find the most relevant heading for this chunk
        chapter_name = None
        section_level = None
        page_start = None
        page_end = None
        
        for boundary in boundaries_included:
            if boundary['type'] == 'heading':
                if not chapter_name or boundary['level'] < section_level:
                    chapter_name = boundary['title']
                    section_level = boundary['level']
            
            if 'page' in boundary:
                if page_start is None or boundary['page'] < page_start:
                    page_start = boundary['page']
                if page_end is None or boundary['page'] > page_end:
                    page_end = boundary['page']
        
        return {
            'content': content.strip(),
            'start_offset': start_offset,
            'end_offset': end_offset,
            'chapter_name': chapter_name,
            'section_level': section_level,
            'page_start': page_start,
            'page_end': page_end
        }
```

#### Embedding Generation and Storage

**OpenAI Embedding Service:**
```python
class OpenAIEmbedder:
    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = "text-embedding-3-large"
        self.batch_size = 50  # Process in batches for efficiency
    
    async def generate_embeddings(
        self, 
        chunks: List[DocumentChunk]
    ) -> List[EmbeddingResult]:
        """Generate embeddings for document chunks in batches."""
        
        # Process in batches to avoid API limits
        embedding_results = []
        
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_results = await self._process_batch(batch)
            embedding_results.extend(batch_results)
        
        return embedding_results
    
    async def _process_batch(
        self, 
        chunk_batch: List[DocumentChunk]
    ) -> List[EmbeddingResult]:
        """Process a batch of chunks for embedding generation."""
        
        # Prepare texts for embedding
        texts = [chunk.content for chunk in chunk_batch]
        
        try:
            # Call OpenAI API
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float"
            )
            
            # Create results
            results = []
            for i, (chunk, embedding_data) in enumerate(zip(chunk_batch, response.data)):
                result = EmbeddingResult(
                    chunk=chunk,
                    embedding=embedding_data.embedding,
                    model=self.model,
                    token_count=len(texts[i].split()),  # Approximate
                    api_usage=response.usage if i == 0 else None  # Include usage for first item
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            log_error("Embedding generation failed for batch", error=str(e))
            raise EmbeddingGenerationError(f"Failed to generate embeddings: {str(e)}")
```

**Dual Storage Persistence:**
```python
class DualStoragePersistence:
    def __init__(self):
        self.db = PostgreSQLDocumentStore()
        self.vector_store = QdrantVectorStore()
    
    async def store_document_and_embeddings(
        self, 
        document: Document, 
        chunks: List[DocumentChunk],
        embedding_results: List[EmbeddingResult]
    ):
        """Store document data in both PostgreSQL and Qdrant with transaction consistency."""
        
        try:
            # Begin database transaction
            async with self.db.transaction() as tx:
                # Store document chunks in PostgreSQL
                chunk_ids = await self._store_chunks_in_db(chunks, tx)
                
                # Prepare Qdrant points
                qdrant_points = self._prepare_qdrant_points(
                    chunks, embedding_results, chunk_ids
                )
                
                # Store in Qdrant
                qdrant_operation = await self.vector_store.upsert_points(
                    collection_name="document_chunks",
                    points=qdrant_points
                )
                
                if not qdrant_operation.success:
                    raise VectorStoreError("Failed to store embeddings in Qdrant")
                
                # Update chunks with Qdrant point IDs in PostgreSQL
                await self._update_chunks_with_qdrant_ids(
                    chunk_ids, qdrant_points, tx
                )
                
                # Commit transaction
                await tx.commit()
                
                log_info(f"Successfully stored document with {len(chunks)} chunks")
                
        except Exception as e:
            log_error("Dual storage persistence failed", error=str(e))
            # Cleanup: Remove from Qdrant if PostgreSQL failed
            if 'qdrant_points' in locals():
                await self._cleanup_qdrant_points(qdrant_points)
            raise DocumentStorageError(f"Failed to store document: {str(e)}")
    
    def _prepare_qdrant_points(
        self, 
        chunks: List[DocumentChunk],
        embedding_results: List[EmbeddingResult],
        chunk_ids: List[int]
    ) -> List[qdrant_client.models.PointStruct]:
        """Prepare Qdrant points with embeddings and metadata."""
        
        points = []
        for chunk, embedding_result, chunk_id in zip(chunks, embedding_results, chunk_ids):
            point = qdrant_client.models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding_result.embedding,
                payload={
                    "chunk_id": chunk_id,
                    "document_id": chunk.document_id,
                    "tenant_id": chunk.tenant_id,
                    "content": chunk.content,
                    "source_title": chunk.source_title,
                    "chapter_name": chunk.chapter_name,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "section_level": chunk.section_level,
                    "chunk_index": chunk.chunk_index
                }
            )
            points.append(point)
        
        return points
```

### File Format Support

#### Supported File Types
```python
SUPPORTED_FILE_TYPES = {
    '.pdf': {
        'mime_types': ['application/pdf'],
        'max_size_mb': 50,
        'extractor': 'PDFTextExtractor',
        'features': ['text', 'toc', 'pages', 'tables']
    },
    '.docx': {
        'mime_types': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'max_size_mb': 25,
        'extractor': 'DOCXTextExtractor', 
        'features': ['text', 'headings', 'tables', 'styles']
    },
    '.txt': {
        'mime_types': ['text/plain'],
        'max_size_mb': 10,
        'extractor': 'PlainTextExtractor',
        'features': ['text']
    },
    # Future extensions:
    # '.xlsx': {...},
    # '.pptx': {...},
    # '.md': {...}
}
```

#### File Validation
```python
class DocumentValidator:
    @staticmethod
    def validate_file_upload(
        file_content: bytes, 
        filename: str, 
        tenant_id: int
    ):
        """Comprehensive file validation before processing."""
        
        # File size check
        if len(file_content) == 0:
            raise ValidationError("Empty file not allowed")
        
        file_extension = Path(filename).suffix.lower()
        
        if file_extension not in SUPPORTED_FILE_TYPES:
            raise UnsupportedFileTypeError(
                f"File type {file_extension} not supported"
            )
        
        file_config = SUPPORTED_FILE_TYPES[file_extension]
        max_size_bytes = file_config['max_size_mb'] * 1024 * 1024
        
        if len(file_content) > max_size_bytes:
            raise FileSizeError(
                f"File too large: {len(file_content)} bytes (max: {max_size_bytes})"
            )
        
        # MIME type validation
        detected_mime = magic.from_buffer(file_content, mime=True)
        if detected_mime not in file_config['mime_types']:
            raise InvalidFileTypeError(
                f"File content doesn't match extension. Detected: {detected_mime}"
            )
        
        # Security scan (basic)
        if DocumentValidator._contains_malicious_patterns(file_content):
            raise SecurityError("File contains potentially malicious content")
        
        return True
    
    @staticmethod
    def _contains_malicious_patterns(file_content: bytes) -> bool:
        """Basic malicious content detection."""
        
        # Check for embedded executables
        malicious_signatures = [
            b'MZ',      # Windows executable
            b'PK\x03\x04',  # ZIP file (could contain executables)
            b'\x7fELF',  # Linux executable
            b'\xca\xfe\xba\xbe',  # Java class file
        ]
        
        for signature in malicious_signatures:
            if file_content[:10].startswith(signature):
                return True
        
        return False
```

## Funkció-specifikus konfiguráció

### Document Processing Configuration
```ini
# File upload limits
MAX_FILE_SIZE_MB=50
MAX_FILES_PER_REQUEST=10
SUPPORTED_EXTENSIONS=pdf,docx,txt

# Chunking configuration
MAX_CHUNK_SIZE_CHARS=1500
CHUNK_OVERLAP_CHARS=200
MIN_CHUNK_SIZE_CHARS=100
RESPECT_SEMANTIC_BOUNDARIES=true

# Text extraction
PDF_EXTRACTION_TIMEOUT_SEC=30
ENABLE_OCR_FALLBACK=false
OCR_LANGUAGE=hun

# Embedding generation
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_BATCH_SIZE=50
EMBEDDING_TIMEOUT_SEC=60

# Storage configuration
ENABLE_TRANSACTIONAL_STORAGE=true
CLEANUP_FAILED_PROCESSING=true
STORE_FULL_DOCUMENT_TEXT=true
```

### Multi-tenant Document Isolation
```python
# All document operations enforce tenant isolation
async def store_document(file_content, filename, tenant_id, user_id, visibility):
    # Validate tenant access
    if not await validate_tenant_access(tenant_id, user_id):
        raise AuthorizationError("Tenant access denied")
    
    # All database operations filtered by tenant
    document = await db.create_document(
        content=full_text,
        tenant_id=tenant_id,  # Always required
        user_id=user_id if visibility == "private" else None,
        visibility=visibility
    )
    
    # Vector storage with tenant isolation
    await qdrant.upsert_points(
        collection_name="document_chunks",
        points=[{
            "id": point_id,
            "vector": embedding,
            "payload": {
                "tenant_id": tenant_id,  # Enforced in all searches
                "chunk_id": chunk_id,
                ...
            }
        }]
    )
```

### Error Recovery and Cleanup
```python
class DocumentProcessingCleanup:
    @staticmethod
    async def cleanup_failed_processing(document_id: int):
        """Clean up resources from failed document processing."""
        
        try:
            # Remove document chunks from PostgreSQL
            chunk_ids = await db.get_chunk_ids_for_document(document_id)
            await db.delete_document_chunks(document_id)
            
            # Remove embeddings from Qdrant
            await qdrant.delete_points(
                collection_name="document_chunks",
                points_selector=qdrant_client.models.FilterSelector(
                    filter=qdrant_client.models.Filter(
                        must=[
                            qdrant_client.models.FieldCondition(
                                key="document_id",
                                match=qdrant_client.models.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            
            # Remove document record
            await db.delete_document(document_id)
            
            log_info(f"Cleaned up failed processing for document {document_id}")
            
        except Exception as e:
            log_error("Cleanup failed", document_id=document_id, error=str(e))
```

### Performance Monitoring
```python
# Document processing metrics
class DocumentProcessingMetrics:
    @staticmethod
    def log_processing_metrics(result: DocumentProcessingResult):
        # Processing time metrics
        prometheus.document_processing_duration.observe(
            result.processing_time_ms / 1000,
            labels={'file_type': Path(result.filename).suffix}
        )
        
        # Document size metrics
        prometheus.document_size_chars.observe(
            result.total_characters,
            labels={'tenant_id': str(result.tenant_id)}
        )
        
        # Chunks created metrics
        prometheus.chunks_created_total.inc(
            result.chunks_created,
            labels={'extraction_method': result.extraction_metadata.get('extraction_method')}
        )
        
        # Success rate tracking
        prometheus.document_processing_success_total.inc(
            labels={'file_type': Path(result.filename).suffix}
        )
```

### Advanced Features

#### Automatic Chapter Detection
```python
def detect_chapter_structure(text: str) -> List[dict]:
    """Detect document chapter structure using ML patterns."""
    
    chapter_patterns = [
        r'^(Chapter|Fejezet)\s+\d+',
        r'^\d+\.\s+[A-Z][^.]{10,}',
        r'^[A-Z]{2,}[^a-z]{0,10}$',  # ALL CAPS headings
        r'^\s*\d+\.\d+\s+[A-Z]',     # Numbered subsections
    ]
    
    chapters = []
    for line_num, line in enumerate(text.split('\n')):
        for pattern in chapter_patterns:
            if re.match(pattern, line.strip()):
                chapters.append({
                    'line_number': line_num,
                    'title': line.strip(),
                    'level': infer_heading_level(line),
                    'pattern_used': pattern
                })
                break
    
    return chapters
```

#### Content Quality Assessment
```python
def assess_content_quality(chunk: DocumentChunk) -> float:
    """Assess the quality of extracted chunk content."""
    
    quality_score = 1.0
    content = chunk.content
    
    # Penalize very short chunks
    if len(content) < 100:
        quality_score *= 0.7
    
    # Penalize chunks with excessive special characters
    special_char_ratio = len(re.findall(r'[^\w\s]', content)) / len(content)
    if special_char_ratio > 0.3:
        quality_score *= 0.8
    
    # Reward chunks with clear structure
    if chunk.chapter_name:
        quality_score *= 1.1
    
    # Reward chunks with page references
    if chunk.page_start:
        quality_score *= 1.05
    
    return min(1.0, quality_score)
```