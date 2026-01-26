#!/usr/bin/env python3
"""
Script to ingest demo documents into the vector database.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag import get_document_processor, get_vectorstore


DEMO_DOCS_PATH = Path(__file__).parent.parent / "data" / "demo_docs"

DOCUMENTS = [
    {
        "filename": "aszf.md",
        "title": "Általános Szerződési Feltételek",
        "doc_type": "aszf",
        "doc_id": "KB-001",
    },
    {
        "filename": "faq.md",
        "title": "Gyakran Ismételt Kérdések",
        "doc_type": "faq",
        "doc_id": "KB-002",
    },
    {
        "filename": "user_guide.md",
        "title": "Felhasználói Útmutató",
        "doc_type": "user_guide",
        "doc_id": "KB-003",
    },
    {
        "filename": "policy.md",
        "title": "Támogatási Szabályzat",
        "doc_type": "policy",
        "doc_id": "KB-004",
    },
]


def main():
    """Main function to ingest all demo documents."""
    print("=" * 60)
    print("TaskFlow Knowledge Base Ingestion")
    print("=" * 60)

    # Initialize services
    processor = get_document_processor()
    vectorstore = get_vectorstore()

    # Ensure collection exists
    vectorstore.ensure_collection()
    print(f"\nCollection: {vectorstore.collection_name}")

    # Process each document
    total_chunks = 0

    for doc_info in DOCUMENTS:
        file_path = DEMO_DOCS_PATH / doc_info["filename"]

        if not file_path.exists():
            print(f"\n❌ File not found: {file_path}")
            continue

        print(f"\n📄 Processing: {doc_info['title']}")
        print(f"   File: {doc_info['filename']}")

        # Read content
        content = file_path.read_text(encoding="utf-8")
        print(f"   Size: {len(content)} characters")

        # Process document
        try:
            result = processor.process_document(
                content=content,
                title=doc_info["title"],
                doc_type=doc_info["doc_type"],
                doc_id=doc_info["doc_id"],
                language="hu",
                url=f"/kb/{doc_info['doc_id'].lower()}",
            )

            print(f"   ✅ Indexed: {result.chunks_count} chunks")
            total_chunks += result.chunks_count

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Documents processed: {len(DOCUMENTS)}")
    print(f"Total chunks created: {total_chunks}")

    # Show collection info
    info = vectorstore.get_collection_info()
    print(f"\nCollection status:")
    print(f"  Points count: {info.get('points_count', 'N/A')}")
    print(f"  Status: {info.get('status', 'N/A')}")

    print("\n✅ Ingestion complete!")


if __name__ == "__main__":
    main()
