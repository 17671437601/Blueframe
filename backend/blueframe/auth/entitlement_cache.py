from __future__ import annotations

import json
from datetime import datetime
from typing import Callable
from uuid import uuid4

from pydantic import field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.domain.common import DomainModel, require_aware
from blueframe.providers.auth import Entitlements


class EntitlementSnapshot(DomainModel):
    entitlements: Entitlements
    verified_at: datetime
    token_expires_at: datetime
    signature_valid: bool
    subject_user_id: str

    _aware = field_validator("verified_at", "token_expires_at")(require_aware)

    @property
    def is_trusted(self) -> bool:
        return self.signature_valid and self.subject_user_id == self.entitlements.user_id


class InMemoryEntitlementCache:
    def __init__(self, snapshot: EntitlementSnapshot | None = None) -> None:
        self.snapshot = snapshot
        self.last_evaluated_at: datetime | None = None

    def get_snapshot(self) -> EntitlementSnapshot | None:
        return self.snapshot

    def update_last_evaluated(self, value: datetime) -> None:
        self.last_evaluated_at = value


class SqliteEntitlementCache:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        signature_verifier: Callable[[bytes, str], bool],
    ) -> None:
        self._session_factory = session_factory
        self._signature_verifier = signature_verifier
        self._user_id: str | None = None

    def save(
        self,
        *,
        profile: "UserProfile",
        credential_reference: str,
        snapshot: EntitlementSnapshot,
        signed_payload: str,
        signature: str,
    ) -> None:
        if profile.user_id != snapshot.subject_user_id:
            raise ValueError("snapshot subject does not match profile")
        with self._session_factory.begin() as session:
            session.execute(
                text(
                    """INSERT INTO account_summary
                    (user_id, display_name, credential_reference, updated_at)
                    VALUES (:user_id, :display_name, :reference, :updated_at)
                    ON CONFLICT(user_id) DO UPDATE SET
                      display_name=excluded.display_name,
                      credential_reference=excluded.credential_reference,
                      updated_at=excluded.updated_at"""
                ),
                {
                    "user_id": profile.user_id,
                    "display_name": profile.display_name,
                    "reference": credential_reference,
                    "updated_at": snapshot.verified_at.isoformat(),
                },
            )
            session.execute(
                text("DELETE FROM entitlement_snapshot WHERE user_id=:user_id"),
                {"user_id": profile.user_id},
            )
            session.execute(
                text(
                    """INSERT INTO entitlement_snapshot
                    (id, user_id, signed_payload, signature, verified_at,
                     token_expires_at, last_evaluated_at)
                    VALUES (:id, :user_id, :payload, :signature, :verified_at,
                            :token_expires_at, :last_evaluated_at)"""
                ),
                {
                    "id": str(uuid4()),
                    "user_id": profile.user_id,
                    "payload": signed_payload,
                    "signature": signature,
                    "verified_at": snapshot.verified_at.isoformat(),
                    "token_expires_at": snapshot.token_expires_at.isoformat(),
                    "last_evaluated_at": snapshot.verified_at.isoformat(),
                },
            )
        self._user_id = profile.user_id

    def get_snapshot(self) -> EntitlementSnapshot | None:
        row = self._load_row()
        if row is None:
            return None
        if not self._signature_verifier(row.signed_payload.encode("utf-8"), row.signature):
            return None
        entitlements = Entitlements.model_validate_json(row.signed_payload)
        return EntitlementSnapshot(
            entitlements=entitlements,
            verified_at=_as_datetime(row.verified_at),
            token_expires_at=_as_datetime(row.token_expires_at),
            signature_valid=True,
            subject_user_id=row.user_id,
        )

    @property
    def last_evaluated_at(self) -> datetime | None:
        row = self._load_row()
        return None if row is None else _as_datetime(row.last_evaluated_at)

    def update_last_evaluated(self, value: datetime) -> None:
        row = self._load_row()
        if row is None:
            return
        with self._session_factory.begin() as session:
            session.execute(
                text("UPDATE entitlement_snapshot SET last_evaluated_at=:value WHERE id=:id"),
                {"value": value.isoformat(), "id": row.id},
            )

    def _load_row(self):
        where = "WHERE user_id=:user_id" if self._user_id else ""
        params = {"user_id": self._user_id} if self._user_id else {}
        with self._session_factory() as session:
            return session.execute(
                text(
                    f"""SELECT id, user_id, signed_payload, signature, verified_at,
                    token_expires_at, last_evaluated_at
                    FROM entitlement_snapshot {where}
                    ORDER BY verified_at DESC LIMIT 1"""
                ),
                params,
            ).mappings().first()


def _as_datetime(value: datetime | str) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


from blueframe.providers.auth import Entitlements, UserProfile  # noqa: E402
