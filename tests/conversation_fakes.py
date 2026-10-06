"""Shared fake repository for conversation-layer unit tests (Phase 3).

Mimics ConversationRepository's method names with in-memory data,
so unit tests never need a live database. Timestamps are simple
increasing counters formatted as ISO strings — enough to verify
chronological ordering.
"""

from app.integrations.booking_repository import RepositoryError


def _timestamp(counter: int) -> str:
    return f"2030-01-01T00:00:{counter:02d}+00:00"


class FakeConversationRepository:
    """In-memory stand-in for ConversationRepository."""

    def __init__(self, fail_on=()) -> None:
        self.fail_on = set(fail_on)
        self.customers: list[dict] = []
        self.conversations: list[dict] = []
        self.messages: list[dict] = []
        self._next_id = 2000
        self._clock = 0

    def _new_id(self, prefix: str) -> str:
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    def _tick(self) -> str:
        self._clock += 1
        return _timestamp(self._clock)

    def _maybe_fail(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(f"Fake failure in {method}")

    # -- customers ------------------------------------------------------
    def find_customer_by_phone(self, phone: str) -> dict | None:
        self._maybe_fail("find_customer_by_phone")
        for customer in self.customers:
            if customer.get("phone") == phone:
                return customer
        return None

    def find_customer_by_email(self, email: str) -> dict | None:
        self._maybe_fail("find_customer_by_email")
        for customer in self.customers:
            if customer.get("email") == email:
                return customer
        return None

    def create_customer(self, name: str, phone: str, email: str | None) -> dict:
        self._maybe_fail("create_customer")
        row = {"id": self._new_id("cust"), "name": name, "phone": phone, "email": email}
        self.customers.append(row)
        return row

    # -- conversations ----------------------------------------------------
    def find_active_conversation(
        self, customer_id: str, channel: str
    ) -> dict | None:
        self._maybe_fail("find_active_conversation")
        actives = [
            conversation
            for conversation in self.conversations
            if conversation.get("customer_id") == customer_id
            and conversation.get("channel") == channel
            and conversation.get("status") == "active"
        ]
        return actives[-1] if actives else None

    def create_conversation(self, customer_id: str, channel: str) -> dict:
        self._maybe_fail("create_conversation")
        now = self._tick()
        row = {
            "id": self._new_id("conv"),
            "customer_id": customer_id,
            "channel": channel,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self.conversations.append(row)
        return row

    def get_conversation(self, conversation_id: str) -> dict | None:
        self._maybe_fail("get_conversation")
        for conversation in self.conversations:
            if conversation.get("id") == conversation_id:
                return conversation
        return None

    def update_conversation_status(
        self, conversation_id: str, status: str
    ) -> dict:
        self._maybe_fail("update_conversation_status")
        for conversation in self.conversations:
            if conversation.get("id") == conversation_id:
                conversation["status"] = status
                conversation["updated_at"] = self._tick()
                return conversation
        raise RepositoryError("Conversation update failed")

    # -- messages -----------------------------------------------------------
    def create_message(
        self, conversation_id: str, sender: str, message: str
    ) -> dict:
        self._maybe_fail("create_message")
        row = {
            "id": self._new_id("msg"),
            "conversation_id": conversation_id,
            "sender": sender,
            "message": message,
            "created_at": self._tick(),
        }
        self.messages.append(row)
        return row

    def list_messages(self, conversation_id: str) -> list[dict]:
        self._maybe_fail("list_messages")
        rows = [
            message
            for message in self.messages
            if message.get("conversation_id") == conversation_id
        ]
        return sorted(rows, key=lambda row: row["created_at"])
