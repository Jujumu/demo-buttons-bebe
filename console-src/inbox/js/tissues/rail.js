import { MAILBOX_TOPICS } from "../contracts.js";
import { esc } from "../util.js";
import { createCustomerTissue, renderCustomer } from "./customer.js";
import { createOrderHistoryTissue, renderOrderHistory } from "./order-history.js";
import { createOrderTissue, renderOrder } from "./order.js";
import { createReturnsTissue, renderReturns } from "./returns.js";

/**
 * Rail organ: customer + this order + returns + past orders.
 * Collapsibles are independent (not an accordion).
 */
export function createRailOrgan({ shop, mailbox }) {
  const customer = createCustomerTissue({ shop });
  const order = createOrderTissue({ shop });
  const returns = createReturnsTissue({ shop });
  const history = createOrderHistoryTissue({ shop, mailbox });

  const open = {
    customer: true,
    order: true,
    returns: false,
    "order-history": false,
    addresses: false,
    shipment: false,
  };

  let models = {
    customer: { ok: false, peek: "Customer", record: null },
    order: { ok: false, peek: "This order", record: null },
    returns: { ok: true, peek: "No returns", collapsedDefault: true, record: null },
    history: { ok: true, peek: "0", rows: [] },
  };
  let peekedHistoryId = null;
  let currentOrderId = null;

  function renderError(tissueId, label, peek, message) {
    return `<section class="rail-card is-error" data-tissue="${esc(tissueId)}" data-open="true">
      <button type="button" class="rail-toggle" data-toggle="${esc(tissueId)}" aria-expanded="true">
        <span>${esc(label)}</span><span class="peek">${esc(peek)}</span>
      </button>
      <div class="rail-body"><p class="tissue-error">${esc(message || "Unavailable")}</p></div>
    </section>`;
  }

  function render() {
    const customerHtml = models.customer.error
      ? renderError("customer", "Customer", models.customer.peek, models.customer.error)
      : renderCustomer(models.customer, { open: open.customer });
    const orderHtml = models.order.error
      ? renderError("order", "This order", models.order.peek, models.order.error)
      : renderOrder(models.order, {
        open: open.order,
        addressesOpen: open.addresses,
        shipmentOpen: models.order.hasTracking ? open.shipment : false,
      });
    const returnsOpen = open.returns || models.returns.inProgress;
    const returnsHtml = models.returns.error
      ? renderError("returns", "Returns", models.returns.peek, models.returns.error)
      : renderReturns(models.returns, { open: returnsOpen });
    const historyHtml = models.history.error
      ? renderError("order-history", "Past orders", models.history.peek, models.history.error)
      : renderOrderHistory(models.history, { open: open["order-history"], peekedId: peekedHistoryId });
    return `<div class="pane-inner rail-inner">
      ${customerHtml}
      ${orderHtml}
      ${returnsHtml}
      ${historyHtml}
    </div>`;
  }

  async function load({ shop: shopId, customerId, orderId }) {
    currentOrderId = orderId || null;
    peekedHistoryId = null;
    const [customerModel, orderModel, returnsModel, historyModel] = await Promise.all([
      customer.load({ shop: shopId, customerId }).catch((err) => ({ ok: false, peek: "Customer error", error: String(err?.message || err), record: null })),
      order.load({ shop: shopId, orderId }).catch((err) => ({ ok: false, peek: "Order error", error: String(err?.message || err), record: null })),
      returns.load({ shop: shopId, orderId }).catch((err) => ({ ok: false, peek: "Returns error", error: String(err?.message || err), collapsedDefault: true })),
      history.load({ shop: shopId, customerId }).catch((err) => ({ ok: false, peek: "0", rows: [], error: String(err?.message || err) })),
    ]);
    models = {
      customer: customerModel,
      order: orderModel,
      returns: returnsModel,
      history: historyModel,
    };
    open.returns = Boolean(returnsModel.inProgress);
    open.shipment = Boolean(orderModel.hasTracking);
    for (const [tissueId, model] of Object.entries({ customer: customerModel, order: orderModel, returns: returnsModel, "order-history": historyModel })) {
      if (model.error) mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId, message: model.error });
    }
    return models;
  }

  function mount(el) {
    el.innerHTML = render();
    el.onclick = (event) => {
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
    snapshot() {
      return {
        models,
        open: { ...open },
        peekedHistoryId,
        currentOrderId,
      };
    },
  };
}
