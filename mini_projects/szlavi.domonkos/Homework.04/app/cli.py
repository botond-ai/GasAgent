"""Command-line interface for the embedding application and RAG agent.

The CLI is a thin layer that interacts with the user and delegates
work to `EmbeddingApp` and `RAGAgent` which follow dependency injection principles.
Includes support for LangGraph workflow orchestration and metrics monitoring.
"""

from __future__ import annotations

import json
import textwrap
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from .embeddings import EmbeddingService
from .google_calendar import CalendarService
from .metrics import MetricCollector
from .rag_agent import RAGAgent
from .tool_clients import (CryptoClient, ForexClient, GeolocationClient,
                           WeatherClient)
from .vector_store import VectorStore

if TYPE_CHECKING:
    from .langgraph_workflow import MeetingAssistantWorkflow


@dataclass
class Neighbor:
    id: str
    distance: float
    text: str


class EmbeddingApp:
    """High-level orchestration class.

    Depends on abstractions: `EmbeddingService` and `VectorStore`.
    """

    def __init__(
        self, emb_service: EmbeddingService, vector_store: VectorStore
    ) -> None:
        self.emb = emb_service
        self.store = vector_store

    def process_query(
        self, text: str, k: int = 3, mode: str = "hybrid", alpha: float = 0.5
    ) -> Tuple[str, List[Neighbor]]:
        """Embed the text, add to vector store, run similarity search.

        Returns the stored id and a list of neighbors.
        """
        uid = uuid.uuid4().hex
        embedding = self.emb.get_embedding(text)
        # store even if embedding is empty (graceful degradation)
        self.store.add(uid, text, embedding)
        # Choose search method
        if mode == "hybrid" and hasattr(self.store, "hybrid_search"):
            results = self.store.hybrid_search(
                embedding, query_text=text, k=k, alpha=alpha
            )
            neighbors: List[Neighbor] = [
                Neighbor(id=r[0], distance=r[1], text=r[2]) for r in results
            ]
        elif mode == "bm25" and hasattr(self.store, "hybrid_search"):
            # bm25-only: alpha=0
            results = self.store.hybrid_search(
                embedding, query_text=text, k=k, alpha=0.0
            )
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
        geolocation_client: Optional[GeolocationClient] = None,
        weather_client: Optional[WeatherClient] = None,
        crypto_client: Optional[CryptoClient] = None,
        forex_client: Optional[ForexClient] = None,
        workflow: Optional[MeetingAssistantWorkflow] = None,
        metrics_collector: Optional[MetricCollector] = None,
    ) -> None:
        self.app = EmbeddingApp(emb_service, vector_store)
        self.rag_agent = rag_agent
        self.calendar_service = calendar_service
        self.geolocation_client = geolocation_client
        self.weather_client = weather_client
        self.crypto_client = crypto_client
        self.forex_client = forex_client
        self.workflow = workflow
        self.metrics_collector = metrics_collector

    def _print_intro(self) -> None:
        intro = (
            "Embedding CLI with RAG - stores documents and performs retrieval + generation.\n"
            "Type your prompt and press Enter. Type 'exit' to quit.\n"
            "Commands: '/mode hybrid|semantic|bm25', '/k N', '/alpha X', '/rag on|off'"
        )
        if self.calendar_service:
            intro += "\nCalendar: '/calendar events', '/calendar today', '/calendar range START END'"
        if self.geolocation_client:
            intro += "\nGeo: '/geo IP_ADDRESS' (e.g., '/geo 8.8.8.8')"
        if self.weather_client:
            intro += "\nWeather: '/weather CITY'"
        if self.crypto_client:
            intro += "\nCrypto: '/crypto SYMBOL' (e.g., '/crypto bitcoin')"
        if self.forex_client:
            intro += "\nForex: '/forex BASE TARGET' (e.g., '/forex USD EUR')"
        if self.workflow:
            intro += "\nWorkflow: '/workflow your request' (LangGraph multi-step orchestration)"
        if self.metrics_collector:
            intro += "\nMetrics: '/metrics' (show API call statistics), '/metrics export' (save to file)"
        print(textwrap.dedent(intro))

    def _print_results(self, uid: str, neighbors: List[Neighbor]) -> None:
        print("\nStored prompt id:", uid)
        print("Retrieved nearest neighbors:")
        if not neighbors:
            print("  (no results)")
            return

        for i, n in enumerate(neighbors, start=1):
            print(f'{i}. (score={n.distance:.6f}) "{n.text}"')

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
                print(
                    f"    {n.text[:200]}..." if len(n.text) > 200 else f"    {n.text}"
                )

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
            if event.get("location"):
                print(f"    Location: {event.get('location')}")
            if event.get("description"):
                desc = event.get("description")[:100]
                print(f"    Description: {desc}...")

    def _print_geolocation(self, location_data: dict) -> None:
        """Print geolocation information."""
        if not location_data:
            print("Geolocation lookup failed.")
            return

        print(f"\n--- IP Geolocation ---")
        print(f"IP Address: {location_data.get('ip')}")
        print(f"Country: {location_data.get('country')}")
        print(f"Region: {location_data.get('region')}")
        print(f"City: {location_data.get('city')}")
        print(
            f"Coordinates: {location_data.get('latitude')}, {location_data.get('longitude')}"
        )
        print(f"Timezone: {location_data.get('timezone')}")
        if location_data.get("isp"):
            print(f"ISP: {location_data.get('isp')}")
        if location_data.get("organization"):
            print(f"Organization: {location_data.get('organization')}")

    def _print_weather(self, weather_data: dict) -> None:
        """Print weather information."""
        if not weather_data:
            print("Weather lookup failed.")
            return

        print(f"\n--- Weather ---")
        print(f"City: {weather_data.get('city')}, {weather_data.get('country')}")
        print(f"Temperature: {weather_data.get('temperature')}°C")
        print(f"Feels Like: {weather_data.get('feels_like')}°C")
        print(f"Condition: {weather_data.get('description', 'N/A')}")
        print(f"Humidity: {weather_data.get('humidity')}%")
        print(f"Wind Speed: {weather_data.get('wind_speed')} m/s")
        print(f"Clouds: {weather_data.get('clouds')}%")
        print(f"Timestamp: {weather_data.get('timestamp')}")

    def _print_crypto_price(self, crypto_data: dict) -> None:
        """Print cryptocurrency price information."""
        if not crypto_data:
            print("Crypto price lookup failed.")
            return

        print(f"\n--- {crypto_data.get('symbol').upper()} Price ---")
        print(
            f"Price: {crypto_data.get('price')} {crypto_data.get('currency').upper()}"
        )
        print(f"24h Change: {crypto_data.get('change_24h')}%")
        print(
            f"Market Cap: {crypto_data.get('market_cap')} {crypto_data.get('currency').upper()}"
        )
        print(
            f"24h Volume: {crypto_data.get('volume_24h')} {crypto_data.get('currency').upper()}"
        )
        print(f"Updated: {crypto_data.get('timestamp')}")

    def _print_forex_rate(self, forex_data: dict) -> None:
        """Print exchange rate information."""
        if not forex_data:
            print("Exchange rate lookup failed.")
            return

        print(f"\n--- Exchange Rate ---")
        print(f"{forex_data.get('base')} → {forex_data.get('target')}")
        print(
            f"Rate: 1 {forex_data.get('base')} = {forex_data.get('rate')} {forex_data.get('target')}"
        )
        print(f"Date: {forex_data.get('timestamp')}")

    def _print_metrics_summary(self, summary) -> None:
        """Print AI metrics summary."""
        print("\n--- AI Metrics Summary ---")
        print(f"Total Inferences: {summary.total_inferences}")
        print(f"Total Tokens In: {summary.total_tokens_in:,}")
        print(f"Total Tokens Out: {summary.total_tokens_out:,}")
        print(f"Total Cost: ${summary.total_cost_usd:.6f}")

        print(
            f"\nError Rate: {summary.error_rate:.2f}% ({summary.total_errors} errors)"
        )

        print(f"\nLatency Statistics (milliseconds):")
        print(f"  p95: {summary.latency_p95_ms:.2f}ms")
        print(f"  p50 (median): {summary.latency_p50_ms:.2f}ms")
        print(f"  Mean: {summary.latency_mean_ms:.2f}ms")

        if summary.agent_execution_latency_mean_ms > 0:
            print(f"\nAgent Execution Latency (milliseconds):")
            print(f"  p95: {summary.agent_execution_latency_p95_ms:.2f}ms")
            print(f"  Mean: {summary.agent_execution_latency_mean_ms:.2f}ms")

        # Breakdown by operation type
        if summary.by_operation:
            print(f"\nBreakdown by Operation:")
            for op_type, stats in summary.by_operation.items():
                print(f"  {op_type}:")
                print(f"    Calls: {stats['count']}")
                print(f"    Tokens In: {stats['tokens_in']:,}")
                print(f"    Tokens Out: {stats['tokens_out']:,}")
                print(f"    Cost: ${stats['cost_usd']:.6f}")
                print(f"    Latency p95: {stats.get('latency_p95_ms', 0):.2f}ms")

        # Breakdown by model
        if summary.by_model:
            print(f"\nBreakdown by Model:")
            for model, stats in summary.by_model.items():
                print(f"  {model}:")
                print(f"    Calls: {stats['count']}")
                print(f"    Cost: ${stats['cost_usd']:.6f}")
                print(f"    Latency p95: {stats.get('latency_p95_ms', 0):.2f}ms")

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
                        events = self.calendar_service.get_upcoming_events(
                            max_results=5
                        )
                        self._print_calendar_events(events)
                    elif cal_cmd == "today":
                        from datetime import datetime, timedelta

                        today = datetime.now().strftime("%Y-%m-%d")
                        tomorrow = (datetime.now() + timedelta(days=1)).strftime(
                            "%Y-%m-%d"
                        )
                        events = self.calendar_service.get_events_by_date(
                            today, tomorrow
                        )
                        print(f"Events for today ({today}):")
                        self._print_calendar_events(events)
                    elif cal_cmd.startswith("range "):
                        parts = cal_cmd.split(maxsplit=2)
                        if len(parts) >= 3:
                            start_date = parts[1]
                            end_date = parts[2]
                            events = self.calendar_service.get_events_by_date(
                                start_date, end_date
                            )
                            print(f"Events from {start_date} to {end_date}:")
                            self._print_calendar_events(events)
                        else:
                            print("Usage: /calendar range YYYY-MM-DD YYYY-MM-DD")
                    else:
                        print(
                            "Calendar commands: /calendar events, /calendar today, /calendar range START END"
                        )
                except Exception as exc:
                    print(f"Calendar error: {exc}")
                continue

            if text.startswith("/geo "):
                if not self.geolocation_client:
                    print("Geolocation service not available")
                    continue

                try:
                    ip_address = text.split(maxsplit=1)[1].strip()
                    location_data = self.geolocation_client.get_location_from_ip(
                        ip_address
                    )
                    self._print_geolocation(location_data)
                except Exception as exc:
                    print(f"Geolocation error: {exc}")
                continue

            if text.startswith("/weather "):
                if not self.weather_client:
                    print("Weather service not available")
                    continue

                try:
                    city = text.split(maxsplit=1)[1].strip()
                    weather_data = self.weather_client.get_weather(city)
                    self._print_weather(weather_data)
                except Exception as exc:
                    print(f"Weather error: {exc}")
                continue

            if text.startswith("/crypto "):
                if not self.crypto_client:
                    print("Crypto service not available")
                    continue

                try:
                    symbol = text.split(maxsplit=1)[1].strip()
                    crypto_data = self.crypto_client.get_crypto_price(symbol)
                    self._print_crypto_price(crypto_data)
                except Exception as exc:
                    print(f"Crypto error: {exc}")
                continue

            if text.startswith("/forex "):
                if not self.forex_client:
                    print("Forex service not available")
                    continue

                try:
                    parts = text.split(maxsplit=2)
                    if len(parts) >= 3:
                        base = parts[1].strip()
                        target = parts[2].strip()
                        forex_data = self.forex_client.get_exchange_rate(base, target)
                        self._print_forex_rate(forex_data)
                    else:
                        print("Usage: /forex BASE TARGET (e.g., /forex USD EUR)")
                except Exception as exc:
                    print(f"Forex error: {exc}")
                continue

            if text.startswith("/workflow "):
                if not self.workflow:
                    print("LangGraph workflow not available")
                    continue

                try:
                    user_request = text.split(maxsplit=1)[1].strip()
                    print("\n--- Starting LangGraph Workflow ---")
                    result = self.workflow.run(user_request)

                    # Print workflow results
                    print("\nWorkflow Results:")
                    print(
                        f"Steps Executed: {result['executed_steps']}/{len(result['execution_plan'])}"
                    )

                    if result["meeting_summary"]:
                        print(f"\nMeeting Summary:\n{result['meeting_summary']}")

                    if result["final_answer"]:
                        print(f"\nFinal Answer:\n{result['final_answer']}")

                    if result["errors"]:
                        print("\nWarnings/Errors:")
                        for error in result["errors"]:
                            print(f"  ⚠ {error}")

                except Exception as exc:
                    print(f"Workflow error: {exc}")
                continue

            if text.startswith("/metrics"):
                if not self.metrics_collector:
                    print("Metrics not available")
                    continue

                try:
                    cmd_parts = text.split(maxsplit=1)
                    cmd = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

                    if cmd == "export":
                        filepath = "./metrics_export.json"
                        self.metrics_collector.export(filepath)
                        print(f"Metrics exported to {filepath}")
                    else:
                        # Default: display metrics summary
                        summary = self.metrics_collector.get_summary()
                        self._print_metrics_summary(summary)
                except Exception as exc:
                    print(f"Metrics error: {exc}")
                continue

            uid, neighbors = self.app.process_query(text, k=k, mode=mode, alpha=alpha)
            if rag_enabled and self.rag_agent:
                # Convert neighbors to format expected by RAG agent
                doc_tuples = [(n.id, n.distance, n.text) for n in neighbors]
                response = self.rag_agent.generate_response(text, doc_tuples)
                self._print_rag_response(uid, neighbors, response)
            else:
                self._print_results(uid, neighbors)

    def process_directory(
        self, data_dir: str, k: int = 3, mode: str = "hybrid", alpha: float = 0.5
    ) -> None:
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

        print(
            f"Processing {len(files)} files from {data_dir} (mode={mode}, k={k}, alpha={alpha})"
        )
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

            uid, neighbors = self.app.process_query(
                content, k=k, mode=mode, alpha=alpha
            )
            print("\nFile:", fname)
            self._print_results(uid, neighbors)
