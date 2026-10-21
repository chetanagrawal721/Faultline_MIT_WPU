"""Static evidence for a cell: which references in the artifact touch an API that changed between the reference world and the consumer's world.

This is the input of decision-table rows 5 to 8 (EXPOSED, POTENTIAL, NOT EXPOSED). It reads source and wheel contents; nothing is executed here, and
the wheels are parsed inside the sandbox. When any input cannot be read the result carries no evidence and says why: absence is never a pass.
"""
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from ..diff.delta import compute_delta
from ..resolvers.pinned import PinnedRequirement, render_lock
from ..usage.exposure import ExposureResult, compute_exposure
from ..usage.index import build_index
from ..verdicts import templates
from ..verdicts.engine import Evidence, Outcome, decide
from ..worlds.builder import WorldBuilder, WorldBuildError
from .bind import IMPORT_ALIASES


@dataclass
class StaticEvidence:
    result: ExposureResult | None = None
    why_not: str | None = None                                  # set when no evidence could be built
    packages: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)              # what was left out (packages that exist in one world only)

    def available(self) -> bool:
        return self.result is not None and bool(self.result.deltas)

    def to_json(self) -> dict:
        r = self.result
        return {"available": self.available(), "why_not": self.why_not, "packages": self.packages,
                "coverage": None if r is None else {"resolved": r.coverage.resolved, "total": r.coverage.total},
                "exposures": [] if r is None else [e.to_json() for e in r.breaking_exposures],
                "unresolved": [] if r is None else [u.to_json() for u in r.dynamic[:20]],
                "limits": ([] if r is None else list(r.static_limits)) + self.notes}


def import_root(distribution: str) -> str:
    key = distribution.lower().replace("_", "-")
    return IMPORT_ALIASES.get(key, key.replace("-", "_"))


def _wheel(builder: WorldBuilder, req: PinnedRequirement) -> tuple[str, str]:
    """(file name, sha256) of the one wheel of this pinned requirement in the wheelhouse, fetched by hash if it is not there yet."""
    files = builder.fetch_wheels(render_lock([req]))
    hits = [f for f in files if (not req.hashes or f["sha256"] in req.hashes) and f["name"].lower().replace("_", "-").startswith(req.name + "-" + req.version + "-")]
    if len(hits) != 1:
        raise WorldBuildError(f"expected one wheel of {req.name} {req.version}, found {len(hits)}")
    return hits[0]["name"], hits[0]["sha256"]


def collect(builder: WorldBuilder, delta, reference: list[PinnedRequirement], consumer: list[PinnedRequirement], sources: dict[str, bytes]) -> StaticEvidence:
    """`delta`: the cell's DeltaItems; `reference` and `consumer`: the pinned requirements of the two worlds; `sources`: the artifact's own Python source."""
    ref_by = {r.name: r for r in reference}
    con_by = {r.name: r for r in consumer}
    roots = {d.name: import_root(d.name) for d in delta}
    first = build_index(sources, set(roots.values()))
    referenced = {r.package for r in first.refs_to_divergent() if r.package}
    referenced_deltas = [d for d in delta if roots[d.name] in referenced]
    if not referenced_deltas:
        return StaticEvidence(why_not="the artifact does not refer to any package whose version differs")
    one_world = [d for d in referenced_deltas if d.name not in ref_by or d.name not in con_by]          # present in one world only: there is no pair of versions to compare
    wanted = [d for d in referenced_deltas if d not in one_world]
    if not wanted:
        return StaticEvidence(why_not=f"{', '.join(d.name for d in one_world)} exists in only one of the two worlds, so there is no API delta to read")
    index = build_index(sources, {roots[d.name] for d in wanted})
    deltas, packages = {}, []
    try:
        for d in wanted:
            (rf, rs), (cf, cs) = _wheel(builder, ref_by[d.name]), _wheel(builder, con_by[d.name])
            root = roots[d.name]
            old, new = builder.read_surface(rf, root, rs), builder.read_surface(cf, root, cs)
            if not old.symbols and not new.symbols and not (old.opaque_modules or new.opaque_modules):
                return StaticEvidence(why_not=f"no Python module named {root} was found in the wheels of {d.name}")
            ad = compute_delta(old, new)
            deltas[root] = ad
            packages.append({"distribution": d.name, "import_root": root, "from": ref_by[d.name].version, "to": con_by[d.name].version, "from_wheel": rs, "to_wheel": cs,
                             "breaking": ad.breaking, "incomplete": ad.incomplete})
    except WorldBuildError as e:
        return StaticEvidence(why_not=f"{e.message}")
    return StaticEvidence(compute_exposure(index, deltas), None, packages, [f"{d.name} exists in only one of the two worlds and was not compared" for d in one_world])


def headline(out, st: StaticEvidence, artifact: str) -> str:
    """The wording of an EXPOSED or POTENTIAL verdict that rests on static evidence (templates.static_headline): what the source and the API change say."""
    r = st.result
    pkg = {p["import_root"]: p for p in st.packages}
    why = "; ".join(out.reasons[:2]) or "the run did not settle it"
    if out.outcome == "EXPOSED":
        e = r.breaking_exposures[0]
        p = pkg.get(e.package, {"from": "?", "to": "?"})
        return templates.static_headline("EXPOSED", artifact=artifact, symbol=e.change.symbol, change_kind=e.change.change, v0=p["from"], v1=p["to"],
                                         reason=f"the run could not settle it ({why})")
    first = next((p for p in st.packages if p["breaking"]), st.packages[0])
    return templates.static_headline("POTENTIAL", artifact=artifact, package=first["distribution"], v0=first["from"], v1=first["to"], n_breaking=sum(len([x for x in d.entries if x.breaking]) for d in r.deltas.values()),
                                     n_dynamic=len(r.dynamic), examples=tuple(u.ref_id for u in r.dynamic[:3]), resolved=r.coverage.resolved, total=r.coverage.total)


def settle(base: Evidence, source: Callable[[], StaticEvidence] | None) -> tuple[Outcome, StaticEvidence | None, dict | None]:
    """(verdict, the static evidence it rests on or None, a note on static evidence that was read and not used or None).

    Static evidence is read only when execution left the result INCONCLUSIVE, and it may only raise it to EXPOSED or POTENTIAL. A witnessed, observed or
    not-applicable result is never changed, NOT EXPOSED is never taken from it (it would hide the run problem), and without evidence nothing changes."""
    out = decide(base)
    if out.outcome != "INCONCLUSIVE" or source is None:
        return out, None, None
    found = source()
    if not found.available():
        return out, None, {"considered": False, "why_not": found.why_not or "no API delta was computed"}
    raised = decide(replace(base, **found.result.evidence_fields()))
    if raised.outcome in ("EXPOSED", "POTENTIAL"):
        return raised, found, None
    return out, None, {"considered": True, "static_outcome": raised.outcome, "reasons": list(raised.reasons), **{k: v for k, v in found.to_json().items() if k in ("packages", "coverage", "limits")}}
