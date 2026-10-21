"""M13.3: the pair key is deterministic, changes with every real input, and ignores everything incidental."""
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from faultline.evidence.pair_key import PairKeyInput, Side, explain, pair_key, record
from faultline.evidence.pairs import side_of
from faultline.storage.db import connect
from faultline.storage.migrate import migrate

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")


def side(**kw) -> Side:
    base = dict(repo="acme/models", commit="a" * 40, project=".", manifests={"requirements.lock.txt": "1" * 64, "pyproject.toml": "2" * 64},
                world_hash="w_ref", source="resolver", resolver="uv", resolver_version="0.13.0",
                resolution={"exclude_newer": "2024-10-30T00:00:00Z", "index": "https://pypi.org/simple", "flags": ["--universal", "--no-build"]},
                platform="linux-x86_64", python="3.12")
    return Side(**{**base, **kw})


def base() -> PairKeyInput:
    return PairKeyInput(
        producer=side(), consumers=(side(repo="acme/notify", commit="b" * 40, world_hash="w_c1", source="lockfile", resolver="requirements",
                                         resolver_version=None, resolution=None, manifests={"requirements.txt": "3" * 64}),),
        reference_world_hash="w_ref", consumer_world_hash="w_test", producer_artifact_sha256="a_" + "9" * 40, entries=("acme_models.web", "acme_models.core"),
        oracles={"o_import": "1.0.0", "o_tests": "1.0.0", "o_bind": "1.0.0", "o_contract": "1.0.0"}, image="sha256:" + "e" * 64,
        resolver_logic="6", verdict_rule="verdict-policy/1")


def test_the_key_is_deterministic_across_processes_and_orderings():          # TC-13.3.1
    k = pair_key(base())
    assert k == pair_key(base()) and k.startswith("pk_") and len(k) == 43
    code = ("import sys; sys.path.insert(0, sys.argv[1]);"
            "from tests.unit.test_pair_key import base; from faultline.evidence.pair_key import pair_key; print(pair_key(base()))")
    out = subprocess.run([sys.executable, "-c", code, BACKEND], capture_output=True, text=True, cwd=Path(BACKEND).parent, env={"PYTHONPATH": os.pathsep.join([BACKEND, str(Path(BACKEND).parent)])})
    assert out.stdout.strip() == k, out.stderr
    b = base()
    shuffled = replace(b, entries=tuple(reversed(b.entries)), producer=replace(b.producer, manifests=dict(reversed(list(b.producer.manifests.items())))),
                       oracles=dict(reversed(list(b.oracles.items()))))
    assert pair_key(shuffled) == k
    two = replace(b, consumers=(side(repo="acme/orders", commit="c" * 40), b.consumers[0]))
    assert pair_key(two) == pair_key(replace(two, consumers=tuple(reversed(two.consumers))))      # the order of consumers does not matter


# every real input, changed alone: (name, function that returns the changed input, the path explain must report)
MUTATIONS = {
    "producer commit": (lambda b: replace(b, producer=replace(b.producer, commit="d" * 40)), "producer.commit"),
    "producer repository": (lambda b: replace(b, producer=replace(b.producer, repo="acme/other")), "producer.repo"),
    "producer project path": (lambda b: replace(b, producer=replace(b.producer, project="libs/models")), "producer.project"),
    "consumer commit": (lambda b: replace(b, consumers=(replace(b.consumers[0], commit="f" * 40),)), "consumers.acme/notify:..commit"),
    "consumer repository": (lambda b: replace(b, consumers=(replace(b.consumers[0], repo="acme/billing"),)), ["consumers.acme/billing:.", "consumers.acme/notify:."]),
    "extra consumer": (lambda b: replace(b, consumers=(*b.consumers, side(repo="acme/zzz", commit="1" * 40))), "consumers.acme/zzz:."),
    "producer artifact byte": (lambda b: replace(b, producer_artifact_sha256="a_" + "8" * 40), "producer_artifact_sha256"),
    "producer lockfile": (lambda b: replace(b, producer=replace(b.producer, manifests={**b.producer.manifests, "requirements.lock.txt": "4" * 64})),
                          "producer.manifests.requirements.lock.txt"),
    "consumer lockfile": (lambda b: replace(b, consumers=(replace(b.consumers[0], manifests={"requirements.txt": "5" * 64}),)),
                          "consumers.acme/notify:..manifests.requirements.txt"),
    "reference world": (lambda b: replace(b, reference_world_hash="w_other"), "reference_world_hash"),
    "consumer world": (lambda b: replace(b, consumer_world_hash="w_other"), "consumer_world_hash"),
    "resolver version": (lambda b: replace(b, producer=replace(b.producer, resolver_version="0.14.0")), "producer.resolver_version"),
    "resolution cut-off": (lambda b: replace(b, producer=replace(b.producer, resolution={**b.producer.resolution, "exclude_newer": "2025-01-01T00:00:00Z"})),
                           "producer.resolution.exclude_newer"),
    "resolution index": (lambda b: replace(b, producer=replace(b.producer, resolution={**b.producer.resolution, "index": "https://mirror.example/simple"})),
                         "producer.resolution.index"),
    "platform": (lambda b: replace(b, producer=replace(b.producer, platform="linux-aarch64")), "producer.platform"),
    "python version": (lambda b: replace(b, producer=replace(b.producer, python="3.13")), "producer.python"),
    "entry modules": (lambda b: replace(b, entries=(*b.entries, "acme_models.extra")), "entries"),
    "o_import version": (lambda b: replace(b, oracles={**b.oracles, "o_import": "1.1.0"}), "oracles.o_import"),
    "o_tests version": (lambda b: replace(b, oracles={**b.oracles, "o_tests": "1.1.0"}), "oracles.o_tests"),
    "o_bind version": (lambda b: replace(b, oracles={**b.oracles, "o_bind": "1.1.0"}), "oracles.o_bind"),
    "o_contract version": (lambda b: replace(b, oracles={**b.oracles, "o_contract": "1.1.0"}), "oracles.o_contract"),
    "sandbox image": (lambda b: replace(b, image="sha256:" + "0" * 64), "image"),
    "resolver logic": (lambda b: replace(b, resolver_logic="7"), "resolver_logic"),
    "witness rule": (lambda b: replace(b, witness_rule="2+2"), "witness_rule"),
    "verdict rule": (lambda b: replace(b, verdict_rule="verdict-policy/2"), "verdict_rule"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_every_real_input_changes_the_key(name):                              # TC-13.3.2
    mutate, _ = MUTATIONS[name]
    assert pair_key(mutate(base())) != pair_key(base()), name


def test_all_mutated_keys_are_different_from_each_other():
    keys = {n: pair_key(m(base())) for n, (m, _) in MUTATIONS.items()}
    assert len(set(keys.values())) == len(keys)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_explain_names_exactly_the_changed_input(name):                      # TC-13.3.4
    mutate, path = MUTATIONS[name]
    diff = explain(record(base()), record(mutate(base())))
    assert [d["input"] for d in diff] == (path if isinstance(path, list) else [path]), diff
    assert explain(record(base()), record(base())) == []


def test_the_record_holds_nothing_incidental():
    text = json.dumps(record(base()))
    for needle in ("analysis", "job_", "cell_", "created_at", "\\\\", "C:/", "tmp"):
        assert needle not in text, needle


# ---- how the inputs are read from the database: the audit's rule about resolution settings (M13.0, section 7) --------------------

def seeded(tmp_path, source: str, resolved_at: str) -> sqlite3.Connection:
    c = connect(tmp_path / "k.db")
    migrate(c)
    c.execute("PRAGMA foreign_keys=OFF")               # only the rows side_of reads are seeded
    c.execute("INSERT INTO repository(id, analysis_project_id, owner, name, status) VALUES ('r1','ap','acme','models','INGESTED')")
    c.execute("INSERT INTO snapshot(id, repository_id, sha, committed_at, store_path, ingest_status) VALUES ('s1','r1',?, 't','p','OK')", ("a" * 40,))
    c.execute("INSERT INTO project(id, snapshot_id, rel_path, ecosystem) VALUES ('p1','s1','.','pypi')")
    c.execute("INSERT INTO manifest(id, project_id, path, kind, content_hash, parse_status) VALUES ('m1','p1','requirements.txt','requirements',?, 'OK')", ("7" * 64,))
    args = {"platform": "linux-x86_64", "python": "3.12", "index": "https://pypi.org/simple", "flags": ["--no-build"], "resolver_version": "0.13.0"}
    c.execute("INSERT INTO project_world(id, project_id, world_hash, source, resolver, resolver_args_json, resolved_at, status) VALUES ('pw','p1','w_1',?, 'requirements',?,?, 'OK')",
              (source, json.dumps(args), resolved_at))
    return c


def two_dirs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    return a, b


def test_a_lockfile_world_ignores_the_resolution_cutoff(tmp_path):
    da, db = two_dirs(tmp_path)
    a = side_of(seeded(da, "lockfile", "2024-10-30T00:00:00Z"), "p1")
    b = side_of(seeded(db, "lockfile", "2025-06-01T00:00:00Z"), "p1")
    assert a == b and a.resolution is None and a.resolver_version is None


def test_a_uv_resolved_world_depends_on_the_cutoff(tmp_path):
    da, db = two_dirs(tmp_path)
    a = side_of(seeded(da, "resolver", "2024-10-30T00:00:00Z"), "p1")
    b = side_of(seeded(db, "resolver", "2025-06-01T00:00:00Z"), "p1")
    assert a != b and a.resolution["exclude_newer"] == "2024-10-30T00:00:00Z" and a.resolver == "uv" and a.resolver_version == "0.13.0"
    assert pair_key(replace(base(), producer=a)) != pair_key(replace(base(), producer=b))
