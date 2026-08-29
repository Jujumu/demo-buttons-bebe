import { esc, formatMoney } from "../util.js";

const IN_PROGRESS = new Set(["OPEN", "REQUESTED", "IN_PROGRESS", "PENDING"]);

/**
 * Returns rail tissue.
 * In: `{ shop, orderId }` via shop tissue.
 * Out: `returns` + returnStatus, in-progress flag, items, refund/credit, tracking.
 * Empty demo fixture: peek "No returns", collapsed.
 */
export function projectReturns(record) {
  const nodes = record?.returns?.nodes || [];
  const inProgress = Boolean(record?.inProgress) || nodes.some((node) => IN_PROGRESS.has(String(node.status || node.returnStatus || "").toUpperCase()));
  const returnStatus = record?.returnStatus || nodes[0]?.status || nodes[0]?.returnStatus || null;
  const empty = nodes.length === 0 && !(record?.items || []).length;
  return {
    ok: true,
    peek: empty ? "No returns" : (returnStatus || `${nodes.length} return${nodes.length === 1 ? "" : "s"}`),
    collapsedDefault: !inProgress,
    inProgress,
    record: {
      returns: { nodes },
      returnStatus,
      inProgress,
      items: record?.items || [],
      refundTotal: record?.refundTotal || null,
      creditTotal: record?.creditTotal || null,
      tracking: record?.tracking || null,
    },
  };
}

export function renderReturns(model, { open } = {}) {
  const isOpen = open == null ? !model.collapsedDefault : open;
  const rec = model.record;
  let body = `<p class="tissue-empty">No returns</p>`;
  if (rec && (rec.returns.nodes.length || rec.items.length)) {
    const items = rec.items.map((item) => (
      `<li>${esc(item.title)} · ${esc(item.reason || "—")} · ${esc(item.type || "—")}</li>`
    )).join("");
    body = `<ul class="return-items">${items || "<li>Return on file</li>"}</ul>
      <p>Status ${esc(rec.returnStatus || "—")}</p>
      <p>Refund ${esc(formatMoney(rec.refundTotal, "—"))} · Credit ${esc(formatMoney(rec.creditTotal, "—"))}</p>`;
  }
  return `<section class="rail-card" data-tissue="returns" data-open="${isOpen ? "true" : "false"}">
    <button type="button" class="rail-toggle" data-toggle="returns" aria-expanded="${isOpen ? "true" : "false"}">
      <span>Returns</span>
      <span class="peek">${esc(model.peek)}</span>
    </button>
    <div class="rail-body"${isOpen ? "" : " hidden"}>${body}</div>
  </section>`;
}

export function createReturnsTissue({ shop }) {
  return {
    id: "returns",
    async load({ shop: shopId, orderId }) {
      try {
        const record = await shop.getReturns({ shop: shopId, orderId });
        return projectReturns(record);
      } catch (err) {
        return {
          ok: false,
          peek: "Returns error",
          collapsedDefault: true,
          inProgress: false,
          record: null,
          error: String(err?.message || err),
        };
      }
    },
    project: projectReturns,
    render: renderReturns,
  };
}
