"""Supabase data-access layer for conversations and messages (Phase 3).

Follows the Phase 2 repository pattern: the services talk to THIS class,
never to raw Supabase calls, and unexpected database problems raise
RepositoryError (reused from `booking_repository`, not duplicated) with a
generic message so callers never leak internals.

Uses the Phase 1 tables as-is — no migration, no new tables.
"""

from app.integrations.booking_repository import RepositoryError


class ConversationRepository:
    """Thin wrapper around a Supabase client for conversation operations."""

    def __init__(self, client) -> None:
        self.client = client

    # -- customers (same customers table as the booking engine) --------------

    def find_customer_by_phone(self, phone: str) -> dict | None:
        """Return the first customer with this exact phone, or None."""
        try:
            response = (
                self.client.table("customers")
                .select("*")
                .eq("phone", phone)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def find_customer_by_email(self, email: str) -> dict | None:
        """Return the first customer with this exact email, or None."""
        try:
            response = (
                self.client.table("customers")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def create_customer(self, name: str, phone: str, email: str | None) -> dict:
        """Insert a customer row and return it (must include its id)."""
        try:
            response = (
                self.client.table("customers")
                .insert({"name": name, "phone": phone, "email": email})
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Customer creation failed") from exc
        rows = response.data or []
        if not rows or "id" not in rows[0]:
            raise RepositoryError("Customer creation failed")
        return rows[0]

    # -- conversations ---------------------------------------------------------

    def find_active_conversation(
        self, customer_id: str, channel: str
    ) -> dict | None:
        """Return the newest 'active' conversation for a customer+channel.

        Closed and human_handoff threads are never returned: a new message
        starts a fresh active conversation instead of resurrecting one.
        """
        try:
            response = (
                self.client.table("conversations")
                .select("*")
                .eq("customer_id", customer_id)
                .eq("channel", channel)
                .eq("status", "active")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Conversation lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def create_conversation(self, customer_id: str, channel: str) -> dict:
        """Insert an 'active' conversation row and return it."""
        try:
            response = (
                self.client.table("conversations")
                .insert(
                    {
                        "customer_id": customer_id,
                        "channel": channel,
                        "status": "active",
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Conversation creation failed") from exc
        rows = response.data or []
        if not rows or "id" not in rows[0]:
            raise RepositoryError("Conversation creation failed")
        return rows[0]

    def get_conversation(self, conversation_id: str) -> dict | None:
        """Return a conversation row by id, or None when it does not exist."""
        try:
            response = (
                self.client.table("conversations")
                .select("*")
                .eq("id", conversation_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Conversation lookup failed") from exc
        rows = response.data or []
        return rows[0] if rows else None

    def update_conversation_status(
        self, conversation_id: str, status: str
    ) -> dict:
        """Persist a status already validated by the service layer."""
        try:
            response = (
                self.client.table("conversations")
                .update({"status": status})
                .eq("id", conversation_id)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Conversation update failed") from exc
        rows = response.data or []
        if not rows:
            raise RepositoryError("Conversation update failed")
        return rows[0]

    # -- messages (append-only history) ------------------------------------------

    def create_message(
        self, conversation_id: str, sender: str, message: str
    ) -> dict:
        """Append one message row and return it (must include its id)."""
        try:
            response = (
                self.client.table("messages")
                .insert(
                    {
                        "conversation_id": conversation_id,
                        "sender": sender,
                        "message": message,
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Message creation failed") from exc
        rows = response.data or []
        if not rows or "id" not in rows[0]:
            raise RepositoryError("Message creation failed")
        return rows[0]

    def list_messages(self, conversation_id: str) -> list[dict]:
        """Return all messages in a conversation, oldest first."""
        try:
            response = (
                self.client.table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError("Message lookup failed") from exc
        return response.data or []
