"""The content key of a producer-consumer pair (ADR 0008, decision 3).

The key is a hash of an explicit, canonical record of every input that can change what the pair's analysis says. Nothing is left to be
implied by another hash. Anything incidental (the time of the run, local paths, analysis ids, job ids) is not in the record, so the same
pinned inputs give the same key in a different analysis, on a different day, in a different process.
"""
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.hashing import canonical_json, sha256_hex

KEY_SCHEMA = "pair/1"
WITNESS_RULE = "3+3"


@dataclass(frozen=True)
class Side:
    """One project's place in the pair: where it came from and how its world was made."""
    repo: str                                    # owner/name
    commit: str                                  # pinned commit SHA
    project: str                                 # path of the project inside the repository
    manifests: dict[str, str]                    # manifest and lockfile path -> SHA-256 of its bytes
    world_hash: str | None
    source: str | None                           # "lockfile" or "resolver": how the world was made
    resolver: str | None                         # "uv" when uv resolved it, else the lockfile kind
    resolver_version: str | None                 # the pinned uv version, only when uv resolved it
    resolution: dict[str, Any] | None            # {exclude_newer, index, flags}: only when uv resolved it (a lockfile does not depend on them)
    platform: str | None
    python: str | None


@dataclass(frozen=True)
class PairKeyInput:
    producer: Side                               # the producer project whose reference world is used
    consumers: tuple[Side, ...]                  # every consumer that shares this projected world, sorted
    reference_world_hash: str
    consumer_world_hash: str                     # the projected consumer world that is tested
    producer_artifact_sha256: str                # the tree that is mounted and imported
    entries: tuple[str, ...]                     # the producer modules the consumers import
    oracles: dict[str, str] = field(default_factory=dict)      # oracle name -> version
    image: str = ""                              # the sandbox image (digest)
    resolver_logic: str = ""                     # which files count and how locks are read (resolvers.python.LOGIC_VERSION)
    witness_rule: str = WITNESS_RULE
    verdict_rule: str = ""
    static_rule: str = ""                        # how static exposure is read and when it may change an INCONCLUSIVE verdict (analysis.static)


def record(inp: PairKeyInput) -> dict:
    """The canonical record: plain JSON types, unordered collections sorted."""
    d = asdict(inp)
    d["consumers"] = sorted(d["consumers"], key=lambda s: (s["repo"], s["commit"], s["project"]))
    d["entries"] = sorted(d["entries"])
    return d


def pair_key(inp: PairKeyInput) -> str:
    return "pk_" + sha256_hex(f"{KEY_SCHEMA}\n".encode() + canonical_json(record(inp)))[:40]


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(obj, list):
        out = {}
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
        if not obj:
            out[prefix] = []
        return out
    return {prefix: obj}


def _by_consumer(rec: dict) -> dict:
    """Consumers keyed by repository and project, so that adding one does not shift the others."""
    return {**rec, "consumers": {f"{c['repo']}:{c['project']}": c for c in rec["consumers"]}}


def explain(a: dict, b: dict) -> list[dict]:
    """Which inputs differ between two records: [{input, before, after}], sorted by input path.

    A consumer that exists on one side only is reported once, as `consumers.<repo>:<project>`; the entry modules are reported as one list.
    """
    ra, rb = _by_consumer(a), _by_consumer(b)
    out: list[dict] = []
    for key in sorted(set(ra["consumers"]) ^ set(rb["consumers"])):
        out.append({"input": f"consumers.{key}", "before": "present" if key in ra["consumers"] else None,
                    "after": "present" if key in rb["consumers"] else None})
    fa = _flatten({k: v for k, v in ra.items() if k != "entries"})
    fb = _flatten({k: v for k, v in rb.items() if k != "entries"})
    onlyone = {f"consumers.{k}" for k in set(ra["consumers"]) ^ set(rb["consumers"])}
    out += [{"input": k, "before": fa.get(k), "after": fb.get(k)} for k in sorted(set(fa) | set(fb))
            if fa.get(k) != fb.get(k) and not any(k == o or k.startswith(o + ".") for o in onlyone)]
    if sorted(a["entries"]) != sorted(b["entries"]):
        out.append({"input": "entries", "before": sorted(a["entries"]), "after": sorted(b["entries"])})
    return sorted(out, key=lambda d: d["input"])
