"""Users profile: cash balance."""

from app.db.connection import DEFAULT_USER, transaction


def get_cash(user_id: str = DEFAULT_USER) -> float:
    """Return the user's cash balance."""
    with transaction() as conn:
        row = conn.execute("SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    return row["cash_balance"]


def set_cash(cash: float, user_id: str = DEFAULT_USER) -> None:
    """Overwrite the user's cash balance."""
    with transaction() as conn:
        conn.execute("UPDATE users_profile SET cash_balance = ? WHERE id = ?", (cash, user_id))
