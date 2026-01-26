"""
Sequential Chat Test Script
Sends questions from test_questions.md to the API and records metrics.

Usage:
    python test_chat_sequence.py           # Run all questions
    python test_chat_sequence.py -n 5      # Run first 5 questions
    python test_chat_sequence.py --limit 3 # Run first 3 questions
"""
import requests
import time
import json
import argparse
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


# Configuration
API_BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{API_BASE_URL}/api/chat/"
QUESTIONS_FILE = Path(__file__).parent / "test_questions.md"
RESULTS_FILE = Path(__file__).parent / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# Test user context
USER_CONTEXT = {
    "tenant_id": 1,
    "user_id": 1
}


def load_questions(file_path: Path) -> List[str]:
    """
    Load questions from markdown file.
    Skips empty lines and lines starting with #.
    """
    questions = []
    
    if not file_path.exists():
        raise FileNotFoundError(f"Questions file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and headers
            if line and not line.startswith('#'):
                questions.append(line)
    
    return questions


def send_question(query: str, session_id: str = None) -> Dict[str, Any]:
    """
    Send a single question to the chat API.
    Returns response data and metrics.
    """
    payload = {
        "query": query,
        "user_context": USER_CONTEXT
    }
    
    if session_id:
        payload["session_id"] = session_id
    
    start_time = time.time()
    
    try:
        response = requests.post(
            CHAT_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "response_time": elapsed_time,
                "status_code": response.status_code,
                "data": data,
                "error": None
            }
        else:
            return {
                "success": False,
                "response_time": elapsed_time,
                "status_code": response.status_code,
                "data": None,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "success": False,
            "response_time": elapsed_time,
            "status_code": None,
            "data": None,
            "error": str(e)
        }


def extract_metrics(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant metrics from API response.
    """
    if not response_data.get("data"):
        return {}
    
    data = response_data["data"]
    prompt_details = data.get("prompt_details", {})
    llm_cache_info = prompt_details.get("llm_cache_info", {})
    
    metrics = {
        "response_time": round(response_data["response_time"], 3),
        "status_code": response_data["status_code"],
        "session_id": data.get("session_id"),
        "iteration_count": llm_cache_info.get("iteration_count"),  # Not in top-level anymore
        "decision": None,  # Not exposed in API response
        "tool_calls": len(prompt_details.get("actions_taken", [])),
        "cache_hit_rate": llm_cache_info.get("cache_hit_rate", 0),
        "cached_tokens": llm_cache_info.get("cached_tokens", 0),
        "prompt_tokens": llm_cache_info.get("prompt_tokens", 0),
        "completion_tokens": llm_cache_info.get("completion_tokens", 0),
        "total_tokens": llm_cache_info.get("total_tokens", 0),
        "answer_preview": data.get("answer", "")[:100] + "..." if len(data.get("answer", "")) > 100 else data.get("answer", "")
    }
    
    return metrics


def print_metrics(question_num: int, question: str, metrics: Dict[str, Any], error: str = None):
    """
    Pretty print metrics for a single question.
    """
    print(f"\n{'='*80}")
    print(f"Question #{question_num}: {question}")
    print(f"{'='*80}")
    
    if error:
        print(f"❌ ERROR: {error}")
        return
    
    print(f"✅ Response Time: {metrics['response_time']}s")
    print(f"🔄 Iteration Count: {metrics['iteration_count']}")
    print(f"🎯 Decision: {metrics['decision']}")
    print(f"🔧 Tool Calls: {metrics['tool_calls']}")
    print(f"💾 Cache Hit Rate: {metrics['cache_hit_rate']:.1f}%")
    print(f"🪙 Tokens: {metrics['cached_tokens']}/{metrics['prompt_tokens']} cached (Total: {metrics['total_tokens']})")
    print(f"📝 Answer Preview: {metrics['answer_preview']}")


def main():
    """
    Main test execution flow.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sequential chat test with configurable question limit')
    parser.add_argument('-n', '--limit', type=int, default=None, 
                        help='Number of questions to test (default: all)')
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🚀 KNOWLEDGE ROUTER - SEQUENTIAL CHAT TEST")
    print("="*80)
    
    # Load questions
    try:
        questions = load_questions(QUESTIONS_FILE)
        total_questions = len(questions)
        print(f"\n📋 Loaded {total_questions} questions from {QUESTIONS_FILE.name}")
        
        # Apply limit if specified
        if args.limit is not None:
            questions = questions[:args.limit]
            print(f"⚠️  Testing only first {len(questions)} questions (limit: {args.limit})")
        else:
            print(f"✅ Testing all {len(questions)} questions")
            
    except Exception as e:
        print(f"❌ Failed to load questions: {e}")
        return
    
    # Results storage
    results = []
    # Use consistent session ID for cache testing
    session_id = str(uuid.uuid4())  # Generate once, reuse for all questions
    print(f"📌 Using Session ID: {session_id}")
    
    # Process each question sequentially
    for i, question in enumerate(questions, start=1):
        print(f"\n⏳ Sending question {i}/{len(questions)}...")
        
        response = send_question(question, session_id)
        
        if response["success"]:
            metrics = extract_metrics(response)
            print_metrics(i, question, metrics)
            
            results.append({
                "question_number": i,
                "question": question,
                "metrics": metrics,
                "success": True,
                "error": None
            })
        else:
            print_metrics(i, question, {}, error=response["error"])
            
            results.append({
                "question_number": i,
                "question": question,
                "metrics": {
                    "response_time": round(response["response_time"], 3),
                    "status_code": response.get("status_code")
                },
                "success": False,
                "error": response["error"]
            })
        
        # Small delay between questions
        if i < len(questions):
            time.sleep(0.5)
    
    # Save results
    print(f"\n{'='*80}")
    print("💾 Saving results...")
    
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "questions_file": str(QUESTIONS_FILE),
            "total_questions": len(questions),
            "session_id": session_id,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Results saved to: {RESULTS_FILE}")
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}")
    
    successful = sum(1 for r in results if r["success"])
    total_time = sum(r["metrics"].get("response_time", 0) for r in results)
    avg_cache_hit = sum(r["metrics"].get("cache_hit_rate", 0) for r in results if r["success"]) / max(successful, 1)
    
    print(f"✅ Successful: {successful}/{len(questions)}")
    print(f"⏱️  Total Time: {total_time:.2f}s")
    print(f"⏱️  Avg Response Time: {total_time/len(questions):.2f}s")
    print(f"💾 Avg Cache Hit Rate: {avg_cache_hit:.1f}%")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
