-- 0008_pair_cell: which pair key each cell of an analysis was run under (M13.3). A workflow index, not evidence: the pair record
-- object holds the inputs, and the key is recomputable from the cell's own data.
CREATE TABLE pair_cell (
  cell_id TEXT PRIMARY KEY REFERENCES cell(id),
  analysis_id TEXT NOT NULL REFERENCES analysis(id),
  pair_key TEXT NOT NULL
);
CREATE INDEX ix_pair_cell_key ON pair_cell(pair_key);
