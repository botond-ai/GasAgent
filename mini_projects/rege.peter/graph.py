from __future__ import annotations

import re
import unicodedata
from datetime import date as date_type
from datetime import datetime
from typing import Any, Callable, TypedDict, cast

from calendar_api import fetch_calendar_context
from llm_client import llm_extract_json_list, llm_summarize
from prompts import ACTION_ITEMS_PROMPT_HU, DECISIONS_PROMPT_HU, SUMMARY_PROMPT_HU
from schemas import validate_public_output


class AgentState(TypedDict, total=False):
    raw_text: str
    meeting_date: str
    country: str
    calendar_context: dict[str, Any]
    summary: str
    decisions: list[str]
    action_items: list[dict[str, Any]]
    output: dict[str, Any]
    llm_error: str


def build_graph() -> Any:
    """
    Build the LangGraph StateGraph with mandatory node order:
    extract_metadata → calendar_api → summarize → extract_decisions → extract_action_items → build_output
    """
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "LangGraph is not available. Install 'langgraph' or use the linear engine."
        ) from exc

    graph = StateGraph(AgentState)
    graph.add_node("extract_metadata", extract_metadata_node)
    graph.add_node("calendar_api", calendar_api_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("extract_decisions", extract_decisions_node)
    graph.add_node("extract_action_items", extract_action_items_node)
    graph.add_node("build_output", build_output_node)

    graph.add_edge(START, "extract_metadata")
    graph.add_edge("extract_metadata", "calendar_api")
    graph.add_edge("calendar_api", "summarize")
    graph.add_edge("summarize", "extract_decisions")
    graph.add_edge("extract_decisions", "extract_action_items")
    graph.add_edge("extract_action_items", "build_output")
    graph.add_edge("build_output", END)
    return graph.compile()


def run_langgraph(state: AgentState) -> AgentState:
    app = build_graph()
    # LangGraph returns a dict-like state; cast for our typed interface.
    result = app.invoke(state)
    return cast(AgentState, result)


def run_linear(state: AgentState) -> AgentState:
    """
    Linear fallback runner that preserves the mandatory node order.
    This keeps the project executable even if LangGraph is not installed yet.
    """
    state = extract_metadata_node(state)
    state = calendar_api_node(state)
    state = summarize_node(state)
    state = extract_decisions_node(state)
    state = extract_action_items_node(state)
    state = build_output_node(state)
    return state


def extract_metadata_node(state: AgentState) -> AgentState:
    raw_text = (state.get("raw_text") or "").strip()
    if not raw_text:
        raise ValueError("Missing state.raw_text")

    # Allow CLI override, otherwise extract.
    if not state.get("meeting_date"):
        state["meeting_date"] = _extract_meeting_date(raw_text)
    return state


def calendar_api_node(state: AgentState) -> AgentState:
    meeting_date = state.get("meeting_date")
    if not isinstance(meeting_date, str) or not meeting_date:
        raise ValueError("Missing state.meeting_date")
    country = state.get("country", "HU")
    if not isinstance(country, str) or not country.strip():
        country = "HU"
    year = date_type.fromisoformat(meeting_date).year
    state["calendar_context"] = fetch_calendar_context(meeting_date, year, country)
    return state


def summarize_node(state: AgentState) -> AgentState:
    raw_text = state["raw_text"]
    if state.get("use_llm"):
        try:
            summary = llm_summarize(SUMMARY_PROMPT_HU, raw_text)
            state["summary"] = summary if summary else "Summary unavailable."
            return state
        except Exception as exc:
            state["llm_error"] = f"LLM summarize failed: {exc}"
    # Simple deterministic summary: join first few content lines without speaker labels.
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    content_lines: list[str] = []
    for line in lines:
        if re.match(r"^[A-Za-z].*:\s*$", line):
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9 _-]{0,40}:\s*$", line):
            continue
        content_lines.append(line)
    summary = " ".join(content_lines[:4]).strip()
    summary_bullets = _extract_summary_bullets(raw_text)
    if summary_bullets:
        bullets_text = "; ".join(_clean_line(bullet).rstrip(".") for bullet in summary_bullets)
        summary = summary.rstrip(".")
        summary = f"{summary}. Összefoglalva: {bullets_text}."
    state["summary"] = summary if summary else "Summary unavailable."
    return state


def extract_decisions_node(state: AgentState) -> AgentState:
    raw_text = state["raw_text"]
    decisions: list[str] = []
    meeting_date = state.get("meeting_date")
    if state.get("use_llm"):
        try:
            llm_items = llm_extract_json_list(DECISIONS_PROMPT_HU, raw_text)
            decisions = [str(item).strip() for item in llm_items if str(item).strip()]
            state["decisions"] = _dedupe_keep_order(decisions)[:10]
            return state
        except Exception as exc:
            state["llm_error"] = f"LLM decisions failed: {exc}"
    summary_bullets = _extract_summary_bullets(raw_text)
    for bullet in summary_bullets:
        if _classify_summary_bullet(bullet, meeting_date=meeting_date) == "decision":
            decisions.append(_clean_line(bullet))

    lines = raw_text.splitlines()
    for idx, line in enumerate(lines):
        candidate = line.strip()
        if not candidate:
            continue
        normalized = _normalize_text(candidate)
        if "akciopont" in normalized:
            continue

        if "dontes" in normalized and "rogzit" in normalized:
            block = _collect_decision_block(lines, idx + 1)
            if block:
                candidate_decision = _clean_line(block)
                if not _decision_exists(decisions, candidate_decision):
                    decisions.append(candidate_decision)
            continue
        if candidate.endswith(":"):
            continue
        if normalized.startswith("rendben") and "rogzit" in normalized and "dontes" not in normalized:
            continue

        if any(
            token in normalized
            for token in [
                "agreed",
                "we decided",
                "decision",
                "we should",
                "we will",
                "let's",
                "akkor dontes",
                "donto",
                "megegyeztunk",
            ]
        ):
            candidate_decision = _clean_line(candidate)
            if not _decision_exists(decisions, candidate_decision):
                decisions.append(candidate_decision)

    state["decisions"] = _dedupe_keep_order(decisions)[:10]
    return state


def extract_action_items_node(state: AgentState) -> AgentState:
    raw_text = state["raw_text"]
    action_items: list[dict[str, Any]] = []
    current_speaker: str | None = None
    meeting_date = state.get("meeting_date")
    if state.get("use_llm"):
        try:
            llm_items = llm_extract_json_list(ACTION_ITEMS_PROMPT_HU, raw_text)
            normalized_items: list[dict[str, Any]] = []
            for item in llm_items:
                if not isinstance(item, dict):
                    continue
                task = item.get("task")
                if not isinstance(task, str) or not task.strip():
                    continue
                normalized: dict[str, Any] = {
                    "task": _clean_line(task),
                    "priority": item.get("priority", "medium"),
                }
                owner = item.get("owner")
                if isinstance(owner, str) and owner.strip():
                    normalized["owner"] = owner.strip()
                due_date = item.get("due_date")
                if isinstance(due_date, str) and due_date.strip():
                    normalized["due_date"] = due_date.strip()
                normalized_items.append(normalized)
            state["action_items"] = _dedupe_action_items(normalized_items)[:20]
            return state
        except Exception as exc:
            state["llm_error"] = f"LLM action items failed: {exc}"
    last_action_index: dict[str, int] = {}
    last_action_global_index: int | None = None
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        speaker_match = _SPEAKER_RE.match(stripped)
        if speaker_match:
            speaker_name = speaker_match.group(1)
            if _normalize_text(speaker_name).startswith("osszefoglal"):
                continue
            current_speaker = speaker_name
            continue

        normalized = _normalize_text(stripped)
        is_action_line = any(
            phrase in normalized
            for phrase in [
                "i can",
                "i will",
                "i'll",
                "i\u2019ll",
                "i shall",
                "i can take care",
                "vallalom",
                "megcsinalom",
                "megcsinaljuk",
                "en csinalom",
                "en keszitem",
                "keszithetek",
                "keszitek",
                "kesziteni",
                "csinalok",
                "csinal",
            ]
        )
        if is_action_line:
            item: dict[str, Any] = {"task": _clean_line(stripped), "priority": "medium"}
            if current_speaker:
                item["owner"] = current_speaker
            due = _extract_due_date(stripped, meeting_date=meeting_date)
            if due:
                item["due_date"] = due
            action_items.append(item)
            if current_speaker:
                last_action_index[current_speaker] = len(action_items) - 1
            last_action_global_index = len(action_items) - 1
            continue

        due = _extract_due_date(stripped, meeting_date=meeting_date)
        if due and current_speaker and current_speaker in last_action_index:
            idx = last_action_index[current_speaker]
            if "due_date" not in action_items[idx]:
                action_items[idx]["due_date"] = due
            continue

        if due and last_action_global_index is not None and _is_due_context(stripped):
            if "due_date" not in action_items[last_action_global_index]:
                action_items[last_action_global_index]["due_date"] = due
            continue

        if due and _is_due_context(stripped):
            action_items.append(
                {
                    "task": _clean_line(stripped),
                    "owner": current_speaker,
                    "due_date": due,
                    "priority": "medium",
                }
            )

    for bullet in _extract_summary_bullets(raw_text):
        if _classify_summary_bullet(bullet, meeting_date=meeting_date) != "action":
            continue
        due = _extract_due_date(bullet, meeting_date=meeting_date)
        if due and _assign_due_to_existing(action_items, bullet, due):
            continue
        item: dict[str, Any] = {"task": _clean_line(bullet), "priority": "medium"}
        if due:
            item["due_date"] = due
        action_items.append(item)

    state["action_items"] = _dedupe_action_items(action_items)[:20]
    return state


def build_output_node(state: AgentState) -> AgentState:
    meeting_date = state["meeting_date"]
    calendar_context = state.get("calendar_context") or {}
    is_holiday = bool(calendar_context.get("is_holiday", False))
    holiday_name = calendar_context.get("holiday_name")
    if holiday_name is not None and not isinstance(holiday_name, str):
        holiday_name = None

    output = {
        "meeting": {
            "date": meeting_date,
            "is_holiday": is_holiday,
            "holiday_name": holiday_name,
            "summary": state.get("summary") or "Summary unavailable.",
        },
        "decisions": state.get("decisions") or [],
        "action_items": state.get("action_items") or [],
    }

    validated = validate_public_output(output).to_dict()
    state["output"] = validated
    return state


_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
    "januar": 1,
    "februar": 2,
    "marcius": 3,
    "aprilis": 4,
    "majus": 5,
    "junius": 6,
    "julius": 7,
    "augusztus": 8,
    "szeptember": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


def _extract_meeting_date(text: str) -> str:
    # Prefer explicit ISO date anywhere in the transcript.
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(1)

    # Try month-name patterns (e.g., "December 9" / "December 9, 2025").
    normalized = _normalize_text(text)
    month_pattern = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    m = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b", normalized)
    if m:
        month = _MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        return date_type(year, month, day).isoformat()

    # If nothing found, default to today for a stable runnable pipeline.
    return date_type.today().isoformat()


def _extract_due_date(text: str, meeting_date: str | None = None) -> str | None:
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(1)

    normalized = _normalize_text(text)
    month_pattern = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    m = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})\b", normalized)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    day = int(m.group(2))
    year = datetime.now().year
    if meeting_date:
        try:
            meeting_dt = date_type.fromisoformat(meeting_date)
            year = meeting_dt.year
            if month < meeting_dt.month:
                year = meeting_dt.year + 1
        except ValueError:
            pass
    try:
        return date_type(year, month, day).isoformat()
    except ValueError:
        return None


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.lower()


def _clean_line(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.rstrip(",;:")
    return cleaned


def _extract_summary_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    lines = text.splitlines()
    capture = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if capture:
                break
            continue
        normalized = _normalize_text(stripped)
        if normalized.startswith("osszefoglalva"):
            capture = True
            continue
        if capture:
            if _SPEAKER_RE.match(stripped):
                break
            if stripped.startswith("-") or stripped.startswith("•"):
                bullets.append(stripped.lstrip("-• ").strip())
    return bullets


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_action_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index_by_task: dict[str, int] = {}
    for item in items:
        task_key = _normalize_text(str(item.get("task", "")))
        if not task_key:
            continue
        if task_key in index_by_task:
            existing = result[index_by_task[task_key]]
            if existing.get("owner") is None and item.get("owner") is not None:
                existing["owner"] = item["owner"]
            if existing.get("due_date") is None and item.get("due_date") is not None:
                existing["due_date"] = item["due_date"]
            continue
        index_by_task[task_key] = len(result)
        result.append(item)
    return result


_SPEAKER_RE = re.compile(
    r"^([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű][A-Za-z0-9ÁÉÍÓÖŐÚÜŰáéíóöőúüű _-]{0,40}):\s*$"
)


_ACTION_KEYWORDS = [
    "frissites",
    "dokumentacio",
    "osszefoglalo",
    "sablon",
    "elemzes",
    "teljesitmeny",
    "keszit",
    "kesziteni",
    "elkeszul",
    "hatarido",
    "csinal",
]


def _classify_summary_bullet(bullet: str, meeting_date: str | None = None) -> str:
    normalized = _normalize_text(bullet)
    if any(token in normalized for token in ["sprint", "lezaras", "stabilizalas"]):
        return "decision"
    has_date = _extract_due_date(bullet, meeting_date=meeting_date) is not None
    if any(key in normalized for key in _ACTION_KEYWORDS):
        return "action"
    if "sprint" in normalized and ("lezaras" in normalized or "stabilizalas" in normalized):
        return "decision"
    if has_date:
        return "action"
    return "decision"


def _is_due_context(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(
        token in normalized
        for token in [
            "hatarido",
            "hatarideje",
            "legkesobb",
            "elkeszul",
            "elkeszulok",
            "kesz",
            "keszul",
            "kesz lesz",
        ]
    )


def _decision_exists(decisions: list[str], candidate: str) -> bool:
    if not decisions:
        return False
    cand_norm = _normalize_text(candidate)
    cand_date = _extract_due_date(candidate, meeting_date=None)
    cand_md = _extract_month_day(candidate)
    for existing in decisions:
        existing_norm = _normalize_text(existing)
        if cand_norm == existing_norm:
            return True
        if "sprint" in cand_norm and "sprint" in existing_norm:
            if "lezaras" in cand_norm and "lezaras" in existing_norm:
                existing_md = _extract_month_day(existing)
                if cand_md and existing_md and cand_md == existing_md:
                    return True
            if cand_date and cand_date in existing:
                return True
    return False


def _assign_due_to_existing(items: list[dict[str, Any]], bullet: str, due: str) -> bool:
    normalized_bullet = _normalize_text(bullet)
    if not any(key in normalized_bullet for key in _ACTION_KEYWORDS):
        return False
    handled = False
    generic_tokens = ["ezt is", "csinalnam meg", "csinalnam", "megcsinalnam", "megcsinalom"]
    strict_keywords = [key for key in _ACTION_KEYWORDS if key != "csinal"]
    matched_keyword = False
    for item in items:
        task_norm = _normalize_text(str(item.get("task", "")))
        if any(key in task_norm and key in normalized_bullet for key in _ACTION_KEYWORDS):
            if "due_date" not in item:
                item["due_date"] = due
            matched_keyword = True
            handled = True
    if matched_keyword:
        return handled
    for item in items:
        task_norm = _normalize_text(str(item.get("task", "")))
        if any(token in task_norm for token in generic_tokens) and not any(
            key in task_norm for key in strict_keywords
        ):
            item["task"] = _clean_line(bullet)
            if "due_date" not in item:
                item["due_date"] = due
            handled = True
    return handled


def _collect_decision_block(lines: list[str], start_idx: int) -> str | None:
    parts: list[str] = []
    for j in range(start_idx, len(lines)):
        candidate = lines[j].strip()
        if not candidate:
            if parts:
                break
            continue
        if _SPEAKER_RE.match(candidate):
            break
        if candidate.startswith("-") or candidate.startswith("•"):
            candidate = candidate.lstrip("-• ").strip()
        parts.append(candidate)
    return " ".join(parts).strip() if parts else None


def _extract_month_day(text: str) -> tuple[int, int] | None:
    normalized = _normalize_text(text)
    month_pattern = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    m = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})\b", normalized)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    day = int(m.group(2))
    return (month, day)


def _next_content_line(lines: list[str], start_idx: int) -> str | None:
    for j in range(start_idx, len(lines)):
        candidate = lines[j].strip()
        if not candidate:
            continue
        if _SPEAKER_RE.match(candidate):
            continue
        if candidate.startswith("-") or candidate.startswith("•"):
            return candidate.lstrip("-• ").strip()
        return candidate
    return None
