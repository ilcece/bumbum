export type ItemFacts = {
  issue_name?: string | null;
  edition_number?: number | null;
  issue_total?: number | null;
  rights?: { kind: string; rule_version?: string }[];
};

export function itemFacts(item: ItemFacts) {
  const width = item.issue_total ? String(item.issue_total).length : 3;
  const edition = item.edition_number
    ? `#${String(item.edition_number).padStart(width, "0")}${item.issue_total ? `/${item.issue_total}` : ""}`
    : item.issue_name ? "待核定" : null;
  return [
    { label: "发行", value: item.issue_name || null },
    { label: "发行编号", value: edition },
    { label: "数字权益", value: item.rights?.flatMap(({ kind }) => kind === "renewal" ? ["换新"] : kind === "resale" ? ["转售"] : []).join("、") || null },
  ].filter((fact): fact is { label: string; value: string } => fact.value !== null);
}
