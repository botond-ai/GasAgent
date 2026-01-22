import hashlib
import uuid
from pathlib import Path
from typing import List

from infrastructure.vector_store import VectorStore, Domain
from core.markdown_chunker import MarkdownRAGChunker
from presentation.display_writer_interface import DisplayWriterInterface


class DocumentProcessor:
    """
    Handles document ingestion: hashing, deduplication, and chunking coordination.

    Single Responsibility: Processing individual documents into the vector store
    with hash-based change detection.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        chunker: MarkdownRAGChunker,
        display_writer: DisplayWriterInterface
    ):
        self.vector_store = vector_store
        self.chunker = chunker
        self.display_writer = display_writer

    async def process_document(self, filepath: Path, domain: Domain) -> bool:
        """
        Process a single document with hash-based deduplication.

        Returns True if document was processed (new or updated), False if skipped.

        Deduplication rules:
        - Title not in DB: process and add
        - Title in DB with same hash: skip
        - Title in DB with different hash: delete old chunks, reprocess
        """
        title = filepath.name
        source = str(filepath.absolute())
        current_hash = self._compute_file_hash(filepath)

        existing = self.vector_store.find_by_title(title, domain)

        if existing:
            existing_hash = existing["metadata"].get("hash", "")

            if existing_hash == current_hash:
                self.display_writer.write(f"  [SKIP] {title} - unchanged\n")
                return False
            else:
                deleted_count = self.vector_store.delete_by_title(title, domain)
                self.display_writer.write(f"  [UPDATE] {title} - deleted {deleted_count} old chunks\n")
        else:
            self.display_writer.write(f"  [NEW] {title}\n")

        await self._ingest_document(filepath, title, source, current_hash, domain)
        return True

    async def process_documents(self, filepaths: List[str], domain: Domain) -> int:
        """
        Process multiple documents.

        Returns the count of documents that were processed (new or updated).
        """
        self.display_writer.write("Processing documents for ingestion...\n")
        processed_count = 0

        for filepath_str in filepaths:
            filepath = Path(filepath_str)
            if await self.process_document(filepath, domain):
                processed_count += 1

        return processed_count

    async def _ingest_document(
        self,
        filepath: Path,
        title: str,
        source: str,
        file_hash: str,
        domain: Domain
    ) -> None:
        """Chunk and add document to vector store."""
        try:
            text = self.chunker.load_markdown(str(filepath))
            chunks = self.chunker.chunk_document(text, str(filepath))

            doc_uuid = str(uuid.uuid4())

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_uuid}_{i}"
                await self.vector_store.add_document_chunk(
                    text=chunk['text'],
                    domain=domain,
                    metadata={
                        "doc_id": chunk_id,
                        "title": title,
                        "source": source,
                        "hash": file_hash,
                    }
                )

            self.display_writer.write(f"    Added {len(chunks)} chunks\n")

        except Exception as e:
            self.display_writer.write(f"    [ERROR] Failed to process {title}: {e}\n")

    def _compute_file_hash(self, filepath: Path) -> str:
        """Compute SHA-256 hash of file content."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
