"""The kinds of evidence object, their schema versions and the fields each must carry (ADR 0008).

A kind is registered with the newest schema version this code can read. An object written under a newer version is reported as
unsupported rather than corrupt, and is never used.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Kind:
    name: str
    version: int
    required: tuple[str, ...]


KINDS: dict[str, Kind] = {k.name: k for k in (
    Kind("oracle_result", 1, ("oracle", "oracle_version", "world_hash", "run")),
    Kind("witness", 1, ("witness_key", "oracle", "entry_point", "signature", "row", "slot", "seq")),
    Kind("attribution", 1, ("witness_key", "status", "minimal", "row", "attempts", "slot", "seq")),
    Kind("verdict", 1, ("finding", "verdict", "policy", "evidence", "slot", "seq")),
    Kind("fix_plan", 1, ("finding_id", "label", "row", "slot", "seq")),
    Kind("pair_record", 1, ("pair_key", "inputs")),
    Kind("ddmin_checkpoint", 1, ("minimisation_id", "seq", "state")),
    Kind("ddmin_test", 1, ("minimisation_id", "test_id", "subset", "direction", "outcome", "slot", "seq")),
    Kind("consumer_imports", 1, ("consumer_commit", "sites")),
    Kind("world_ref", 1, ("world_hash",)),
)}


class InvalidObject(ValueError):
    """The payload does not fit its kind (unknown kind, not an object, or a required field is missing)."""


def check_payload(kind: str, payload: object) -> Kind:
    k = KINDS.get(kind)
    if k is None:
        raise InvalidObject(f"unknown evidence kind {kind!r}")
    if not isinstance(payload, dict):
        raise InvalidObject(f"{kind} payload must be an object")
    missing = [f for f in k.required if f not in payload]
    if missing:
        raise InvalidObject(f"{kind} payload is missing {', '.join(missing)}")
    return k
