"""
Locust Load Test for Knowledge Router Chat API - FIXED PAYLOAD

BIZTONSÁGOS TERHELÉS:
- Kezdés: 1-5 user, 1 user/sec spawn rate
- Web UI: http://localhost:8089
- Ajánlott max: 10-20 concurrent user (1 worker setup)

FUTTATÁS:
    pip install locust
    python -m locust -f backend/debug/load_test_chat.py --host=http://localhost:8000

HEADLESS MÓD:
    python -m locust -f backend/debug/load_test_chat.py --host=http://localhost:8000 --headless --users 5 --spawn-rate 1 --run-time 2m
"""

from locust import HttpUser, task, between, events
import random
import logging
import uuid

# Locust log level csökkentés
logging.getLogger("locust").setLevel(logging.WARNING)


class ChatUser(HttpUser):
    """
    Szimulált user aki chat kéréseket küld.
    
    Viselkedés:
    - 2-5 sec várakozás kérések között (természetes user behavior)
    - EGY user = EGY session (valós behavior, history épül)
    - 30% RAG query (search_vectors/search_fulltext tool) → gpt-4.1
    - 25% Tool query (weather, currency) → gpt-4.1
    - 20% Complex question → gpt-4.1
    - 15% Simple chat → gpt-3.5-turbo
    - 10% Health check
    """
    
    wait_time = between(2, 5)  # 2-5 sec user "gondolkodási idő"
    
    def on_start(self):
        """User session start - EGYEDI session minden user-nek"""
        self.user_id = random.randint(1, 10)
        self.tenant_id = 1
        self.session_id = str(uuid.uuid4())  # Persistent session
        self.request_count = 0
        print(f"[USER {self.user_id}] Session created: {self.session_id}")
    
    @task(3)  # 30% RAG queries
    def rag_query(self):
        """RAG kérdések - specifikus keresések hogy search_vectors-t hívjanak"""
        questions = [
            "Hogyan működik a backpropagation a neurális hálókban?",
            "Mi a különbség a CNN és RNN között?",
            "Magyarázd el a transformer architektúrát",
            "Mik a gradient descent algoritmus főbb lépései?",
            "Hogyan működik a természetes nyelvfeldolgozás alapja?",
            "Mik az attention mechanism előnyei?"
        ]
        
        self.client.post(
            "/api/chat/",
            json={
                "query": random.choice(questions),
                "user_context": {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                },
                "session_id": self.session_id  # Persistent session!
            },
            timeout=40.0,
            name="/api/chat/ [RAG]"
        )
        self.request_count += 1
    
    @task(3)  # 25% Tool queries (weather, currency)
    def tool_query(self):
        """Tool hívást triggerelő kérdések (get_weather, get_currency)"""
        questions = [
            "Milyen időjárás lesz holnap Budapesten?",
            "Mi az aktuális euró árfolyam?",
            "Mennyi az USD/HUF árfolyam most?",
            "Esni fog ma?",
            "Mi az EUR/USD árfolyam tegnap?",
            "Milyen az időjárás előrejelzés a hétre Párizsban?",
            "Hány fok lesz holnap?",
            "Mi a CHF/HUF árfolyam?"
        ]
        
        self.client.post(
            "/api/chat/",
            json={
                "query": random.choice(questions),
                "user_context": {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                },
                "session_id": self.session_id  # Persistent session!
            },
            timeout=40.0,
            name="/api/chat/ [Tool]"
        )
        self.request_count += 1
    
    @task(2)  # 20% Complex reasoning
    def complex_question(self):
        """Összetett kérdések (gpt-4.1 reasoning, több lépés)"""
        questions = [
            "Hasonlítsd össze a supervised és unsupervised learning előnyeit és hátrányait",
            "Miért hatékony a transformer architektúra az NLP feladatokban?",
            "Milyen etikai kihívásokat vet fel az AI fejlődése?",
            "Hogyan működik a backpropagation algoritmus lépésről lépésre?",
            "Mi a különbség a generative és discriminative modellek között?",
            "Elemezd a reinforcement learning alkalmazási területeit"
        ]
        
        self.client.post(
            "/api/chat/",
            json={
                "query": random.choice(questions),
                "user_context": {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                },
                "session_id": self.session_id  # Persistent session!
            },
            timeout=40.0,
            name="/api/chat/ [Complex]"
        )
        self.request_count += 1
    
    @task(2)  # 15% Simple chat
    def simple_chat(self):
        """Egyszerű chat (gpt-3.5-turbo, direkt válasz, nincs tool hívás)"""
        questions = [
            "Szia!",
            "Mi a helyzet?",
            "Hello, be tudsz mutatni?",
            "Köszönöm szépen!",
            "Viszlát"
        ]
        
        self.client.post(
            "/api/chat/",
            json={
                "query": random.choice(questions),
                "user_context": {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                },
                "session_id": self.session_id  # Persistent session!
            },
            timeout=20.0,
            name="/api/chat/ [Simple]"
        )
        self.request_count += 1
    
    @task(1)  # 10% súly
    def health_check(self):
        """Health check endpoint (gyors, minimális terhelés)"""
        self.client.get(
            "/health",
            timeout=5.0,
            name="/health"
        )


# === EVENT LISTENERS (opcionális statisztikák) ===

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Teszt indításkor log"""
    print("\n" + "="*60)
    print("🚀 LOCUST LOAD TEST STARTED")
    print("="*60)
    print(f"Target: {environment.host}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Teszt leállításkor összegzés"""
    print("\n" + "="*60)
    print("🛑 LOCUST LOAD TEST STOPPED")
    print("="*60)
    
    if environment.stats.total.num_requests > 0:
        print(f"Total requests: {environment.stats.total.num_requests}")
        print(f"Total failures: {environment.stats.total.num_failures}")
        print(f"Avg response time: {environment.stats.total.avg_response_time:.2f}ms")
        print(f"Min response time: {environment.stats.total.min_response_time:.2f}ms")
        print(f"Max response time: {environment.stats.total.max_response_time:.2f}ms")
        print(f"Requests/sec: {environment.stats.total.total_rps:.2f}")
        print(f"Failure rate: {environment.stats.total.fail_ratio*100:.2f}%")
    else:
        print("No requests were made.")
    
    print("="*60 + "\n")
