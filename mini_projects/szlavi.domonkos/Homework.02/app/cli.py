"""Command-line interface for the embedding application and RAG agent.

The CLI is a thin layer that interacts with the user and delegates
work to `EmbeddingApp` and `RAGAgent` which follow dependency injection principles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
import uuid
import textwrap

from .embeddings import EmbeddingService
from .vector_store import VectorStore
from .rag_agent import RAGAgent
from .google_calendar import CalendarService


@dataclass
class Neighbor:
    id: str
    distance: float
    text: str


class EmbeddingApp:
    """High-level orchestration class.

    Depends on abstractions: `EmbeddingService` and `VectorStore`.
    """

    def __init__(self, emb_service: EmbeddingService, vector_store: VectorStore) -> None:
        self.emb = emb_service
        self.store = vector_store

    def process_query(self, text: str, k: int = 3, mode: str = "hybrid", alpha: float = 0.5) -> Tuple[str, List[Neighbor]]:
        """Embed the text, add to vector store, run similarity search.

        Returns the stored id and a list of neighbors.
        """
        uid = uuid.uuid4().hex
        embedding = self.emb.get_embedding(text)
        # store even if embedding is empty (graceful degradation)
        self.store.add(uid, text, embedding)
        # Choose search method
        if mode == "hybrid" and hasattr(self.store, "hybrid_search"):
            results = self.store.hybrid_search(embedding, query_text=text, k=k, alpha=alpha)
            neighbors: List[Neighbor] = [Neighbor(id=r[0], distance=r[1], text=r[2]) for r in results]
        elif mode == "bm25" and hasattr(self.store, "hybrid_search"):
            # bm25-only: alpha=0
            results = self.store.hybrid_search(embedding, query_text=text, k=k, alpha=0.0)
            neighbors = [Neighbor(id=r[0], distance=r[1], text=r[2]) for r in results]
        else:
            results = self.store.similarity_search(embedding, k=k)
            neighbors = [Neighbor(id=r[0], distance=r[1], text=r[2]) for r in results]
        return uid, neighbors


class CLI:
    def __init__(
        self,
        emb_service: EmbeddingService,
        vector_store: VectorStore,
        rag_agent: Optional[RAGAgent] = None,
        calendar_service: Optional[CalendarService] = None,
    ) -> None:
        self.app = EmbeddingApp(emb_service, vector_store)
        self.rag_agent = rag_agent
        self.calendar_service = calendar_service

    def _print_intro(self) -> None:
        intro = (
            "Embedding CLI with RAG - stores documents and performs retrieval + generation.\n"
            "Type your prompt and press Enter. Type 'exit' to quit.\n"
            "Commands: '/mode hybrid|semantic|bm25', '/k N', '/alpha X', '/rag on|off'"
        )
        if self.calendar_service:
            intro += "\nCalendar commands: '/calendar events', '/calendar today', '/calendar range START END'"
        print(textwrap.dedent(intro))

    def _print_results(self, uid: str, neighbors: List[Neighbor]) -> None:
        print("\nStored prompt id:", uid)
        print("Retrieved nearest neighbors:")
        if not neighbors:
            print("  (no results)")
            return

        for i, n in enumerate(neighbors, start=1):
            print(f"{i}. (score={n.distance:.6f}) \"{n.text}\"")

    def _print_rag_response(
        self, uid: str, neighbors: List[Neighbor], response: str
    ) -> None:
        """Print retrieved context and generated response."""
        print("\nStored query id:", uid)
        print("\n--- Retrieved Context ---")
        if not neighbors:
            print("  (no documents found)")
        else:
            for i, n in enumerate(neighbors, start=1):
                print(f"[{i}] (relevance: {n.distance:.6f})")
                print(f"    {n.text[:200]}..." if len(n.text) > 200 else f"    {n.text}")

        print("\n--- Generated Response ---")
        print(response)

    def _print_calendar_events(self, events: List[dict]) -> None:
        """Print calendar events in a formatted way."""
        if not events:
            print("No events found.")
            return

        print(f"\nUpcoming Events ({len(events)}):")
        for i, event in enumerate(events, start=1):
            print(f"\n[{i}] {event.get('title', 'Untitled')}")
            print(f"    Start: {event.get('start', 'N/A')}")
            print(f"    End: {event.get('end', 'N/A')}")
            if event.get('location'):
                print(f"    Location: {event.get('location')}")
            if event.get('description'):
                desc = event.get('description')[:100]
                print(f"    Description: {desc}...")

    def run(self) -> None:
        self._print_intro()
        mode = "hybrid"
        k = 3
        alpha = 0.5
        rag_enabled = self.rag_agent is not None
        while True:
            try:
                text = input("Enter a prompt (or 'exit' to quit): ").strip()
            except EOFError:
                print()
                break

            if not text:
                continue
            if text.lower() in {"exit", "quit"}:
                break

            # simple command parsing
            if text.startswith("/mode "):
                new_mode = text.split(maxsplit=1)[1].strip().lower()
                if new_mode in {"hybrid", "semantic", "bm25"}:
                    mode = new_mode
                    print(f"Search mode set to: {mode}")
                else:
                    print("Unknown mode. Valid: hybrid, semantic, bm25")
                continue

            if text.startswith("/k "):
                try:
                    k = int(text.split(maxsplit=1)[1].strip())
                    print(f"Result count k set to: {k}")
                except Exception:
                    print("Invalid k value")
                continue

            if text.startswith("/alpha "):
                try:
                    alpha = float(text.split(maxsplit=1)[1].strip())
                    print(f"Hybrid alpha set to: {alpha}")
                except Exception:
                    print("Invalid alpha value")
                continue

            if text.startswith("/rag "):
                rag_cmd = text.split(maxsplit=1)[1].strip().lower()
                if rag_cmd == "on":
                    if self.rag_agent is None:
                        print("RAG agent not available (no LLM configured)")
                    else:
                        rag_enabled = True
                        print("RAG generation enabled")
                elif rag_cmd == "off":
                    rag_enabled = False
                    print("RAG generation disabled")
                else:
                    print("Invalid /rag command. Use: /rag on or /rag off")
                continue

            if text.startswith("/calendar "):
                if not self.calendar_service:
                    print("Calendar service not available")
                    continue

                cal_cmd = text.split(maxsplit=1)[1].strip().lower()
                try:
                    if cal_cmd == "events":
                        events = self.calendar_service.get_upcoming_events(max_results=5)
                        self._print_calendar_events(events)
                    elif cal_cmd == "today":
                        from datetime import datetime, timedelta
                        today = datetime.now().strftime("%Y-%m-%d")
                        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                        events = self.calendar_service.get_events_by_date(today, tomorrow)
                        print(f"Events for today ({today}):")
                        self._print_calendar_events(events)
                    elif cal_cmd.startswith("range "):
                        parts = cal_cmd.split(maxsplit=2)
                        if len(parts) >= 3:
                            start_date = parts[1]
                            end_date = parts[2]
                            events = self.calendar_service.get_events_by_date(start_date, end_date)
                            print(f"Events from {start_date} to {end_date}:")
                            self._print_calendar_events(events)
                        else:
                            print("Usage: /calendar range YYYY-MM-DD YYYY-MM-DD")
                    else:
                        print("Calendar commands: /calendar events, /calendar today, /calendar range START END")
                except Exception as exc:
                    print(f"Calendar error: {exc}")
                continue

            uid, neighbors = self.app.process_query(text, k=k, mode=mode, alpha=alpha)
            if rag_enabled and self.rag_agent:
                # Convert neighbors to format expected by RAG agent
                doc_tuples = [(n.id, n.distance, n.text) for n in neighbors]
                response = self.rag_agent.generate_response(text, doc_tuples)
                self._print_rag_response(uid, neighbors, response)
            else:
                self._print_results(uid, neighbors)

    def process_directory(self, data_dir: str, k: int = 3, mode: str = "hybrid", alpha: float = 0.5) -> None:
        """Process all text/markdown files in `data_dir`: embed, store and run search.

        This is a batch mode alternative to the interactive CLI. It reads files
        (extensions .md, .txt) and calls `process_query` for each file's content.
        """
        import os

        if not os.path.isdir(data_dir):
            print(f"Data directory not found: {data_dir}")
            return

        files = [f for f in os.listdir(data_dir) if f.endswith((".md", ".txt"))]
        if not files:
            print(f"No .md or .txt files found in {data_dir}")
            return

        print(f"Processing {len(files)} files from {data_dir} (mode={mode}, k={k}, alpha={alpha})")
        for fname in files:
            path = os.path.join(data_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read().strip()
            except Exception as exc:
                print(f"Failed to read {path}: {exc}")
                continue

            if not content:
                print(f"Skipping empty file: {path}")
                continue

            uid, neighbors = self.app.process_query(content, k=k, mode=mode, alpha=alpha)
            print("\nFile:", fname)
            self._print_results(uid, neighbors)
