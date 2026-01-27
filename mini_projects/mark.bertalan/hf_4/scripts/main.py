"""
Main entry point for the vector embeddings demo application.

USAGE INSTRUCTIONS:
-------------------

1. Setup:
   - Copy .env.example to .env:
     $ cp .env.example .env
   
   - Edit .env and add your OpenAI API key:
     OPENAI_API_KEY=sk-your-actual-api-key-here

2. Build Docker image:
   $ docker build -t embedding-demo .

3. Run the application:
   $ docker run -it --env-file .env embedding-demo

4. Interact with the CLI:
   - Type prompts and press Enter
   - View similar prompts from the vector database
   - Type 'exit' to quit

ARCHITECTURE:
-------------
This application demonstrates SOLID principles:

- Single Responsibility: Each module has one clear purpose
  • config.py: Configuration loading
  • embeddings.py: Embedding generation
  • vector_store.py: Vector database operations
  • application.py: Business logic orchestration
  • cli.py: User interface

- Open/Closed: The app is open for extension via interfaces
  • Can swap embedding providers (OpenAI, Cohere, etc.)
  • Can swap vector stores (Chroma, Pinecone, Weaviate, etc.)

- Liskov Substitution: Concrete classes honor their interface contracts

- Interface Segregation: Small, focused interfaces (EmbeddingService, VectorStore)

- Dependency Inversion: High-level logic depends on abstractions, not implementations
"""

from scripts.config import Config
from scripts.embeddings import OpenAIEmbeddingClient
from scripts.vector_store import ChromaVectorStore
from scripts.llm import OpenAILLMClient
from scripts.application import EmbeddingApp
from typing import List, Tuple, Optional, Dict, Any
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

def format_cosine_results(
    results: List[Tuple[str, float, float, str, Optional[Dict[str, Any]]]]
) -> str:
    """
    Format cosine similarity search results for display.

    Args:
        results: List of (id, distance, similarity, text, metadata) tuples.

    Returns:
        Formatted string for terminal output.
    """
    if not results:
        return "No results found."

    output = "\n📊 COSINE SIMILARITY SEARCH:\n"
    output += "   (Measures angle between vectors - higher similarity = more similar)\n"
    for i, (doc_id, distance, similarity, text, metadata) in enumerate(results, 1):
        # Truncate long texts for display
        display_text = text
        output += f"  {i}. similarity={similarity:.4f} (dist={distance:.4f}) \"{display_text}\"\n"

        # Display metadata if available
        if metadata:
            output += f"     📝 Source: {metadata.get('source_document_id', 'unknown')}, "
            output += f"Domain: {metadata.get('domain', 'unknown')}, "
            output += f"Chunk: {metadata.get('chunk_index', '?')}/{metadata.get('total_chunks', '?')}\n"

    return output

def format_knn_results(
    results: List[Tuple[str, float, str, Optional[Dict[str, Any]]]]
) -> str:
    """
    Format k-NN (Euclidean distance) search results for display.

    Args:
        results: List of (id, euclidean_distance, text, metadata) tuples.

    Returns:
        Formatted string for terminal output.
    """
    if not results:
        return "No results found."

    output = "\n📏 K-NEAREST NEIGHBORS (Euclidean Distance):\n"
    output += "   (Measures geometric distance - lower distance = more similar)\n"
    for i, (doc_id, euclidean_dist, text, metadata) in enumerate(results, 1):
        # Truncate long texts for display
        display_text = text if len(text) <= 55 else f"{text[:52]}..."
        output += f"  {i}. distance={euclidean_dist:.4f} \"{display_text}\"\n"

        # Display metadata if available
        if metadata:
            output += f"     📝 Source: {metadata.get('source_document_id', 'unknown')}, "
            output += f"Domain: {metadata.get('domain', 'unknown')}, "
            output += f"Chunk: {metadata.get('chunk_index', '?')}/{metadata.get('total_chunks', '?')}\n"

    return output

def main() -> None:
    """
    Initialize and run the application.
    
    This function wires up all dependencies using constructor injection,
    demonstrating the Dependency Inversion Principle.
    """
    try:
        # Load configuration
        config = Config.from_env()
        
        # Initialize embedding service (concrete implementation)
        embedding_service = OpenAIEmbeddingClient(
            token=config.openai_api_key,
            model_name=config.embedding_model,
            chunk_size=config.embedding_chunk_size,
            overlap=config.overlap
        )
        
        # Initialize vector store (concrete implementation)
        vector_store = ChromaVectorStore(
            db_path=config.chroma_db_path,
            collection_name=config.collection_name
        )

        # Initialize LLM service (concrete implementation)
        llm_service = OpenAILLMClient(
            token=config.openai_api_key,
            model_name=config.llm_model
        )

        # Create application with injected dependencies
        # (app depends on abstractions, not concrete classes)
        app = EmbeddingApp(
            embedding_service=embedding_service,
            vector_store=vector_store,
            llm=llm_service,
            config=config  # Pass config for Jira integration
        )
        
        # Embed documents for RAG
        app.store_and_embed_documents(config.documents_root)

        print("\nCommands:")
        print("  - Type your question and press Enter")
        print("  - 'reset' - Clear conversation history")
        print("  - 'exit' - Quit the application")

        while True:
            try:
                # Prompt user for input
                user_input = input("\nEnter a prompt (or 'exit' to quit): ").strip()

                # Check for exit command
                if user_input.lower() == 'exit':
                    print("\nGoodbye!")
                    break

                # Check for reset command
                if user_input.lower() == 'reset':
                    app.reset_conversation()
                    print("✓ Conversation history cleared")
                    continue

                # Skip empty inputs
                if not user_input:
                    print("Please enter a non-empty prompt.")
                    continue
                
                # Process the query with RAG
                print("\nProcessing...")
                query_id, results, generated_answer, state = app.process_query_with_rag(user_input, k=3)

                # Debug: Show state info
                print(f"\n[DEBUG] jira_suggested: {state.get('jira_suggested', False)}")
                print(f"[DEBUG] conversation_history length: {len(state.get('conversation_history', []))}")
                print(f"[DEBUG] pending_jira_suggestion: {state.get('pending_jira_suggestion')}")

                # Display generated answer
                print(f"\n✓ Query ID: {query_id}")
                print("\n" + "="*60)
                print("🤖 GENERATED ANSWER:")
                print("="*60)
                print(generated_answer)
                print("="*60)


            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n✗ Error: {e}")
                print("Please try again or type 'exit' to quit.")
      
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
