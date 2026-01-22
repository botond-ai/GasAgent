import asyncio
import os

from dotenv import load_dotenv

from infrastructure.openai_gateway import OpenAIGateway
from infrastructure.vector_store import VectorStore
from presentation.cli_interface import CliInterface
from core.document_processor import DocumentProcessor
from core.knowledge_base_loader import KnowledgeBaseLoader
from core.markdown_chunker import MarkdownRAGChunker
from core.rag_engine import RAGEngine
from core.conversation_session import ConversationSession
from workflows import create_workflow


async def main():
    load_dotenv()

    # Presentation layer
    display_writer = CliInterface()

    display_writer.write("Loading documents, please wait...\n")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")

    # Infrastructure layer
    openai_gateway = OpenAIGateway(
        api_key=openai_api_key,
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        completion_model=os.getenv("COMPLETION_MODEL", "gpt-4o-mini")
    )
    vector_store = VectorStore(openai_gateway)

    # Core layer
    chunker = MarkdownRAGChunker(display_writer)
    rag_engine = RAGEngine(vector_store)

    # Document ingestion
    root_dir = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.join(root_dir, os.pardir, "data")

    processor = DocumentProcessor(vector_store, chunker, display_writer)
    loader = KnowledgeBaseLoader(processor, display_writer)
    await loader.load(documents_dir)

    # LangGraph workflow
    workflow = create_workflow(openai_gateway, rag_engine)

    # Conversation session for memory across queries
    session = ConversationSession()

    # Interactive loop
    display_writer.write("\n" + "=" * 50)
    display_writer.write("Knowledge Assistant Ready")
    display_writer.write("Type 'quit' to exit, 'clear' to reset conversation")
    display_writer.write("=" * 50 + "\n")

    while True:
        query = input("You: ").strip()

        if query.lower() in ("quit", "exit", "q"):
            display_writer.write("Goodbye!")
            break

        if query.lower() == "clear":
            session.clear()
            display_writer.write("Conversation history cleared.\n")
            continue

        if not query:
            continue

        # Run the workflow with conversation history
        result = await workflow.run(query, session.get_history())

        # Add this turn to the conversation session
        session.add_turn(query, result['response'])

        # Display results
        display_writer.write(f"\n[Domain: {result['detected_domain'].value if result['detected_domain'] else 'unknown'}]")
        display_writer.write(f"Assistant: {result['response']}\n")

        if result['citations']:
            display_writer.write("Sources:")
            for cite in result['citations']:
                display_writer.write(f"  - {cite['title']} (relevance: {cite['score']:.2f})")
            display_writer.write()


if __name__ == "__main__":
    asyncio.run(main())