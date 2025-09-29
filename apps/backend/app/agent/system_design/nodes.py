from typing import Dict, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from .state import State, MAX_ITERATIONS
from langchain_openai import ChatOpenAI
from functools import lru_cache
import json
import os

@lru_cache(maxsize=4)
def make_brain(model: str | None=None) -> ChatOpenAI:
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
        # to capture last human message content in sequence 
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

def call_brain(messages: list[any]) -> str:
    ms = normalise(messages)
    r = BRAIN.invoke(ms)
    return getattr(r, "content", "") or ""


def collect_recent_context(messages: list[BaseMessage], max_chars: int = 1200) -> str:
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


def tool_call(state: State) -> Dict[str, any]: # for external tools - Tavaly to call later
    return {}





def intent(state: State) -> Dict[str, any]: # analysing user's intent with LLM
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
        human = HumanMessage(content=f"Ask for {need}. Keep short & specific"
        )
        question = call_brain([sys, human]).strip() or f"Please provide {need}"
        return {
            "messages": [AIMessage(content=question)],
            "iterations": it + 1
        }
    
    return {}



def planner(state: State) -> Dict[str, any]: # analysing user's intent with LLM
    goal = state.get("goal", "") or ""
    constraints = ""
    # fetching constraint context
    user_reply = last_human_text(state.get("messages", []))
    if user_reply and user_reply.lower() != goal.lower():
        constraints = user_reply

    sys = SystemMessage(content=(
        "As a system design top-notch expert, write a high-level, step-by-step system design plan for the described goal, suitable for an experienced engineer "
        " Be terse, numbered, and cover: scope, key components, data/storage, API outline, scaling, reliability, and risks"
    ))
    prompt = f"Goal:\n{goal}\n\nAdditional info (may include constraints:\n{constraints}\n\nReturn a compact numbered plan)"
    plan = call_brain([sys, HumanMessage(content=prompt)]).strip()
    return {"plan": plan}

def designer(state: State) -> Dict[str, any]:
    plan = state.get("plan", "") or ""
    goal = state.get("goal", "") or ""

    sys = SystemMessage(content=(
        "You are an expert in system design. Expand the plan into a technical design outline with clear sections on bullets."
        "Include: architecture overview, component, data model, APIs, read/write paths, indexing/caching, scaling strategies, consistency, fault tolerance, observability, and trade-offs"
        "Use crisp bullets and short sentences"

    ))
    prompt = f"Goal:\n{goal}\n\nPlan:\n{plan}\n\nProduce a concise, technically rigorous outline"
    design = call_brain([sys, HumanMessage(content=prompt)]).strip()

    return {"design": design}



def finaliser(state: State) -> Dict[str, any]:
    plan = state.get("plan", "") or ""
    goal = state.get("goal", "") or ""
    design = state.get("design", "") or ""

    sys = SystemMessage(content=(
        "Being an expert in system design, edit it to a clear markdown for an engineer"
        "Include: Title with the goal, Executive Summary (3-5 bullets), Plan (numbered and in order it needs to be done), Design (sections) and Next Steps (checklist, in order of execution). Keep it short and practical"

    ))

    prompt = (
        f"Title: {goal}\n\n"
        f"PLAN:\n{plan}\n\n"
        f"DESIGN:\n{design}\n\n"
        "Assemble the final markdown now.")
    

    output_md = call_brain([sys, HumanMessage(content=prompt)]).strip()


    return {"output": output_md}
