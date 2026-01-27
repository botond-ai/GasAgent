from pathlib import Path
from typing import Optional

from infrastructure.vector_store import Domain
from core.document_processor import DocumentProcessor
from presentation.display_writer_interface import DisplayWriterInterface


class KnowledgeBaseLoader:
    """
    Handles knowledge base folder traversal and domain detection.

    Single Responsibility: Discovering documents in a folder structure
    and delegating processing to DocumentProcessor.

    Expected folder structure:
        knowledge_base_path/
            hr/
                doc1.md
                subfolder/doc2.md
            it/
                doc3.md
            finance/
                doc4.md
    """

    def __init__(
        self,
        document_processor: DocumentProcessor,
        display_writer: DisplayWriterInterface
    ):
        self.document_processor = document_processor
        self.display_writer = display_writer

    async def load(self, knowledge_base_path: str) -> None:
        """
        Traverse the knowledge base folder and process all documents.

        Domain is determined by the first-level subdirectory name.
        """
        base_path = Path(knowledge_base_path)

        if not base_path.exists():
            self.display_writer.write(f"Knowledge base path does not exist: {base_path}")
            return

        self.display_writer.write(f"Initializing knowledge base from: {base_path}")

        domain_folders = [d for d in base_path.iterdir() if d.is_dir()]

        for domain_folder in domain_folders:
            domain = self._resolve_domain(domain_folder.name)

            if domain is None:
                self.display_writer.write(f"Skipping unknown domain folder: {domain_folder.name}\n")
                continue

            self.display_writer.write(f"Processing domain: {domain.value}")

            md_files = list(domain_folder.rglob("*.md"))

            for filepath in md_files:
                await self.document_processor.process_document(filepath, domain)

        self.display_writer.write("\nKnowledge base initialization complete.\n")

    def _resolve_domain(self, folder_name: str) -> Optional[Domain]:
        """Map folder name to Domain enum, returns None if invalid."""
        try:
            return Domain(folder_name.lower())
        except ValueError:
            return None
