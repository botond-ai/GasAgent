from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from graph import run_langgraph, run_linear


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Meeting Assistant (LangGraph)")
    parser.add_argument("--input", required=True, help="Path to transcript (.txt/.md)")
    parser.add_argument("--country", required=True, help="Country code (e.g., HU)")
    parser.add_argument(
        "--date",
        required=False,
        help="Optional meeting date override (YYYY-MM-DD); otherwise extracted from transcript.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Optional output JSON path; defaults to outputs/output_<timestamp>.json",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "linear", "langgraph"],
        default="auto",
        help="Execution engine (default: auto).",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use local LLM (Ollama) for summary/decisions/actions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    transcript_text = input_path.read_text(encoding="utf-8")

    state = {"raw_text": transcript_text, "country": args.country}
    if args.date:
        state["meeting_date"] = args.date
    if args.use_llm:
        state["use_llm"] = True

    print("1/6 extract_metadata")
    print("2/6 calendar_api (public)")
    print("3/6 summarize")
    print("4/6 extract_decisions")
    print("5/6 extract_action_items")
    print("6/6 build_output")
    if args.engine == "linear":
        final_state = run_linear(state)
    elif args.engine == "langgraph":
        final_state = run_langgraph(state)
    else:
        try:
            final_state = run_langgraph(state)
        except Exception:
            final_state = run_linear(state)

    output_payload = final_state["output"]
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = outputs_dir / f"output_{ts}.json"

    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
