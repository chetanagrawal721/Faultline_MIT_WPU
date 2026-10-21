"""TC-13.3.3: the same pinned inputs analysed twice, in two separate analyses and databases, give the same pair key for every cell."""
import pytest

from faultline.evidence.object_store import FsObjectStore
from faultline.evidence.pair_key import explain
from faultline.evidence.runtime import objects_dir
from tests.integration.test_evidence_projection import analyse_scenario_d

pytestmark = pytest.mark.docker


def keys(conn, res) -> dict:
    return {r["cell_id"]: r["pair_key"] for r in conn.execute("SELECT cell_id, pair_key FROM pair_cell WHERE analysis_id=?", (res.analysis_id,))}


def test_the_same_pinned_inputs_give_the_same_pair_keys_in_two_analyses(daemon, image, tmp_path):
    runs = []
    for tag in ("_a", "_b"):                                 # fresh remote names: a second commit on one remote would have a parent and another SHA
        d = tmp_path / tag
        d.mkdir()
        runs.append(analyse_scenario_d(daemon, image, d, tag))
    (c1, r1), (c2, r2) = runs
    k1, k2 = keys(c1, r1), keys(c2, r2)
    analysed = [c for c in r1.cells if c["state"] == "ANALYZED"]
    assert len(analysed) == 1 and len(k1) == 1 and len(k2) == 1, "one pair key for each analysed cell"
    assert set(k1.values()) == set(k2.values()), "the pair key must not depend on the analysis"
    assert next(iter(k1)) != next(iter(k2)), "the cell ids do differ between analyses: the key is what is stable"
    key = next(iter(k1.values()))
    assert key.startswith("pk_") and c1.execute("SELECT COUNT(*) FROM pair_index WHERE pair_key=?", (key,)).fetchone()[0] == 1
    # the stored record explains the key, and the two analyses stored the very same object
    recs = []
    for conn in (c1, c2):
        oid = conn.execute("SELECT pair_record_id FROM pair_index WHERE pair_key=?", (key,)).fetchone()[0]
        got = FsObjectStore(objects_dir(conn)).get(oid)
        assert got.ok and got.payload["pair_key"] == key
        recs.append((oid, got.payload["inputs"]))
    assert recs[0][0] == recs[1][0] and explain(recs[0][1], recs[1][1]) == []
    inp = recs[0][1]
    assert inp["producer"]["repo"] == "faultline-demo/acme-models" and len(inp["producer"]["commit"]) == 40
    assert [c["repo"] for c in inp["consumers"]] == ["faultline-demo/notify-svc"] and inp["entries"] == ["acme_models.web"]
    assert inp["producer"]["manifests"] and inp["consumers"][0]["manifests"] and inp["image"].startswith("sha256:")
    assert set(inp["oracles"]) == {"o_import", "o_tests", "o_bind", "o_contract"} and inp["verdict_rule"] == "verdict-policy/1"
