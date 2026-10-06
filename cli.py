# -*- coding: utf-8 -*-
"""
Interactive command-line chat with the real-estate agent.

New vs. the original notebook: the customer is identified by phone number
(existing customers are recognized instead of always starting a fresh
anonymous session), and a couple of slash commands let you manage
appointments without going through the LLM at all.

Run:
    python cli.py
"""
from __future__ import annotations

import config
import repositories as repo
from conversation_service import chat
from database import init_db

HELP_TEXT = """Commands:
  /appointments        Show your booked viewings
  /cancel <id>          Cancel an appointment by its ID
  /help                  Show this help text
  /exit                   Quit
Anything else is sent to the agent as a normal message - including things
like "show my appointments" or "what times are open on Friday", which the
agent now understands directly in conversation."""


def _identify_customer() -> int:
    phone = input("Phone number (used to recognize returning customers): ").strip()
    existing = repo.find_customer_by_phone(phone) if phone else None
    if existing:
        print(f"Welcome back, {existing['name']}!")
        return existing["customer_id"]

    name = input("What's your name? ").strip() or "Guest"
    email = input("Email (optional): ").strip() or None
    customer_id = repo.create_customer(name=name, email=email, phone=phone or None)
    print(f"Nice to meet you, {name}!")
    return customer_id


def _handle_command(command: str, customer_id: int) -> bool:
    """Returns True if the input was a command (handled here, not sent to the agent)."""
    if command in ("/exit", "exit", "quit"):
        raise SystemExit

    if command == "/help":
        print(HELP_TEXT)
        return True

    if command == "/appointments":
        appointments = repo.get_customer_appointments(customer_id)
        if not appointments:
            print("You don't have any appointments yet.")
        for a in appointments:
            print(
                f"  #{a['appointment_id']} | {a['property_id']} | "
                f"{a['appointment_date']} {a['appointment_time']} | {a['status']}"
            )
        return True

    if command.startswith("/cancel"):
        parts = command.split()
        if len(parts) != 2 or not parts[1].isdigit():
            print("Usage: /cancel <appointment_id>")
            return True
        ok = repo.cancel_appointment(int(parts[1]), customer_id)
        print("Cancelled." if ok else "Couldn't find a scheduled appointment with that ID for you.")
        return True

    return False


def main() -> None:
    config.configure_logging()
    init_db()

    print("Real Estate Agent - type /help for commands, /exit to quit.\n")
    customer_id = _identify_customer()
    graph = None  # tool-calling agent; graph unused

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        try:
            if _handle_command(user_input, customer_id):
                continue
        except SystemExit:
            print("Goodbye!")
            break

        response = chat(customer_id, user_input, graph)
        print(f"\nAgent: {response}")


if __name__ == "__main__":
    main()
