"""The evidence store contract (ADR 0008). Objects are immutable; an id names exactly one content."""
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    CORRUPT = "CORRUPT"             # the bytes do not match the id, or are not a valid envelope
    UNSUPPORTED = "UNSUPPORTED"     # an unknown kind or a schema version newer than this code reads


@dataclass(frozen=True)
class Result:
    status: Status
    id: str
    kind: str | None = None
    payload: Any = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is Status.OK


class EvidenceStore(ABC):
    @abstractmethod
    def put(self, kind: str, payload: dict) -> str:
        """Canonicalise, hash, write atomically, verify, and return the id. The same content always returns the same id."""

    @abstractmethod
    def get(self, object_id: str) -> Result:
        """Read and verify one object. Never returns a payload unless the bytes match the id."""

    @abstractmethod
    def exists(self, object_id: str) -> bool: ...

    @abstractmethod
    def link(self, parent: str, relation: str, child: str) -> None:
        """Append a typed provenance edge. Edges are never rewritten."""

    @abstractmethod
    def edges(self, parent: str | None = None) -> list[tuple[str, str, str]]: ...

    @abstractmethod
    def iter_objects(self) -> Iterator[tuple[str, Status]]:
        """Every stored object id with the result of verifying it (used by rebuild and verify_all)."""

    @abstractmethod
    def verify_all(self) -> dict[str, int]:
        """Counts by status; changes nothing."""
