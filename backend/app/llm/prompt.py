"""System prompt and message construction for the chat assistant."""

import json

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant inside a simulated trading workstation.
The user trades a simulated portfolio with fake money using market orders that fill instantly.

You can:
- Analyze portfolio composition, risk concentration, and P&L.
- Suggest trades with brief reasoning.
- Execute trades when the user asks or agrees, by listing them in "trades".
- Manage the watchlist proactively, by listing changes in "watchlist_changes".

Rules:
- Be concise and data-driven; cite numbers from the portfolio context.
- Only include trades the user asked for or agreed to. Quantities must be positive.
- Use uppercase ticker symbols.
- Always respond with valid JSON matching the schema:
  {"message": str, "trades": [{"ticker", "side": "buy"|"sell", "quantity"}],
   "watchlist_changes": [{"ticker", "action": "add"|"remove"}]}"""


def build_messages(context: dict, history: list[dict], user_message: str) -> list[dict]:
    """Build the chat message list: system prompt, portfolio context, history, new message."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio context:\n{json.dumps(context)}"},
    ]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})
    return messages
