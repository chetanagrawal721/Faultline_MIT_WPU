import { api } from "../../api/client";
import { useAsync, short } from "../../lib/hooks";
import type { AppView } from "../../lib/route";
import { DataTable, Panel, Status } from "../../ui/primitives";
import { Loading } from "../shared";

const REASON: Record<string, string> = {
  REUSED: "Every input of the pair key is unchanged, so the stored result was used and no oracle ran.",
  NEW: "No stored result existed for this pair.",
  CHANGED: "An input changed since the last time these repositories were analysed.",
  REJECTED: "A stored object was damaged or missing, so it was not used and the pair was computed again.",
};

export function ReusePanel({ analysisId, status, go }: { analysisId: string; status: string; go: (view: AppView, id?: string | null) => void }) {
  // counted from the event log; read again when the analysis changes state, so a running analysis shows its counts as they happen
  const data = useAsync(() => Promise.all([api.counters(analysisId), api.pairs(analysisId)]), [analysisId, status]);
  const [counters, pairs] = data.data ?? [null, []];
  const metrics: [string, number | string, string][] = [
    ["Pairs reused", counters ? counters.pairs.reused : "—", "A stored result was found for the pair key"],
    ["Pairs recomputed", counters ? counters.pairs.recomputed : "—", "The pipeline ran for the pair and finished"],
    ["Stored objects rejected", counters ? counters.pairs.rejected_objects : "—", "Damaged or missing, not used"],
    ["Worlds reused / built", counters ? `${counters.worlds.reused} / ${counters.worlds.built}` : "—", "An existing world, or a build that ran"],
  ];
  return (
    <Panel title="Reuse and recomputation" meta={counters ? `${counters.events} recorded events` : "Loading"}>
      {data.loading && !data.data ? (
        <Loading what="reuse counters" />
      ) : (
        <>
          <div className="metric-strip" data-testid="reuse-counters">
            {metrics.map(([label, value, note]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
                <small>{note}</small>
              </div>
            ))}
          </div>
          {pairs.length === 0 ? (
            <p className="panel-copy">No pair was run in this analysis: a relationship with identical versions on both sides has nothing to run.</p>
          ) : (
            <DataTable
              testid="reuse-pairs"
              columns={["Pair", "Result", "Why", "Inputs that changed"]}
              rows={pairs.map((p) => [
                <code key="k" title={p.pair_key}>{short(p.pair_key, 14)}</code>,
                <Status key="s" tone={p.status === "REUSED" ? "good" : p.status === "UNFINISHED" ? "warn" : "neutral"}>
                  {p.status === "REUSED" ? "Reused" : p.status === "RECOMPUTED" ? "Recomputed" : "Unfinished"}
                </Status>,
                REASON[p.reason] ?? p.reason,
                p.changed.length ? p.changed.join(", ") : "—",
              ])}
              onRow={() => go("worlds")}
              rowAttrs={(i) => ({ "data-testid": `reuse-pair-${i}`, "data-status": pairs[i].status })}
            />
          )}
          <p className="panel-note">Counts come from the append-only event log. A reused pair is never counted as a fresh run.</p>
        </>
      )}
    </Panel>
  );
}
