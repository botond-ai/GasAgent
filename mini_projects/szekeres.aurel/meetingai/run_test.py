import json
import importlib.util
from pathlib import Path

base = Path(__file__).parent
llm_path = base / "backend" / "services" / "llm.py"
transcript_path = base / "data" / "example_transcript.txt"

spec = importlib.util.spec_from_file_location("llm", str(llm_path))
llm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm)

transcript = transcript_path.read_text(encoding="utf-8")
res = llm.analyze_transcript(transcript)
print(json.dumps(res, ensure_ascii=False, indent=2))
