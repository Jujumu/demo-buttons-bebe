import { MAILBOX_TOPICS } from "../contracts.js";
import {
  esc,
  formatOrderCount,
  isPrivacyRequest,
  PRIVACY_HANDLED_LABEL,
  PRIVACY_LOCK_COPY,
  privacySubtypeLabel,
  requestTypeTitle,
  requestTypeWritePeek,
} from "../util.js";
import { createCustomerTissue, renderCustomer } from "./customer.js";
import { createOrderHistoryTissue, renderOrderHistory } from "./order-history.js";
import { createOrderTissue, renderOrder } from "./order.js";
import { createReturnsTissue, renderReturns } from "./returns.js";

/** Locked first-paint defaults. Addresses and past orders never start open. */
export const RAIL_DEFAULTS = Object.freeze({
  customer: true,
  order: true,
  returns: false,
  "order-history": false,
  addresses: false,
  shipment: false,
  giftCards: false,
  discounts: false,
  invoice: false,
  warranty: false,
  eta: false,
});

/**
 * Rail organ: customer + this order + returns + past orders.
 * Collapsibles are independent (not an accordion).
 */
export function createRailOrgan({ shop, mailbox }) {
  const customer = createCustomerTissue({ shop });
  const order = createOrderTissue({ shop });
  const returns = createReturnsTissue({ shop });
  const history = createOrderHistoryTissue({ shop, mailbox });

  const open = { ...RAIL_DEFAULTS };

  let models = {
    customer: { ok: false, peek: "Customer", record: null },
    order: { ok: false, peek: "This order", record: null },
    returns: { ok: true, peek: "No returns", collapsedDefault: true, record: null },
    history: { ok: true, peek: formatOrderCount(0), rows: [] },
  };
  let peekedHistoryId = null;
  let currentOrderId = null;
  let currentTicketKey = null;
  let lastLoad = {
    shop: "",
    customerId: "",
    orderId: "",
    ticketId: "",
    requestType: "",
    privacySubtype: "",
    privacyHandled: false,
  };

  function ticketKey({ ticketId, customerId, orderId }) {
    if (ticketId) return `ticket:${ticketId}`;
    return `order:${customerId || ""}:${orderId || ""}`;
  }

  function applyLockDefaults(returnsModel, orderModel, customerModel) {
    Object.assign(open, RAIL_DEFAULTS);
    open.returns = Boolean(returnsModel?.inProgress);
    open.shipment = Boolean(orderModel?.hasTracking);
    open.giftCards = Boolean(customerModel?.hasGiftCards);
    open.discounts = Boolean(orderModel?.hasDiscounts);
    open.invoice = Boolean(orderModel?.hasInvoice);
    open.warranty = Boolean(orderModel?.hasWarranty);
    open.eta = Boolean(orderModel?.hasEta);
  }

  const ERROR_LABEL = {
    customer: "Customer",
    order: "Order",
    returns: "Returns",
    "order-history": "History",
  };

  function errorCopy(tissueId) {
    return `Couldn't load ${ERROR_LABEL[tissueId] || "section"}. Retry.`;
  }

  function renderError(tissueId, label, peek) {
    return `<section class="rail-card is-error" data-tissue="${esc(tissueId)}" data-open="true">
      <button type="button" class="rail-toggle" data-toggle="${esc(tissueId)}" aria-expanded="true">
        <h2>${esc(label)}</h2><span class="peek">${esc(peek)}</span>
      </button>
      <div class="rail-body">
        <p class="tissue-error">${esc(errorCopy(tissueId))}</p>
        <button type="button" class="btn-hairline" data-retry="${esc(tissueId)}">Retry</button>
      </div>
    </section>`;
  }

  function renderPreference() {
    const typed = lastLoad.requestType;
    const title = requestTypeTitle(typed);
    if (!title) return "";
    const subtype = privacySubtypeLabel(lastLoad.privacySubtype);
    const peek = isPrivacyRequest(typed)
      ? (subtype || "No Shopify write")
      : "No Shopify write";
    const line = isPrivacyRequest(typed)
      ? PRIVACY_LOCK_COPY
      : requestTypeWritePeek(typed);
    const handled = Boolean(lastLoad.privacyHandled);
    const action = isPrivacyRequest(typed)
      ? (handled
        ? `<p class="mute preference-handled">Privacy handled</p>`
        : `<button type="button" class="btn-hairline" data-privacy-gate-open>${esc(PRIVACY_HANDLED_LABEL)}</button>`)
      : "";
    return `<section class="rail-card" data-tissue="preference" data-open="true" data-request-type="${esc(typed)}">
      <div class="rail-static">
        <h2>${esc(title)}</h2>
        <span class="peek">${esc(peek)}</span>
      </div>
      <div class="rail-body">
        <p class="mute preference-line">${esc(line)}</p>
        ${action}
      </div>
    </section>`;
  }

  function render() {
    const customerHtml = models.customer.error
      ? renderError("customer", "Customer", models.customer.peek)
      : renderCustomer(models.customer, { open: open.customer, giftCardsOpen: open.giftCards });
    const orderHtml = models.order.error
      ? renderError("order", "This order", models.order.peek)
      : renderOrder(models.order, {
        open: open.order,
        addressesOpen: open.addresses,
        shipmentOpen: open.shipment,
        discountsOpen: open.discounts,
        invoiceOpen: open.invoice,
        warrantyOpen: open.warranty,
        etaOpen: open.eta,
      });
    const returnsHtml = models.returns.error
      ? renderError("returns", "Returns", models.returns.peek)
      : renderReturns(models.returns, { open: open.returns });
    const historyRows = (models.history.rows || []).filter((row) => row.id !== currentOrderId);
    const historyView = models.history.error
      ? models.history
      : { ...models.history, peek: formatOrderCount(historyRows.length), rows: historyRows };
    const historyHtml = models.history.error
      ? renderError("order-history", "Past orders", models.history.peek)
      : renderOrderHistory(historyView, { open: open["order-history"], peekedId: peekedHistoryId });
    return `<div class="pane-inner rail-inner">
      ${renderPreference()}
      ${customerHtml}
      ${orderHtml}
      ${returnsHtml}
      ${historyHtml}
    </div>`;
  }

  async function loadTissue(tissueId, { shop: shopId, customerId, orderId }) {
    if (tissueId === "customer") {
      return customer.load({ shop: shopId, customerId }).catch((err) => ({
        ok: false, peek: "Customer error", error: String(err?.message || err), record: null,
      }));
    }
    if (tissueId === "order") {
      return order.load({ shop: shopId, orderId }).catch((err) => ({
        ok: false, peek: "Order error", error: String(err?.message || err), record: null, skuLabels: [], addressPeek: "—",
      }));
    }
    if (tissueId === "returns") {
      return returns.load({ shop: shopId, orderId }).catch((err) => ({
        ok: false, peek: "Returns error", error: String(err?.message || err), collapsedDefault: true, inProgress: false,
      }));
    }
    return history.load({ shop: shopId, customerId }).catch((err) => ({
      ok: false, peek: formatOrderCount(0), rows: [], error: String(err?.message || err),
    }));
  }

  async function load({ shop: shopId, customerId, orderId, ticketId, requestType, privacySubtype, privacyHandled }) {
    lastLoad = {
      shop: shopId,
      customerId,
      orderId,
      ticketId,
      requestType: requestType || "",
      privacySubtype: privacySubtype || "",
      privacyHandled: Boolean(privacyHandled),
    };
    const nextKey = ticketKey({ ticketId, customerId, orderId });
    const switched = nextKey !== currentTicketKey;
    currentTicketKey = nextKey;
    currentOrderId = orderId || null;
    peekedHistoryId = null;
    const [customerModel, orderModel, returnsModel, historyModel] = await Promise.all([
      loadTissue("customer", lastLoad),
      loadTissue("order", lastLoad),
      loadTissue("returns", lastLoad),
      loadTissue("order-history", lastLoad),
    ]);
    models = {
      customer: customerModel,
      order: orderModel,
      returns: returnsModel,
      history: historyModel,
    };
    if (switched) applyLockDefaults(returnsModel, orderModel, customerModel);
    for (const [tissueId, model] of Object.entries({ customer: customerModel, order: orderModel, returns: returnsModel, "order-history": historyModel })) {
      if (model.error) mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId, message: model.error });
    }
    return models;
  }

  async function retry(tissueId) {
    const key = tissueId === "order-history" ? "history" : tissueId;
    const next = await loadTissue(tissueId, lastLoad);
    models[key] = next;
    if (next.error) mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId, message: next.error });
    return next;
  }

  function mount(el) {
    el.innerHTML = render();
    el.onclick = (event) => {
      const privacyGate = event.target.closest("[data-privacy-gate-open]");
      if (privacyGate) {
        mailbox.publish(MAILBOX_TOPICS.PRIVACY_GATE_OPEN, {});
        return;
      }
      const gate = event.target.closest("[data-write-gate-open]");
      if (gate) {
        mailbox.publish(MAILBOX_TOPICS.WRITE_GATE_OPEN, {});
        return;
      }
      const retryBtn = event.target.closest("[data-retry]");
      if (retryBtn) {
        retry(retryBtn.dataset.retry).then(() => {
          el.innerHTML = render();
        });
        return;
      }
      const historyRow = event.target.closest("[data-history]");
      if (historyRow) {
        peekedHistoryId = historyRow.dataset.history;
        mailbox.publish(MAILBOX_TOPICS.HISTORY_PEEK, { orderId: peekedHistoryId, currentOrderId });
        el.innerHTML = render();
        return;
      }
      const toggle = event.target.closest("[data-toggle]");
      if (!toggle) return;
      const key = toggle.dataset.toggle;
      open[key] = !open[key];
      el.innerHTML = render();
    };
  }

  return {
    id: "rail",
    load,
    render,
    mount,
    toggle(key) {
      if (!(key in open)) return open[key];
      open[key] = !open[key];
      return open[key];
    },
    retry,
    snapshot() {
      return {
        models,
        open: { ...open },
        peekedHistoryId,
        currentOrderId,
        currentTicketKey,
      };
    },
  };
}
