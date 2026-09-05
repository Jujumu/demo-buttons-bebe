import { MAILBOX_TOPICS, MARKETING_LOCKED_COPY, PAYMENTS_LOCKED_COPY, PRIVACY_LOCKED_COPY, CUSTOMER_JOIN_LOCKED_COPY, ORDER_LINK_LOCKED_COPY } from "./contracts.js";
import { SHOP, STORE_NAME, macros as fixtureMacros, ticketInView, tickets as fixtureTickets, viewCounts, views } from "./fixtures/demo-inbox.js";
import { createMailbox } from "./mailbox.js";
import { createHelpdeskShop } from "./shop/helpdesk-shop.js";
import { createComposerTissue } from "./tissues/composer.js";
import { createListTissue } from "./tissues/list.js";
import { createRailOrgan } from "./tissues/rail.js";
import { createThreadTissue } from "./tissues/thread.js";
import { forbiddenControlHits, GATE_CONFIRM_LABEL } from "./util.js";

const RAIL_EXPAND_ICON = `<svg class="list-expand-icon" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M9 2.5 4.5 7 9 11.5"/>
</svg>`;

function withRecipient(ticket, email) {
  if (!ticket) return null;
  return {
    ...ticket,
    toEmail: email || "",
  };
}

function safeMount(tissue, el, input) {
  try {
    if (input) tissue.update?.(input);
    tissue.mount(el);
    return { ok: true };
  } catch (err) {
    el.innerHTML = `<div class="tissue-error" data-tissue-error="${tissue.id}">${tissue.id} unavailable</div>`;
    return { ok: false, error: String(err?.message || err) };
  }
}

/**
 * Inbox organ: list + thread + rail + composer.
 * Views live in the list filter menu (no separate views pane).
 * One tissue error stays in its pane.
 */
export function createInboxOrgan(opts = {}) {
  const mailbox = opts.mailbox || createMailbox();
  const shop = opts.shop || createHelpdeskShop({ fail: opts.fail });
  const shopHost = opts.shopHost || shop.shop || SHOP;
  const pinnedCatalog = opts.tickets || null;
  const listTissue = createListTissue({ mailbox });
  const threadTissue = createThreadTissue({ mailbox });
  const composerTissue = createComposerTissue({ mailbox });
  const rail = createRailOrgan({ shop, mailbox });

  let viewId = opts.viewId || "mine";
  let selectedId = opts.ticketId || null;
  let body = "";
  let strip = "";
  let summarizeText = "";
  let discarded = false;
  let sent = [];
  let toEmail = "";
  let macros = fixtureMacros;
  let macroQuery = "";
  let selectedMacroId = "";
  let macrosOpen = false;
  let listCollapsed = false;
  let railCollapsed = false;
  /** Session-local unread ids. Fixtures start unread; selecting marks read. No Shopify field. */
  const unreadIds = new Set(
    (pinnedCatalog || fixtureTickets).map((ticket) => ticket.id).filter(Boolean),
  );
  let writeGate = {
    mutationsEnabled: false,
    refused: ["send", "refund", "cancel"],
    message: "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.",
  };
  let writeGateOpen = false;
  let customerJoinGateOpen = false;
  let orderLinkGateOpen = false;
  let privacyGateOpen = Boolean(opts.privacyGate);
  let marketingGateOpen = Boolean(opts.marketingGate);
  let listRows = pinnedCatalog ? pinnedCatalog.filter((ticket) => ticketInView(ticket, viewId)) : [];
  let selected = pinnedCatalog?.find((ticket) => ticket.id === selectedId) || null;
  let counts = pinnedCatalog ? viewCounts(pinnedCatalog) : viewCounts(fixtureTickets);

  function markRead(ticketId) {
    if (ticketId) unreadIds.delete(ticketId);
  }

  function visibleTickets() {
    return listRows;
  }

  function selectedTicket() {
    return selected || listRows.find((ticket) => ticket.id === selectedId) || null;
  }

  function ensureSelection() {
    const visible = visibleTickets();
    if (!visible.some((ticket) => ticket.id === selectedId)) {
      selectedId = visible[0]?.id || null;
    }
    if (selectedId) markRead(selectedId);
  }

  async function refreshList() {
    if (pinnedCatalog) {
      listRows = pinnedCatalog.filter((ticket) => ticketInView(ticket, viewId));
      counts = viewCounts(pinnedCatalog);
      return;
    }
    if (typeof shop.listTickets === "function") {
      try {
        const [rows, ...viewRows] = await Promise.all([
          shop.listTickets({ view: viewId, limit: 50 }),
          ...views.map((view) => shop.listTickets({ view: view.id, limit: 100 })),
        ]);
        if (Array.isArray(rows)) listRows = rows;
        counts = Object.fromEntries(views.map((view, index) => [
          view.id,
          Array.isArray(viewRows[index]) ? viewRows[index].length : 0,
        ]));
        return;
      } catch {
        // fixture fallback below
      }
    }
    listRows = fixtureTickets.filter((ticket) => ticketInView(ticket, viewId));
    counts = viewCounts(fixtureTickets);
  }

  async function refreshThread() {
    const id = selectedId;
    if (!id) {
      selected = null;
      return;
    }
    if (pinnedCatalog) {
      selected = pinnedCatalog.find((ticket) => ticket.id === id) || null;
      return;
    }
    if (typeof shop.getTicket === "function") {
      try {
        const ticket = await shop.getTicket({ ticketId: id });
        if (ticket) {
          selected = ticket;
          return;
        }
      } catch {
        // fixture fallback below
      }
    }
    selected = fixtureTickets.find((ticket) => ticket.id === id)
      || listRows.find((ticket) => ticket.id === id)
      || null;
  }

  function closeAllGates() {
    writeGateOpen = false;
    privacyGateOpen = false;
    marketingGateOpen = false;
    customerJoinGateOpen = false;
    orderLinkGateOpen = false;
  }

  function gateSheetHtml() {
    if (privacyGateOpen) {
      return `<div class="gate-sheet-backdrop" data-gate-sheet data-privacy-gate>
        <div class="gate-sheet" role="dialog" aria-modal="true" aria-labelledby="gate-sheet-copy">
          <p id="gate-sheet-copy">${PRIVACY_LOCKED_COPY}</p>
          <div class="gate-sheet-actions">
            <button type="button" class="btn-ink" data-privacy-handled>${GATE_CONFIRM_LABEL}</button>
            <button type="button" class="btn-hairline" data-gate-dismiss>Close</button>
          </div>
        </div>
      </div>`;
    }
    if (marketingGateOpen) {
      return `<div class="gate-sheet-backdrop" data-gate-sheet data-marketing-gate>
        <div class="gate-sheet" role="dialog" aria-modal="true" aria-labelledby="gate-sheet-copy">
          <p id="gate-sheet-copy">${MARKETING_LOCKED_COPY}</p>
          <div class="gate-sheet-actions">
            <button type="button" class="btn-ink" data-unsubscribe-handled>${GATE_CONFIRM_LABEL}</button>
            <button type="button" class="btn-hairline" data-gate-dismiss>Close</button>
          </div>
        </div>
      </div>`;
    }
    if (customerJoinGateOpen) {
      return `<div class="gate-sheet-backdrop" data-gate-sheet data-customer-join-gate>
        <div class="gate-sheet" role="dialog" aria-modal="true" aria-labelledby="gate-sheet-copy">
          <p id="gate-sheet-copy">${CUSTOMER_JOIN_LOCKED_COPY}</p>
          <div class="gate-sheet-actions">
            <button type="button" class="btn-hairline" data-gate-dismiss>Close</button>
          </div>
        </div>
      </div>`;
    }
    if (orderLinkGateOpen) {
      return `<div class="gate-sheet-backdrop" data-gate-sheet data-order-link-gate>
        <div class="gate-sheet" role="dialog" aria-modal="true" aria-labelledby="gate-sheet-copy">
          <p id="gate-sheet-copy">${ORDER_LINK_LOCKED_COPY}</p>
          <div class="gate-sheet-actions">
            <button type="button" class="btn-hairline" data-gate-dismiss>Close</button>
          </div>
        </div>
      </div>`;
    }
    if (!writeGateOpen) return "";
    return `<div class="gate-sheet-backdrop" data-gate-sheet>
      <div class="gate-sheet" role="dialog" aria-modal="true" aria-labelledby="gate-sheet-copy">
        <p id="gate-sheet-copy">${PAYMENTS_LOCKED_COPY}</p>
        <div class="gate-sheet-actions">
          <button type="button" class="btn-hairline" data-gate-dismiss>Close</button>
        </div>
      </div>
    </div>`;
  }

  function railCollapsedHtml() {
    return `<div class="pane-inner">
      <button type="button" class="rail-expand-btn" data-rail-expand aria-label="Expand customer rail" title="Show customer rail">
        ${RAIL_EXPAND_ICON}
        <span class="rail-expand-label">Customer</span>
      </button>
    </div>`;
  }

  function shell() {
    return `<div class="inbox" data-organ="inbox">
      <a class="skip-link" href="#inbox-thread">Skip to thread.</a>
      <section class="pane pane-list${listCollapsed ? " is-collapsed" : ""}" data-pane="list"></section>
      <section class="pane pane-thread" id="inbox-thread" data-pane="thread" tabindex="-1">
        <div data-slot="thread"></div>
        <div data-slot="composer"></div>
      </section>
      <aside class="pane pane-rail${railCollapsed ? " is-collapsed" : ""}" data-pane="rail"></aside>
    </div>
    <div data-gate-host></div>`;
  }

  async function loadDraft(ticket) {
    if (!ticket) return "";
    if (typeof shop.draftReply === "function") {
      try {
        const railSnap = rail.snapshot();
        const result = await shop.draftReply({
          ticketId: ticket.id,
          shop: shopHost,
          thread: ticket,
          customerId: ticket.customerId,
          orderId: ticket.orderId,
          customer: railSnap.models.customer?.record,
          order: railSnap.models.order?.record,
          returns: railSnap.models.returns?.record,
          pastOrders: railSnap.models.history?.rows,
        });
        if (result?.draft) return result.draft;
      } catch {
        // fixture fallback below
      }
    }
    return ticket.stubDraft || "";
  }

  async function loadSummary(ticket) {
    if (!ticket) return "";
    if (typeof shop.summarizeThread === "function") {
      try {
        const result = await shop.summarizeThread({
          ticketId: ticket.id,
          shop: shopHost,
          thread: ticket,
        });
        if (result?.summary) return result.summary;
      } catch {
        // fixture fallback below
      }
    }
    return ticket.stubSummary || "";
  }

  async function refreshComposer() {
    const ticket = selectedTicket();
    discarded = false;
    summarizeText = "";
    strip = ticket ? await loadDraft(ticket) : "";
  }

  async function refreshWriteGate() {
    if (typeof shop.writeGateStatus === "function") {
      try {
        const result = await shop.writeGateStatus();
        if (result && Array.isArray(result.refused)) writeGate = result;
      } catch {
        // keep default gated copy
      }
    }
  }

  async function escalateSelected(reason) {
    const ticket = selectedTicket();
    if (!ticket || ticket.escalated) return ticket;
    if (typeof shop.escalateTicket === "function") {
      try {
        const result = await shop.escalateTicket({ ticketId: ticket.id, reason });
        if (result) {
          selected = result;
          return result;
        }
      } catch {
        // local flag below
      }
    }
    selected = {
      ...ticket,
      escalated: true,
      escalationReason: reason || "",
      statusEvents: [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "escalated" },
      ],
    };
    return selected;
  }

  async function markPrivacyHandled() {
    const ticket = selectedTicket();
    if (!ticket || ticket.requestType !== "privacy_request") return ticket;
    if (typeof shop.markPrivacyHandled === "function") {
      try {
        const result = await shop.markPrivacyHandled({ ticketId: ticket.id });
        if (result) {
          selected = result;
          privacyGateOpen = false;
          return result;
        }
      } catch {
        // local flag below
      }
    }
    selected = {
      ...ticket,
      privacyHandled: true,
      statusEvents: [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "privacy handled" },
      ],
    };
    privacyGateOpen = false;
    return selected;
  }

  async function markUnsubscribed() {
    const ticket = selectedTicket();
    if (!ticket || ticket.requestType !== "marketing_unsubscribe") return ticket;
    if (typeof shop.markUnsubscribed === "function") {
      try {
        const result = await shop.markUnsubscribed({ ticketId: ticket.id });
        if (result) {
          selected = result;
          marketingGateOpen = false;
          return result;
        }
      } catch {
        // local flag below
      }
    }
    selected = {
      ...ticket,
      unsubscribeHandled: true,
      statusEvents: [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "unsubscribed" },
      ],
    };
    marketingGateOpen = false;
    return selected;
  }

  async function markBugHandled() {
    const ticket = selectedTicket();
    if (!ticket || ticket.requestType !== "bug") return ticket;
    if (typeof shop.markBugHandled === "function") {
      try {
        const result = await shop.markBugHandled({ ticketId: ticket.id });
        if (result) {
          selected = result;
          return result;
        }
      } catch {
        // local flag below
      }
    }
    selected = {
      ...ticket,
      bugHandled: true,
      statusEvents: [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "bug handled" },
      ],
    };
    return selected;
  }

  async function refreshMacros(query = "") {
    macroQuery = query;
    if (typeof shop.searchMacros === "function") {
      try {
        const result = await shop.searchMacros({ query });
        if (Array.isArray(result?.macros)) {
          macros = result.macros;
          return;
        }
      } catch {
        // fixture fallback below
      }
    }
    const needle = String(query || "").trim().toLowerCase();
    macros = fixtureMacros.filter((macro) => {
      if (!needle) return true;
      return `${macro.id} ${macro.title} ${(macro.tags || []).join(" ")} ${macro.body}`.toLowerCase().includes(needle);
    });
  }

  function composerInput(ticket) {
    return {
      ticket: withRecipient(ticket, toEmail),
      draft: discarded ? "" : strip,
      summarize: summarizeText,
      macros,
      body,
      strip: discarded ? "" : strip,
      query: macroQuery,
      selectedMacroId,
      searchOpen: macrosOpen,
      writeGate,
    };
  }

  function listInput() {
    return {
      tickets: visibleTickets(),
      selectedTicketId: selectedId,
      views,
      counts,
      selectedViewId: viewId,
      collapsed: listCollapsed,
      unreadIds: [...unreadIds],
    };
  }

  function snapshot() {
    ensureSelection();
    const ticket = selectedTicket();
    const listModel = listTissue.update(listInput());
    const threadModel = threadTissue.update({ ticket });
    const composerModel = composerTissue.update(composerInput(ticket));
    const railHtml = railCollapsed ? railCollapsedHtml() : rail.render();
    const html = `<div class="inbox" data-organ="inbox">
      <a class="skip-link" href="#inbox-thread">Skip to thread.</a>
      <section class="pane pane-list${listCollapsed ? " is-collapsed" : ""}" data-pane="list">${listTissue.render(listModel)}</section>
      <section class="pane pane-thread" id="inbox-thread" data-pane="thread" tabindex="-1">${threadTissue.render(threadModel)}${composerTissue.render(composerModel)}</section>
      <aside class="pane pane-rail${railCollapsed ? " is-collapsed" : ""}" data-pane="rail">${railHtml}</aside>
    </div>${gateSheetHtml()}`;
    return {
      html,
      panes: { views: false, list: true, thread: true, rail: true },
      listCollapsed,
      railCollapsed,
      viewId,
      selectedId,
      unreadIds: [...unreadIds],
      selectedHasInkBar: Boolean(selectedId) && html.includes(`data-ticket="${selectedId}"`) && html.includes("is-selected"),
      sendDisabled: composerTissue.sendDisabled(composerModel),
      hideSendAndClose: composerTissue.hideSendAndClose(composerModel),
      forbidden: forbiddenControlHits(html),
      rail: rail.snapshot(),
      errors: mailbox.failures().concat(
        Object.entries(rail.snapshot().models)
          .filter(([, model]) => model.error)
          .map(([tissueId, model]) => ({ tissueId, message: model.error })),
      ),
      sent,
      strip: composerModel.strip,
      summarize: summarizeText,
      macros: composerModel.macros,
      query: composerModel.query,
      selectedMacroId: composerModel.selectedMacroId,
      searchOpen: composerModel.searchOpen,
    };
  }

  async function refreshRail() {
    const ticket = selectedTicket();
    await rail.load({
      shop: shopHost,
      customerId: ticket?.customerId,
      orderId: ticket?.orderId,
      ticketId: ticket?.id,
    });
    toEmail = rail.snapshot().models.customer?.record?.defaultEmailAddress?.emailAddress || "";
  }

  async function mount(root) {
    root.innerHTML = shell();
    const panes = {
      list: root.querySelector('[data-pane="list"]'),
      thread: root.querySelector("[data-slot=thread]"),
      composer: root.querySelector("[data-slot=composer]"),
      rail: root.querySelector('[data-pane="rail"]'),
    };
    await refreshList();
    ensureSelection();
    await refreshThread();
    await refreshRail();
    await refreshComposer();
    await refreshMacros("");
    await refreshWriteGate();

    const paint = () => {
      const ticket = selectedTicket();
      panes.list?.classList?.toggle?.("is-collapsed", listCollapsed);
      panes.rail?.classList?.toggle?.("is-collapsed", railCollapsed);
      safeMount(listTissue, panes.list, listInput());
      const threadResult = safeMount(threadTissue, panes.thread, { ticket });
      safeMount(composerTissue, panes.composer, composerInput(ticket));
      try {
        if (railCollapsed) {
          panes.rail.innerHTML = railCollapsedHtml();
        } else {
          rail.mount(panes.rail);
        }
      } catch (err) {
        panes.rail.innerHTML = `<div class="tissue-error" data-tissue-error="rail">rail unavailable</div>`;
        mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId: "rail", message: String(err?.message || err) });
      }
      if (!threadResult.ok) {
        mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId: "thread", message: threadResult.error });
      }
      const host = root.querySelector("[data-gate-host]");
      if (host) host.innerHTML = gateSheetHtml();
    };

    mailbox.subscribe(MAILBOX_TOPICS.LIST_COLLAPSED, ({ collapsed }) => {
      listCollapsed = Boolean(collapsed);
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.RAIL_COLLAPSED, ({ collapsed }) => {
      railCollapsed = Boolean(collapsed);
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.VIEW_SELECTED, ({ viewId: next }) => {
      viewId = next;
      selectedId = null;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = false;
      refreshList().then(() => {
        ensureSelection();
        return refreshThread();
      }).then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.LIST_SELECTED, ({ ticketId }) => {
      selectedId = ticketId;
      markRead(ticketId);
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = false;
      refreshThread().then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_BODY, ({ text }) => {
      body = text;
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_MACROS, ({ open }) => {
      macrosOpen = Boolean(open);
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_INSERT, (payload) => {
      if (payload?.macroId) {
        selectedMacroId = "";
        macrosOpen = false;
        macroQuery = "";
      }
      if (payload?.text) body = payload.text;
      strip = "";
      discarded = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_DISCARD, () => {
      strip = "";
      discarded = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_REGENERATE, () => {
      discarded = false;
      const ticket = selectedTicket();
      loadDraft(ticket).then((text) => {
        strip = text;
        paint();
      });
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SUMMARIZE, ({ ticketId }) => {
      const ticket = selectedTicket() || listRows.find((item) => item.id === ticketId) || null;
      loadSummary(ticket).then((text) => {
        summarizeText = text;
        paint();
      });
    });
    mailbox.subscribe(MAILBOX_TOPICS.THREAD_ESCALATE, ({ ticketId, reason }) => {
      if (ticketId && ticketId !== selectedId) selectedId = ticketId;
      escalateSelected(reason).then(() => refreshThread()).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.WRITE_GATE_OPEN, () => {
      closeAllGates();
      writeGateOpen = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.WRITE_GATE_CLOSE, () => {
      writeGateOpen = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.CUSTOMER_JOIN_GATE_OPEN, () => {
      closeAllGates();
      customerJoinGateOpen = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.CUSTOMER_JOIN_GATE_CLOSE, () => {
      customerJoinGateOpen = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.ORDER_LINK_GATE_OPEN, () => {
      closeAllGates();
      orderLinkGateOpen = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.ORDER_LINK_GATE_CLOSE, () => {
      orderLinkGateOpen = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.PRIVACY_GATE_OPEN, () => {
      closeAllGates();
      privacyGateOpen = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.PRIVACY_GATE_CLOSE, () => {
      privacyGateOpen = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.PRIVACY_HANDLED, ({ ticketId }) => {
      if (ticketId && ticketId !== selectedId) selectedId = ticketId;
      markPrivacyHandled().then(() => refreshRail()).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.MARKETING_GATE_OPEN, () => {
      closeAllGates();
      marketingGateOpen = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.MARKETING_GATE_CLOSE, () => {
      marketingGateOpen = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.MARKETING_HANDLED, ({ ticketId }) => {
      if (ticketId && ticketId !== selectedId) selectedId = ticketId;
      markUnsubscribed().then(() => refreshRail()).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.BUG_HANDLED, ({ ticketId }) => {
      if (ticketId && ticketId !== selectedId) selectedId = ticketId;
      markBugHandled().then(() => refreshRail()).then(paint);
    });
    root.onclick = (event) => {
      if (event.target.closest("[data-rail-expand]")) {
        railCollapsed = false;
        paint();
        return;
      }
      if (event.target.closest("[data-privacy-handled]")) {
        const ticket = selectedTicket();
        mailbox.publish(MAILBOX_TOPICS.PRIVACY_HANDLED, { ticketId: ticket?.id });
        return;
      }
      if (event.target.closest("[data-unsubscribe-handled]")) {
        const ticket = selectedTicket();
        mailbox.publish(MAILBOX_TOPICS.MARKETING_HANDLED, { ticketId: ticket?.id });
        return;
      }
      if (event.target.closest("[data-bug-handled]")) {
        const ticket = selectedTicket();
        mailbox.publish(MAILBOX_TOPICS.BUG_HANDLED, { ticketId: ticket?.id });
        return;
      }
      if (event.target.closest("[data-gate-dismiss]") || event.target.closest("[data-gate-sheet]") === event.target) {
        closeAllGates();
        paint();
      }
    };
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SEND, ({ text, close }) => {
      const ticket = selectedTicket();
      if (!ticket || !String(text || "").trim()) return;
      ticket.messages = [
        ...(ticket.messages || []),
        {
          id: `out-${Date.now()}`,
          from: "agent",
          fromAgent: true,
          fromName: STORE_NAME,
          name: STORE_NAME,
          at: new Date().toISOString(),
          body: text,
        },
      ];
      if (close) ticket.status = "closed";
      sent.push({ ticketId: ticket.id, text, close });
      body = "";
      strip = "";
      paint();
    });

    paint();
    return snapshot();
  }

  return {
    mailbox,
    shop,
    mount,
    snapshot,
    selectView(next) {
      viewId = next;
      selectedId = null;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = false;
      return refreshList().then(() => {
        ensureSelection();
        return refreshThread();
      }).then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery));
    },
    selectTicket(id) {
      selectedId = id;
      markRead(id);
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = false;
      return refreshThread().then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery));
    },
    collapseList(collapsed = true) {
      listCollapsed = Boolean(collapsed);
      return snapshot();
    },
    collapseRail(collapsed = true) {
      railCollapsed = Boolean(collapsed);
      return snapshot();
    },
    toggleRail(key) {
      return rail.toggle(key);
    },
    setBody(text) {
      body = text;
      composerTissue.update(composerInput(selectedTicket()));
    },
    discardStrip() {
      discarded = true;
      strip = "";
      composerTissue.update(composerInput(selectedTicket()));
    },
    insertDraft() {
      const text = discarded ? "" : strip;
      if (text) body = body ? `${body}\n\n${text}` : text;
      strip = "";
      discarded = true;
      composerTissue.update(composerInput(selectedTicket()));
    },
    async regenerateDraft() {
      discarded = false;
      strip = await loadDraft(selectedTicket());
      composerTissue.update(composerInput(selectedTicket()));
      return snapshot();
    },
    openMacros() {
      macrosOpen = true;
      composerTissue.update(composerInput(selectedTicket()));
      return snapshot();
    },
    async searchMacros(query = "") {
      macrosOpen = true;
      await refreshMacros(query);
      composerTissue.update(composerInput(selectedTicket()));
      return snapshot();
    },
    async applyMacro(macroId, mode = "replace") {
      selectedMacroId = macroId;
      macrosOpen = false;
      macroQuery = "";
      let text = "";
      if (typeof shop.applyMacro === "function") {
        try {
          const result = await shop.applyMacro({
            macroId,
            mode,
            currentBody: body,
          });
          text = result?.text || "";
        } catch {
          text = "";
        }
      }
      if (!text) {
        const macro = macros.find((item) => item.id === macroId) || fixtureMacros.find((item) => item.id === macroId);
        if (macro) {
          text = mode === "append" && body.trim() ? `${body.trimEnd()}\n\n${macro.body}` : macro.body;
        }
      }
      if (text) body = text;
      composerTissue.update(composerInput(selectedTicket()));
      return snapshot();
    },
    async escalate(reason) {
      const ticket = await escalateSelected(reason);
      if (ticket && !pinnedCatalog) await refreshThread();
      composerTissue.update(composerInput(selectedTicket()));
      threadTissue.update({ ticket: selectedTicket() });
      return snapshot();
    },
    openWriteGate() {
      closeAllGates();
      writeGateOpen = true;
      return snapshot();
    },
    closeWriteGate() {
      writeGateOpen = false;
      return snapshot();
    },
    openCustomerJoinGate() {
      closeAllGates();
      customerJoinGateOpen = true;
      return snapshot();
    },
    closeCustomerJoinGate() {
      customerJoinGateOpen = false;
      return snapshot();
    },
    openOrderLinkGate() {
      closeAllGates();
      orderLinkGateOpen = true;
      return snapshot();
    },
    closeOrderLinkGate() {
      orderLinkGateOpen = false;
      return snapshot();
    },
    openPrivacyGate() {
      closeAllGates();
      privacyGateOpen = true;
      return snapshot();
    },
    closePrivacyGate() {
      privacyGateOpen = false;
      return snapshot();
    },
    openMarketingGate() {
      closeAllGates();
      marketingGateOpen = true;
      return snapshot();
    },
    closeMarketingGate() {
      marketingGateOpen = false;
      return snapshot();
    },
    async markPrivacyHandled() {
      const ticket = await markPrivacyHandled();
      if (ticket && !pinnedCatalog) await refreshThread();
      await refreshRail();
      return snapshot();
    },
    async markUnsubscribed() {
      const ticket = await markUnsubscribed();
      if (ticket && !pinnedCatalog) await refreshThread();
      await refreshRail();
      return snapshot();
    },
    async markBugHandled() {
      const ticket = await markBugHandled();
      if (ticket && !pinnedCatalog) await refreshThread();
      await refreshRail();
      return snapshot();
    },
    async requestSummarize() {
      const ticket = selectedTicket();
      summarizeText = await loadSummary(ticket);
      composerTissue.update(composerInput(ticket));
      return snapshot();
    },
    async ready() {
      await refreshList();
      ensureSelection();
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      await refreshMacros(macroQuery);
      await refreshWriteGate();
      return snapshot();
    },
    async ingestEmail(args) {
      if (typeof shop.ingestEmail !== "function") return null;
      const result = await shop.ingestEmail(args);
      await refreshList();
      if (result?.id) {
        selectedId = result.id;
        unreadIds.add(result.id);
      }
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      return result;
    },
    async ingestChat(args) {
      if (typeof shop.ingestChat !== "function") return null;
      const result = await shop.ingestChat(args);
      await refreshList();
      if (result?.id) {
        selectedId = result.id;
        unreadIds.add(result.id);
      }
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      return result;
    },
    async pullMailbox(args = {}) {
      if (typeof shop.pullMailbox !== "function") return null;
      const result = await shop.pullMailbox(args);
      await refreshList();
      const first = Array.isArray(result?.ingested) ? result.ingested[0] : null;
      if (first?.id) {
        selectedId = first.id;
        unreadIds.add(first.id);
      }
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      return result;
    },
  };
}
