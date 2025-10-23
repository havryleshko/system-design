from typing import Dict, Optional, Sequence
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from .state import State, MAX_ITERATIONS, CRITIC_TARGET, MAX_CRITIC_PASSES
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from functools import lru_cache
import json, os, math, requests
from jsonschema import validate as jsonschema_validate, ValidationError
from datetime import datetime
from app.storage.memory import add_event
from app.schemas.runs import RunEvent

@lru_cache(maxsize=4)
def make_brain(model: str | None = None) -> ChatOpenAI:
    model_name = model or os.getenv("CHAT_OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model_name)

BRAIN = make_brain()

def to_message(x: any) -> BaseMessage:
    if isinstance(x, BaseMessage):
        return x
    if isinstance(x, str):
        return HumanMessage(content=x)
    if isinstance(x, dict):
        role = (x.get("role") or "user").lower()
        content = x.get("content", "")
        return HumanMessage(content=content) if role in ("user", "human") else AIMessage(content=content)
    return HumanMessage(content=str(x))

def normalise(ms: Optional[list[any]]) -> list[BaseMessage]:
    return [to_message(m) for m in (ms or [])]

def get_content(m: any) -> str:
    return getattr(m, "content", m.get("content", "") if isinstance(m, dict) else str(m))

def last_human_text(messages: list[any]) -> str:
    ms = normalise(messages)
    text = ""
    for m in ms:
        if isinstance(m, HumanMessage):
            text = str(m.content or "")
        else:
            if isinstance(m, dict) and (m.get("role") or "user").lower() in ("user", "human"):
                text = str(m.get("content", "") or "")
    return text.strip()

def json_only(text: str) -> Optional[dict]:
    try:
        json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            return None
    return None

def call_brain(messages: list[any], *, run_id: str | None = None, node: str | None = None) -> str:
    ms = normalise(messages)
    r = BRAIN.invoke(ms)
    if run_id and node:
        log_token_usage(run_id, node, r)
    return getattr(r, "content", "") or ""


def call_brain_json(messages: list[any], *, run_id: str | None = None, node: str | None = None) -> dict:
    raw = call_brain(messages, run_id=run_id, node=node)
    try:
        return json.loads(raw)
    except Exception:
        data = json_only(raw)
        if data is None:
            raise ValueError("LLM response was not valid JSON")
        return data


def log_token_usage(run_id: str, node: str, response: BaseMessage) -> None:
    usage = getattr(response, "usage_metadata", None) or {}
    prompt_tokens = int(usage.get("input_tokens", 0))
    completion_tokens = int(usage.get("output_tokens", 0))
    total = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
    add_event(run_id, RunEvent(
        ts_ms=int(datetime.now().timestamp() * 1000),
        level="info",
        message=f"{node} tokens",
        data={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        }
    ))

def collect_recent_context(messages: list[BaseMessage], max_chars: int = 600) -> str:
    buf: list[str] = []
    count = 0
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            part = str(m.content or "").strip()
            if not part:
                continue
            if count + len(part) > max_chars:
                break
            buf.append(part)
            count += len(part)
        elif isinstance(m, AIMessage):
            break
    return "\n".join(reversed(buf)).strip()

def estimate_tokens(text: str) -> int:
    words = text.split()
    return max(1, math.ceil(len(words) / 0.75))


def trim_snippet(text: str, max_chars: int = 320) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _snippet_key(s: dict) -> tuple[str, str, str]:
    source_url = str(s.get("source_url") or "").strip().lower()
    cid = str(s.get("id") or "").strip()
    summary = trim_snippet(str(s.get("summary") or "").strip(), 200)
    return (source_url, cid, summary)


def _merge_snippet_lists(
    existing: Sequence[dict[str, str | int]] | None,
    incoming: Sequence[dict[str, str | int]] | None,
    *,
    max_total: int | None = None,
) -> list[dict[str, str | int]]:
    merged: list[dict[str, str | int]] = []
    seen: set[tuple[str, str, str]] = set()

    for s in (existing or []):
        k = _snippet_key(s)
        if k in seen:
            continue
        merged.append(s)
        seen.add(k)

    for s in (incoming or []):
        k = _snippet_key(s)
        if k in seen:
            continue
        merged.append(s)
        seen.add(k)

    if max_total is None:
        try:
            max_total = int(os.getenv("GROUNDING_MAX_SNIPPETS", "6") or 6)
        except Exception:
            max_total = 6

    return merged[: max(1, int(max_total))]


def embed_query(text: str) -> Optional[list[float]]:
    model_name = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        embedder = OpenAIEmbeddings(model=model_name)
        return embedder.embed_query(text)
    except Exception:
        return None


def kb_search(state: State) -> Dict[str, any]:
    goal = (state.get("goal") or "").strip()
    latest_user = last_human_text(state.get("messages", []))
    query_parts = [goal]
    if latest_user and latest_user.lower() != goal.lower():
        query_parts.append(latest_user)
    query = " ".join(part for part in query_parts if part).strip()
    if not query:
        return {}

    embedding = embed_query(query)
    if not embedding:
        return {}

    supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
    rpc_name = os.getenv("KB_MATCH_RPC", "match_playbook_chunks")
    top_k = int(os.getenv("KB_TOP_K", "3") or 3)
    if not supabase_url or not supabase_key:
        return {}

    payload = {
        "query_embedding": embedding,
        "match_count": top_k,
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    url = f"{supabase_url}/rest/v1/rpc/{rpc_name}"
    snippets: list[dict[str, str | int]] = []
    qualified = 0
    threshold = float(os.getenv("KB_SIM_THRESHOLD", "0.78") or 0.78)
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        results = resp.json() or []
    except Exception:
        results = []

    for idx, row in enumerate(results[:top_k], start=1):
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        summary = trim_snippet(content, 320)
        sim = float(row.get("similarity") or 0.0)
        if sim >= threshold:
            qualified += 1
        topic = str(row.get("topic") or row.get("category") or "kb").strip()
        title = str(row.get("title") or topic.title() or "Playbook").strip()
        cid = f"[KB{idx}]"
        snippets.append({
            "id": cid,
            "summary": summary,
            "source_url": f"kb://{topic}/{title}",
            "token_count": estimate_tokens(summary),
        })

    metadata = state.setdefault("metadata", {})
    metadata.update({
        "kb_hits": len(snippets),
        "kb_qualified": qualified,
        "kb_threshold": threshold,
    })

    if not snippets:
        return {"metadata": metadata}

    # Merge with any existing global snippets/citations in state to avoid overwrite by other nodes
    existing_snippets = state.get("grounding_snippets", []) or []
    existing_citations = state.get("citations", []) or []
    merged_snippets = _merge_snippet_lists(existing_snippets, snippets)
    merged_citations = _merge_snippet_lists(existing_citations, snippets)

    return {
        "grounding_snippets": merged_snippets,
        "citations": merged_citations,
        # Source-specific outputs for introspection/debugging
        "kb_grounding_snippets": snippets,
        "kb_citations": snippets,
        "metadata": metadata,
    }


def tavily_search(
    query: str,
    *,
    max_snippets: int = 2,
    api_key: Optional[str] = None,
    timeout: int = 10,
) -> list[dict[str, str | int]]:
    if not api_key:
        return []
    url = "https://api.tavily.com/search"
    payload = {
        "query": query,
        "max_results": max_snippets,
        "search_depth": "advanced",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json() or {}
    results: Sequence[dict] = data.get("results") or []
    snippets: list[dict[str, str | int]] = []
    seen_urls: set[str] = set()
    for item in results:
        url_value = str(item.get("url") or "").strip()
        if url_value in seen_urls:
            continue
        raw_content = str(item.get("content") or item.get("snippet") or "").strip()
        if not raw_content:
            continue
        summary = trim_snippet(raw_content)
        token_count = estimate_tokens(summary)
        snippets.append({
            "source_url": url_value,
            "summary": summary,
            "token_count": token_count,
        })
        seen_urls.add(url_value)
    return snippets[:max_snippets]

def tool_call(state: State) -> Dict[str, any]:  # For later
    return {}

def intent(state: State) -> Dict[str, any]:
    user_text = last_human_text(state.get("messages", []))
    sys = SystemMessage(content=(
        "You are a system design expert. You extract system design intent from an input and see what required fields are missing. \n"
        "Required fields: ['use_case', 'constraints'] \n"
        "Output strictly as compact JSON with the keys: goal (str), missing_fields (array of strings) \n"
    ))
    human = HumanMessage(content=f"Input:\n{user_text}\n\nReturn JSON only")
    raw = call_brain([sys, human])
    data = json_only(raw) or {}
    goal = str(data.get("goal") or user_text).strip()
    required = ['use_case', 'constraints']
    missing = [m for m in (data.get('missing_fields') or []) if str(m).lower() in required]
    if not missing:
        lowered = goal.lower()
        if 'use_case' not in lowered:
            missing.append('use_case')
        if 'constraints' not in lowered:
            missing.append('constraints')
    return {"goal": goal, "missing_fields": missing}

def clarifier(state: State) -> Dict[str, any]:
    missing = state.get('missing_fields', []) or []
    it = int(state.get("iterations", 0) or 0)
    if missing and it < MAX_ITERATIONS:
        need = ", ".join(str(x) for x in missing)
        sys = SystemMessage(content=(
            "As a system design expert, craft a single concise clarifying question to collect the missing items for a system design task"
        ))
        human = HumanMessage(content=f"Ask for {need}. Keep short & specific")
        question = call_brain([sys, human]).strip() or f"Please provide {need}"
        state.setdefault("metadata", {})
        state["metadata"].setdefault("cached_clarifier", question)
        return {
            "messages": [AIMessage(content=question)],
            "iterations": it + 1
        }
    return {}

def planner(state: State) -> Dict[str, any]:
    goal = state.get("goal", "") or ""
    constraints = ""
    user_reply = last_human_text(state.get("messages", []))
    if user_reply and user_reply.lower() != goal.lower():
        constraints = user_reply
    sys = SystemMessage(content=(
        "As a system design top-notch expert, write a high-level, step-by-step system design plan for the described goal, suitable for an experienced engineer "
        " Be terse, numbered, and cover: scope, key components, data/storage, API outline, scaling, reliability, and risks"
    ))
    prompt = f"Goal:\n{goal}\n\nAdditional info (may include constraints:\n{constraints}\n\nReturn a compact numbered plan)"
    run_id = state.get("metadata", {}).get("run_id")
    plan = call_brain([sys, HumanMessage(content=prompt[:1600])], run_id=run_id, node="planner").strip()
    return {"plan": plan}

def web_search(state: State) -> Dict[str, any]:
    goal = (state.get("goal") or "").strip()
    latest_user = last_human_text(state.get("messages", []))
    query_parts = [goal]
    if latest_user and latest_user.lower() != goal.lower():
        query_parts.append(latest_user)
    query = " ".join(part for part in query_parts if part).strip()
    api_key = os.getenv("TAVILY_API_KEY")
    metadata = state.setdefault("metadata", {})
    cache_key = f"web::{query or goal}" if query or goal else None
    cached = metadata.get(cache_key) if cache_key else None
    if cached:
        snippets = cached
    else:
        try:
            snippets = tavily_search(query or goal, max_snippets=3, api_key=api_key)
        except Exception as exc:
            snippets = [{
                "source_url": "",
                "summary": f"Web search failed: {exc}",
                "token_count": 0,
            }]
        if cache_key:
            metadata[cache_key] = snippets

    structured: list[dict[str, str | int]] = []
    for idx, snip in enumerate(snippets, start=1):
        cid = f"[{idx}]"
        structured.append({
            "id": cid,
            "summary": str(snip.get("summary", "")).strip(),
            "source_url": str(snip.get("source_url", "")).strip(),
            "token_count": int(snip.get("token_count", 0) or 0),
        })

    # Merge with any existing global snippets/citations to avoid clobbering KB results
    existing_snippets = state.get("grounding_snippets", []) or []
    existing_citations = state.get("citations", []) or []
    merged_snippets = _merge_snippet_lists(existing_snippets, structured)
    merged_citations = _merge_snippet_lists(existing_citations, structured)

    # Merge queries as well (dedupe)
    existing_queries = [str(q) for q in (state.get("grounding_queries", []) or [])]
    new_queries = [query] if query else []
    all_queries = []
    seen_q: set[str] = set()
    for q in existing_queries + new_queries:
        qn = (q or "").strip()
        if not qn or qn in seen_q:
            continue
        all_queries.append(qn)
        seen_q.add(qn)

    return {
        "grounding_queries": all_queries,
        "grounding_snippets": merged_snippets,
        "citations": merged_citations,
        # Source-specific outputs for introspection/debugging
        "web_grounding_snippets": structured,
        "web_citations": structured,
    }

def _format_grounding(snippets: Sequence[dict[str, str | int]], max_chars: int = 600) -> str:
    lines: list[str] = []
    total = 0
    for snip in snippets:
        cid = str(snip.get("id") or "")
        summary = str(snip.get("summary") or "").strip()
        source = str(snip.get("source_url") or "").strip()
        if not summary:
            continue
        line = f"{cid} {summary}"
        if source:
            line += f" (Source: {source})"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def designer(state: State) -> Dict[str, any]:
    plan = state.get("plan", "") or ""
    goal = state.get("goal", "") or ""
    snippets = state.get("grounding_snippets", []) or []
    grounding_text = _format_grounding(snippets)
    critic_notes = state.get("critic_notes", "") or ""
    critic_fixes = state.get("critic_fixes", []) or []

    sys = SystemMessage(content=(
        "You are a senior system designer. Respond strictly as JSON with keys:"
        " components (array of high-level modules),"
        " data_flow (array describing producer->consumer steps),"
        " storage (array outlining data stores and retention),"
        " nfr_mapping (array of {nfr, strategy}),"
        " brief (short human-readable summary)."
        " Focus only on high-level components, data flow, storage, and NFR mapping."
        " No API specs, no markdown, no extra text outside JSON."
    ))
    feedback = ""
    if critic_notes or critic_fixes:
        fixes_block = "\n".join(f"- {f}" for f in critic_fixes)
        feedback = (
            "\nCritic feedback to address:\n"
            + (critic_notes + "\n" if critic_notes else "")
            + (fixes_block if critic_fixes else "")
        ).strip()

    references = f"\nRelevant web info:\n{grounding_text}" if grounding_text else ""
    prompt = (
        f"Goal:\n{goal}\n\nPlan:\n{plan}{references}\n\n"
        + (f"{feedback}\n\n" if feedback else "")
        + "Return JSON only."
    )

    run_id = state.get("metadata", {}).get("run_id")
    try:
        parsed = call_brain_json([sys, HumanMessage(content=prompt[:1600])], run_id=run_id, node="designer")
    except Exception:
        recovery = SystemMessage(content=(
            "You must return valid JSON. Output only the JSON object with keys"
            " components, data_flow, storage, nfr_mapping, brief."
        ))
        parsed = call_brain_json([recovery, HumanMessage(content=prompt[:1600])], run_id=run_id, node="designer")

    design_brief = str(parsed.get("brief") or "").strip()
    design_json = {
        "components": parsed.get("components") or [],
        "data_flow": parsed.get("data_flow") or [],
        "storage": parsed.get("storage") or [],
        "nfr_mapping": parsed.get("nfr_mapping") or [],
    }

    return {
        "design_json": design_json,
        "design_brief": design_brief,
        "design": json.dumps({**design_json, "brief": design_brief}, ensure_ascii=False),
    }

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "issues": {"type": "array", "items": {"type": "string"}},
        "fixes": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"}
    },
    "required": ["score", "issues", "fixes", "summary"]
}

def critic(state: State) -> Dict[str, any]:
    design_json = state.get("design_json") or {}
    design_brief = state.get("design_brief", "") or ""
    initial_plan = state.get("plan", "") or ""
    sys = SystemMessage(content=(
        "You are a senior system architecture critic. Given the proposed design, you must:\n"
        "- Give a correctness score between 0 and 1 (1 is flawless).\n"
        "- List contradictions (impossible or conflicting requirements).\n"
        "- List infeasible combinations or missing essentials.\n"
        "- Suggest concrete fixes in plain language.\n"
        "Return JSON matching this schema:\n"
        f"{json.dumps(CRITIC_SCHEMA)}"
    ))
    prompt = json.dumps({
        "goal": state.get("goal", ""),
        "plan": initial_plan,
        "design": design_json,
        "brief": design_brief,
    }, ensure_ascii=False)

    run_id = state.get("metadata", {}).get("run_id")
    raw_result = call_brain([sys, HumanMessage(content=prompt)], run_id=run_id, node="critic")
    parsed = json_only(raw_result) or {}
    try:
        jsonschema_validate(parsed, CRITIC_SCHEMA)
    except ValidationError:
        recovery = SystemMessage(content=(
            "Respond again using valid JSON that matches the schema exactly."
        ))
        raw_result = call_brain([recovery, HumanMessage(content=prompt)], run_id=run_id, node="critic")
        parsed = json_only(raw_result) or {}
        jsonschema_validate(parsed, CRITIC_SCHEMA)

    score = float(parsed.get("score") or 0.0)
    score = max(0.0, min(1.0, score))
    issues = [str(x).strip() for x in parsed.get("issues") or [] if str(x).strip()]
    fixes = [str(x).strip() for x in parsed.get("fixes") or [] if str(x).strip()]
    summary = str(parsed.get("summary") or "").strip()
    loops = int(state.get("critic_iterations", 0) or 0) + 1

    notes_parts: list[str] = []
    if summary:
        notes_parts.append(summary)
    if issues:
        notes_parts.append("Issues:\n" + "\n".join(f"- {i}" for i in issues))
    critic_notes = "\n\n".join(notes_parts)

    return {
        "critic_score": score,
        "critic_notes": critic_notes,
        "critic_fixes": fixes,
        "critic_iterations": loops,
    }

def finaliser(state: State) -> Dict[str, any]:
    plan = state.get("plan", "") or ""
    goal = state.get("goal", "") or ""
    design_json = state.get("design_json") or {}
    design_brief = state.get("design_brief", "") or ""
    citations = state.get("citations", []) or []
    critic_score = state.get("critic_score")
    critic_notes = state.get("critic_notes")
    sys = SystemMessage(content=(
        "Being an expert in system design, edit it to a clear markdown for an engineer"
        "Include: Title with the goal, Executive Summary (3-5 bullets), Plan (numbered and in order it needs to be done), Design (sections) and Next Steps (checklist, in order of execution). Keep it short and practical"
    ))
    design_sections = json.dumps(design_json, ensure_ascii=False, indent=2)
    prompt = (
        f"Title: {goal}\n\n"
        f"PLAN:\n{plan}\n\n"
        f"DESIGN_BRIEF:\n{design_brief}\n\n"
        f"DESIGN_JSON:\n{design_sections}\n\n"
        + (f"CRITIC_SCORE: {critic_score}\n\n" if critic_score is not None else "")
        + (f"CRITIC_NOTES:\n{critic_notes}\n\n" if critic_notes else "")
        + "Assemble the final markdown now."
    )
    run_id = state.get("metadata", {}).get("run_id")
    output_md = call_brain([sys, HumanMessage(content=prompt)], run_id=run_id, node="finaliser").strip()
    if citations:
        ref_lines = [
            f"{str(c.get('id') or '')} {str(c.get('source_url') or '')}"
            for c in citations
            if c.get('source_url')
        ]
        if ref_lines:
            output_md = output_md.rstrip() + "\n\nReferences\n" + "\n".join(ref_lines)

    return {"output": output_md}
