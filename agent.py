# -*- coding: utf-8 -*-
"""
Tool-calling real-estate agent (LangGraph + bound tools).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

import llm_service
import repositories as repo
from tools import build_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a warm, proactive real-estate advisor — not a form bot.
Today is {today} ({weekday}). Resolve relative dates (tomorrow, next Friday) using this.

Inventory (important):
- Live data is the USA Housing dataset on Supabase (King County / greater Seattle, Washington).
- Main cities: Seattle, Bellevue, Redmond, Kirkland, Renton, Issaquah, Sammamish, Kent, Auburn,
  Shoreline, Federal Way, Maple Valley, Mercer Island, Woodinville, and nearby.
- Almost every listing is for Sale (not rent). Prices are in USD.
- Property IDs look like USA00001, USA01234 — always show them when listing options.

Personality:
- 1–4 short sentences when chatting; use structured lists only when showing properties.
- Be proactive: after results, suggest details, compare, book a viewing, or refine filters.
- The web UI shows property cards (with Compare / Book / Favorite buttons) for your search and compare results, so do not repeat every field: highlight the top 1-2 picks and why, then suggest one next step.
- Remember taste: if they say why they like/reject something, ALWAYS call save_feedback with the reason.
- Never invent property IDs, prices, or availability — use tools.
- Speak the same language the customer is using (Persian or English).

Tools — when to use them:
- get_customer_memory: early in a session or when personalizing.
- search_properties: when they describe what they want (city is the most useful filter).
- get_property_details: full card for one ID.
- compare_properties: 2+ IDs side by side.
- save_feedback: like/reject + reason (critical for learning).
- add_favorite / list_favorites: shortlist.
- get_available_slots → book_appointment: viewing flow (confirm date/time with user).
- list_appointments / cancel_appointment: manage bookings.

When presenting search results, number them 1..n and always include property_id (e.g. ID: USA00042)
so the user can refer to options by number or ID next turn. Map "option 2" to the 2nd ID you listed.

If city is missing, ask once naturally (e.g. Seattle vs Bellevue). Do not insist on rent vs sale —
default is Sale. After feedback, acknowledge the reason and offer a refined search.
"""


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: int


@dataclass
class ToolTraceItem:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    summary: str = ""
    data: Any = None  # parsed JSON result of the tool (used by the web UI for cards)


@dataclass
class TurnResult:
    response: str
    tool_trace: List[ToolTraceItem] = field(default_factory=list)


def _system_message() -> SystemMessage:
    today = date.today()
    return SystemMessage(
        content=SYSTEM_PROMPT.format(today=today.isoformat(), weekday=today.strftime("%A"))
    )


def _summarize_tool_result(name: str, content: str) -> str:
    """Short human-readable line for the activity panel."""
    try:
        data = json.loads(content) if content else {}
    except Exception:
        text = (content or "")[:80]
        return text + ("…" if len(content or "") > 80 else "")

    if not isinstance(data, dict):
        return str(data)[:100]

    if data.get("error"):
        return f"error: {data['error']}"

    if name == "search_properties":
        n = data.get("showing") or data.get("count") or 0
        total = data.get("count", n)
        return f"{n} shown (of {total})"
    if name == "get_property_details":
        prop = data.get("property") or {}
        return prop.get("property_id") or "loaded"
    if name == "compare_properties":
        props = data.get("properties") or []
        ids = [p.get("property_id") for p in props if isinstance(p, dict)]
        return " vs ".join(ids) if ids else "compared"
    if name == "save_feedback":
        return f"{data.get('action', '')} · {data.get('property_id', '')}"
    if name == "book_appointment":
        if data.get("success"):
            return f"booked #{data.get('appointment_id')}"
        return data.get("message") or "failed"
    if name == "get_available_slots":
        slots = data.get("slots") or []
        return f"{len(slots)} open on {data.get('date', '')}"
    if name == "list_appointments":
        return f"{len(data.get('appointments') or [])} scheduled"
    if name == "list_favorites":
        return f"{len(data.get('favorites') or [])} saved"
    if name == "add_favorite":
        return data.get("property_id") or "saved"
    if name == "get_customer_memory":
        return "preferences loaded"
    if name == "cancel_appointment":
        return "cancelled" if data.get("ok") else "not found"
    return "ok"


def _extract_trace(messages: Sequence[BaseMessage]) -> List[ToolTraceItem]:
    """Pair AI tool_calls with subsequent ToolMessage results."""
    pending: Dict[str, ToolTraceItem] = {}
    ordered: List[ToolTraceItem] = []

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tid = tc.get("id") or ""
                name = tc.get("name") or "tool"
                args = tc.get("args") or {}
                if not isinstance(args, dict):
                    args = {"raw": args}
                item = ToolTraceItem(name=name, args=args)
                ordered.append(item)
                if tid:
                    pending[tid] = item
        elif isinstance(msg, ToolMessage):
            tid = getattr(msg, "tool_call_id", None) or ""
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            item = pending.get(tid)
            if item is None:
                item = ToolTraceItem(name=getattr(msg, "name", None) or "tool")
                ordered.append(item)
            item.summary = _summarize_tool_result(item.name, content)
            try:
                parsed = json.loads(content) if content else None
                if isinstance(parsed, dict):
                    item.data = parsed
            except Exception:
                pass
            if (content or "").startswith("Error"):
                item.ok = False
            if content and "error" in content.lower()[:200]:
                try:
                    if json.loads(content).get("error"):
                        item.ok = False
                except Exception:
                    pass

    return ordered


def build_agent_graph(customer_id: int):
    tools = build_tools(customer_id)
    llm = llm_service.llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def chatbot(state: AgentState) -> Dict[str, Any]:
        msgs = list(state["messages"])
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [_system_message(), *msgs]
        response = llm.invoke(msgs)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("agent", chatbot)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")
    return graph.compile()


_GRAPH_CACHE: Dict[int, Any] = {}


def get_agent(customer_id: int):
    if customer_id not in _GRAPH_CACHE:
        _GRAPH_CACHE[customer_id] = build_agent_graph(customer_id)
    return _GRAPH_CACHE[customer_id]


def clear_agent_cache(customer_id: Optional[int] = None) -> None:
    if customer_id is None:
        _GRAPH_CACHE.clear()
    else:
        _GRAPH_CACHE.pop(customer_id, None)


def run_turn(
    customer_id: int,
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> TurnResult:
    agent = get_agent(customer_id)

    messages: List[BaseMessage] = [_system_message()]

    try:
        taste = repo.get_taste_summary(customer_id)
        profile = repo.get_customer_profile(customer_id)
        if taste or profile:
            messages.append(
                SystemMessage(
                    content=f"Known preferences: {profile or {}}. Taste insights: {taste or 'none yet'}."
                )
            )
    except Exception:
        logger.exception("memory preload failed")

    if history:
        for m in history[-16:]:
            role = m.get("role")
            content = m.get("content") or m.get("message") or ""
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))

    result = agent.invoke({"messages": messages, "customer_id": customer_id})
    out_messages = result.get("messages") or []
    trace = _extract_trace(out_messages)

    response_text = "I'm not sure how to help with that — could you rephrase?"
    for msg in reversed(out_messages):
        if isinstance(msg, AIMessage):
            text = msg.content
            if isinstance(text, list):
                parts = []
                for block in text:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("text"):
                        parts.append(block["text"])
                text = "\n".join(parts)
            if text and str(text).strip():
                response_text = str(text).strip()
                break

    return TurnResult(response=response_text, tool_trace=trace)
