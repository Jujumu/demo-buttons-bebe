import { MAILBOX_TOPICS } from "./contracts.js";
import { SHOP, STORE_NAME, macros as fixtureMacros, ticketInView, tickets as fixtureTickets, viewCounts, views } from "./fixtures/demo-inbox.js";
import { createMailbox } from "./mailbox.js";
import { createHelpdeskShop } from "./shop/helpdesk-shop.js";
import { createComposerTissue } from "./tissues/composer.js";
import { createListTissue } from "./tissues/list.js";
import { createRailOrgan } from "./tissues/rail.js";
import { createThreadTissue } from "./tissues/thread.js";
import { createViewTissue } from "./tissues/view.js";
import { forbiddenControlHits } from "./util.js";

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
 * Inbox organ: view + list + thread + rail + composer.
 * One tissue error stays in its pane.
 */
export function createInboxOrgan(opts = {}) {
  const mailbox = opts.mailbox || createMailbox();
  const shop = opts.shop || createHelpdeskShop({ fail: opts.fail });
  const shopHost = opts.shopHost || shop.shop || SHOP;
  const pinnedCatalog = opts.tickets || null;
  const viewTissue = createViewTissue({ mailbox });
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
  let macrosOpen = true;
  let writeGate = {
    mutationsEnabled: false,
    refused: ["send", "refund", "cancel"],
    message: "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.",
  };
  let listRows = pinnedCatalog ? pinnedCatalog.filter((ticket) => ticketInView(ticket, viewId)) : [];
  let selected = pinnedCatalog?.find((ticket) => ticket.id === selectedId) || null;
  let counts = pinnedCatalog ? viewCounts(pinnedCatalog) : viewCounts(fixtureTickets);

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

  function shell() {
    return `<div class="inbox" data-organ="inbox">
      <a class="skip-link" href="#inbox-thread">Skip to thread.</a>
      <aside class="pane pane-views" data-pane="views"></aside>
      <section class="pane pane-list" data-pane="list"></section>
      <section class="pane pane-thread" id="inbox-thread" data-pane="thread" tabindex="-1">
        <div data-slot="thread"></div>
        <div data-slot="composer"></div>
      </section>
      <aside class="pane pane-rail" data-pane="rail"></aside>
    </div>`;
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

  function snapshot() {
    ensureSelection();
    const ticket = selectedTicket();
    const viewModel = viewTissue.update({ views, counts, selectedViewId: viewId });
    const listModel = listTissue.update({
      tickets: visibleTickets(),
      selectedTicketId: selectedId,
      viewLabel: views.find((view) => view.id === viewId)?.label || "Inbox",
    });
    const threadModel = threadTissue.update({ ticket });
    const composerModel = composerTissue.update(composerInput(ticket));
    const html = `<div class="inbox" data-organ="inbox">
      <a class="skip-link" href="#inbox-thread">Skip to thread.</a>
      <aside class="pane pane-views" data-pane="views">${viewTissue.render(viewModel)}</aside>
      <section class="pane pane-list" data-pane="list">${listTissue.render(listModel)}</section>
      <section class="pane pane-thread" id="inbox-thread" data-pane="thread" tabindex="-1">${threadTissue.render(threadModel)}${composerTissue.render(composerModel)}</section>
      <aside class="pane pane-rail" data-pane="rail">${rail.render()}</aside>
    </div>`;
    return {
      html,
      panes: { views: true, list: true, thread: true, rail: true },
      viewId,
      selectedId,
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
      views: root.querySelector('[data-pane="views"]'),
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
      safeMount(viewTissue, panes.views, { views, counts, selectedViewId: viewId });
      safeMount(listTissue, panes.list, {
        tickets: visibleTickets(),
        selectedTicketId: selectedId,
        viewLabel: views.find((view) => view.id === viewId)?.label || "Inbox",
      });
      const threadResult = safeMount(threadTissue, panes.thread, { ticket });
      safeMount(composerTissue, panes.composer, composerInput(ticket));
      try {
        rail.mount(panes.rail);
      } catch (err) {
        panes.rail.innerHTML = `<div class="tissue-error" data-tissue-error="rail">rail unavailable</div>`;
        mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId: "rail", message: String(err?.message || err) });
      }
      if (!threadResult.ok) {
        mailbox.publish(MAILBOX_TOPICS.TISSUE_ERROR, { tissueId: "thread", message: threadResult.error });
      }
    };

    mailbox.subscribe(MAILBOX_TOPICS.VIEW_SELECTED, ({ viewId: next }) => {
      viewId = next;
      selectedId = null;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = true;
      refreshList().then(() => {
        ensureSelection();
        return refreshThread();
      }).then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.LIST_SELECTED, ({ ticketId }) => {
      selectedId = ticketId;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = true;
      refreshThread().then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_BODY, ({ text }) => {
      body = text;
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
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SEND, ({ text, close }) => {
      const ticket = selectedTicket();
      if (!ticket || !String(text || "").trim()) return;
      ticket.messages = [
        ...(ticket.messages || []),
        {
          id: `out-${Date.now()}`,
          fromAgent: true,
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
      macrosOpen = true;
      return refreshList().then(() => {
        ensureSelection();
        return refreshThread();
      }).then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery));
    },
    selectTicket(id) {
      selectedId = id;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      macrosOpen = true;
      return refreshThread().then(refreshRail).then(refreshComposer).then(() => refreshMacros(macroQuery));
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
      if (result?.id) selectedId = result.id;
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      return result;
    },
    async ingestChat(args) {
      if (typeof shop.ingestChat !== "function") return null;
      const result = await shop.ingestChat(args);
      await refreshList();
      if (result?.id) selectedId = result.id;
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
      if (first?.id) selectedId = first.id;
      await refreshThread();
      await refreshRail();
      await refreshComposer();
      return result;
    },
  };
}
