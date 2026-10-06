# -*- coding: utf-8 -*-
"""
Polished Gradio UI — Gradio 5/6 compatible, with Agent activity panel.
Light UI upgrade: clearer hierarchy, mini property cards, cleaner side rail.
"""
from __future__ import annotations

import html
import inspect
from typing import List, Optional

import config
import repositories as repo
from agent import ToolTraceItem
from conversation_service import chat_with_trace
from database import init_db

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "gradio is not installed. Run `pip install gradio` to use the web UI, "
        "or use cli.py instead."
    ) from exc


CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap');

:root {
  --bg: #0b0e13;
  --bg-elevated: #121820;
  --bg-card: #181f29;
  --border: #2a3544;
  --border-soft: rgba(42, 53, 68, 0.7);
  --text: #e8eef6;
  --muted: #8b9bb0;
  --accent: #4aa3f5;
  --accent-soft: rgba(74, 163, 245, 0.14);
  --ok: #34d399;
  --err: #f87171;
  --price: #f0c14a;
  --radius: 14px;
  --shadow: 0 10px 36px rgba(0,0,0,0.38);
}

.gradio-container {
  font-family: 'DM Sans', system-ui, sans-serif !important;
  background: var(--bg) !important;
  color: var(--text) !important;
  max-width: 1120px !important;
  margin: 0 auto !important;
  padding-bottom: 28px !important;
}

/* —— Hero —— */
.re-hero {
  background:
    radial-gradient(ellipse 80% 60% at 100% 0%, rgba(74,163,245,0.16), transparent 55%),
    linear-gradient(145deg, #121820 0%, #152030 55%, #0f1a16 100%);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 26px 30px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.re-hero h1 {
  font-family: 'Instrument Serif', Georgia, serif !important;
  font-size: 2rem !important;
  font-weight: 400 !important;
  margin: 0 0 8px 0 !important;
  color: var(--text) !important;
  letter-spacing: -0.02em;
  line-height: 1.15 !important;
}
.re-hero p {
  margin: 0 !important;
  color: var(--muted) !important;
  font-size: 0.92rem !important;
  max-width: 540px;
  line-height: 1.55;
}
.re-badge {
  display: inline-block;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 12px;
}
.re-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.re-pill {
  font-size: 0.75rem;
  color: var(--muted);
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  padding: 4px 10px;
}

/* —— Side cards —— */
.re-side-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 10px;
}
.re-side-card h3 {
  font-size: 0.72rem !important;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--muted) !important;
  margin: 0 0 10px 0 !important;
  font-weight: 600 !important;
  display: flex;
  align-items: center;
  gap: 6px;
}
.re-side-card .empty {
  color: var(--muted);
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.45;
}
.re-side-card ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

/* Mini property cards (favorites) */
.re-mini {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.re-mini:last-child { margin-bottom: 0; }
.re-mini .id {
  font-size: 0.72rem;
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.02em;
}
.re-mini .price {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--price);
  margin: 2px 0 4px 0;
}
.re-mini .loc {
  font-size: 0.82rem;
  color: var(--text);
}
.re-mini .meta {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 4px;
}

/* Taste chips */
.re-chip {
  display: inline-block;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 9px;
  margin: 3px;
  font-size: 0.78rem;
  color: var(--muted);
}

/* Activity log */
.re-trace-item {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.74rem;
  padding: 8px 10px;
  margin: 6px 0;
  border-radius: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  color: var(--text);
  line-height: 1.4;
}
.re-trace-item .name { color: var(--accent); font-weight: 600; }
.re-trace-item .ok { color: var(--ok); }
.re-trace-item .err { color: var(--err); }
.re-trace-item .args { color: var(--muted); display: block; margin-top: 2px; }

/* Viewing rows */
.re-appt {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 6px;
  font-size: 0.84rem;
}
.re-appt .when { color: var(--muted); font-size: 0.78rem; margin-top: 2px; }

.re-footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.75rem;
  margin-top: 16px;
  opacity: 0.85;
}

/* Chat area polish */
.re-chat textarea, .re-chat {
  border-radius: 14px !important;
}
"""


EXAMPLES = [
    "Looking to buy a 3-bedroom house in Seattle under 600000",
    "3 bed in Bellevue or Redmond under 800k",
    "Show details on the second option",
    "Compare option 1 and 3",
    "Option 2 is too expensive — show me cheaper in Renton or Kent",
    "Book a viewing for the first property tomorrow at 11:00",
]


def _resolve_customer(phone: str, name: str):
    phone = (phone or "").strip()
    name = (name or "").strip() or "Guest"
    if phone:
        existing = repo.find_customer_by_phone(phone)
        if existing:
            return existing["customer_id"], f"Welcome back, **{existing['name']}**"
    cid = repo.create_customer(name=name, phone=phone or None)
    return cid, f"Nice to meet you, **{name}**"


def _money(n) -> str:
    try:
        return f"${int(n):,}"
    except (TypeError, ValueError):
        return "—"


def _favorites_html(customer_id):
    if not customer_id:
        return (
            "<div class='re-side-card'><h3>★ Favorites</h3>"
            "<p class='empty'>Enter a phone number so favorites persist across visits.</p></div>"
        )
    profile = repo.get_customer_profile(customer_id)
    ids = [k.split(":", 1)[1] for k in profile if k.startswith("favorite:")]
    if not ids:
        return (
            "<div class='re-side-card'><h3>★ Favorites</h3>"
            "<p class='empty'>None yet — ask me to save a listing you like.</p></div>"
        )
    props = repo.get_properties_by_ids(ids)
    cards = []
    for p in props:
        cards.append(
            "<div class='re-mini'>"
            f"<div class='id'>{html.escape(str(p.get('property_id', '')))}</div>"
            f"<div class='price'>{_money(p.get('price'))}</div>"
            f"<div class='loc'>{html.escape(str(p.get('neighborhood') or ''))}, "
            f"{html.escape(str(p.get('city') or ''))}</div>"
            f"<div class='meta'>{p.get('bedrooms', '?')} bed · {p.get('bathrooms', '?')} bath · "
            f"{p.get('area_sqft', '?')} sqft</div>"
            "</div>"
        )
    return f"<div class='re-side-card'><h3>★ Favorites</h3>{''.join(cards)}</div>"


def _taste_html(customer_id):
    if not customer_id:
        return (
            "<div class='re-side-card'><h3>◎ Your taste</h3>"
            "<p class='empty'>Like or skip listings with a reason — I’ll learn.</p></div>"
        )
    summary = repo.get_taste_summary(customer_id)
    if not summary:
        return (
            "<div class='re-side-card'><h3>◎ Your taste</h3>"
            "<p class='empty'>No insights yet. Say why an option works or doesn’t.</p></div>"
        )
    chips = "".join(
        f"<span class='re-chip'>{html.escape(part.strip())}</span>"
        for part in summary.split(";")
        if part.strip()
    )
    return f"<div class='re-side-card'><h3>◎ Your taste</h3><div>{chips}</div></div>"


def _appointments_html(customer_id):
    if not customer_id:
        return (
            "<div class='re-side-card'><h3>📅 Viewings</h3>"
            "<p class='empty'>—</p></div>"
        )
    appts = [
        a for a in repo.get_customer_appointments(customer_id) if a.get("status") == "scheduled"
    ]
    if not appts:
        return (
            "<div class='re-side-card'><h3>📅 Viewings</h3>"
            "<p class='empty'>No upcoming viewings. Ask to book one.</p></div>"
        )
    items = []
    for a in appts:
        items.append(
            "<div class='re-appt'>"
            f"<strong>#{a['appointment_id']}</strong> · {html.escape(str(a['property_id']))}"
            f"<div class='when'>{html.escape(str(a['appointment_date']))} "
            f"{html.escape(str(a['appointment_time']))}</div>"
            "</div>"
        )
    return f"<div class='re-side-card'><h3>📅 Viewings</h3>{''.join(items)}</div>"


def _format_args(args: dict) -> str:
    if not args:
        return ""
    parts = []
    for k, v in list(args.items())[:6]:
        if v is None or v == "" or v is False:
            continue
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "…"
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def _activity_html(trace: Optional[List[ToolTraceItem]]):
    body = "<div class='re-side-card'><h3>⚡ Agent activity</h3>"
    if not trace:
        body += "<p class='empty'>Tool calls from the last reply show up here.</p></div>"
        return body

    items = []
    for t in trace:
        status = "ok" if t.ok else "err"
        status_label = "ok" if t.ok else "error"
        args = _format_args(t.args)
        summary = html.escape(t.summary or "")
        name = html.escape(t.name)
        args_html = f"<span class='args'>{html.escape(args)}</span>" if args else ""
        items.append(
            f"<div class='re-trace-item'>"
            f"<span class='name'>{name}</span> "
            f"<span class='{status}'>· {status_label}</span>"
            f"{args_html}"
            f"<span class='args'>{summary}</span>"
            f"</div>"
        )
    body += "".join(items) + "</div>"
    return body


def _chatbot_kwargs():
    sig = inspect.signature(gr.Chatbot.__init__)
    params = sig.parameters
    kwargs = {"label": "Conversation", "height": 520}
    if "type" in params:
        kwargs["type"] = "messages"
    if "show_copy_button" in params:
        kwargs["show_copy_button"] = True
    if "elem_classes" in params:
        kwargs["elem_classes"] = ["re-chat"]
    if "bubble_full_width" in params:
        kwargs["bubble_full_width"] = False
    return kwargs


def build_interface():
    with gr.Blocks(title="Homes · AI Realtor") as demo:
        customer_state = gr.State(None)

        gr.HTML(
            """
            <div class="re-hero">
              <div class="re-badge">AI Realtor · King County · Supabase</div>
              <h1>Find a place that feels like yours</h1>
              <p>Search Seattle-area homes, compare options, save favorites, and book viewings.
              I remember why you liked or skipped each listing.</p>
              <div class="re-hero-meta">
                <span class="re-pill">Seattle · Bellevue · Redmond</span>
                <span class="re-pill">Sale listings · USD</span>
                <span class="re-pill">Tool-calling agent</span>
              </div>
            </div>
            """
        )

        with gr.Row():
            phone_box = gr.Textbox(
                label="Phone",
                placeholder="+1… (returning clients)",
                scale=2,
            )
            name_box = gr.Textbox(label="Name", placeholder="First visit only", scale=2)
            status = gr.Markdown("*Enter phone & start chatting*", scale=3)

        with gr.Row():
            with gr.Column(scale=7):
                chatbot = gr.Chatbot(**_chatbot_kwargs())
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="e.g. 3-bed house in Seattle under 600k…",
                        show_label=False,
                        scale=6,
                        container=False,
                    )
                    send = gr.Button("Send", variant="primary", scale=1)
                gr.Examples(examples=EXAMPLES, inputs=msg, label="Try one of these")

            with gr.Column(scale=3):
                activity_panel = gr.HTML(_activity_html(None))
                fav_panel = gr.HTML(_favorites_html(None))
                taste_panel = gr.HTML(_taste_html(None))
                appt_panel = gr.HTML(_appointments_html(None))
                refresh = gr.Button("Refresh panels", size="sm")

        gr.HTML(
            "<div class='re-footer'>Homes agent · LangGraph tools · Supabase · USA Housing (King County)</div>"
        )

        def respond(message, history, phone, name, cid):
            history = history or []
            empty_panels = (
                history,
                cid,
                gr.update(),
                _activity_html(None),
                _favorites_html(cid),
                _taste_html(cid),
                _appointments_html(cid),
                "",
            )
            if not (message or "").strip():
                return empty_panels

            if not cid:
                cid, note = _resolve_customer(phone, name)
                status_md = note
            else:
                status_md = f"**Session** · customer #{cid}"

            reply, trace = chat_with_trace(cid, message.strip())
            history = history + [
                {"role": "user", "content": message.strip()},
                {"role": "assistant", "content": reply},
            ]
            return (
                history,
                cid,
                status_md,
                _activity_html(trace),
                _favorites_html(cid),
                _taste_html(cid),
                _appointments_html(cid),
                "",
            )

        def refresh_panels(cid):
            return (
                _activity_html(None),
                _favorites_html(cid),
                _taste_html(cid),
                _appointments_html(cid),
            )

        outputs = [
            chatbot,
            customer_state,
            status,
            activity_panel,
            fav_panel,
            taste_panel,
            appt_panel,
            msg,
        ]
        send.click(
            respond,
            inputs=[msg, chatbot, phone_box, name_box, customer_state],
            outputs=outputs,
        )
        msg.submit(
            respond,
            inputs=[msg, chatbot, phone_box, name_box, customer_state],
            outputs=outputs,
        )
        refresh.click(
            refresh_panels,
            inputs=[customer_state],
            outputs=[activity_panel, fav_panel, taste_panel, appt_panel],
        )

    return demo


def launch(share: bool = True, **kwargs):
    config.configure_logging()
    init_db()
    demo = build_interface()
    launch_sig = inspect.signature(demo.launch)
    launch_kwargs = {"share": share, **kwargs}
    if "css" in launch_sig.parameters:
        launch_kwargs["css"] = CUSTOM_CSS
    if "theme" in launch_sig.parameters:
        try:
            launch_kwargs["theme"] = gr.themes.Soft(primary_hue="blue", neutral_hue="slate")
        except Exception:
            pass
    if "css" not in launch_sig.parameters:
        try:
            demo.css = CUSTOM_CSS
        except Exception:
            pass
    return demo.launch(**launch_kwargs)


if __name__ == "__main__":
    launch(share=True)
