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
  const catalog = opts.tickets || fixtureTickets;
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

  function visibleTickets() {
    return catalog.filter((ticket) => ticketInView(ticket, viewId));
  }

  function selectedTicket() {
    return catalog.find((ticket) => ticket.id === selectedId) || null;
  }

  function ensureSelection() {
    const visible = visibleTickets();
    if (!visible.some((ticket) => ticket.id === selectedId)) {
      selectedId = visible[0]?.id || null;
    }
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
    };
  }

  function snapshot() {
    ensureSelection();
    const ticket = selectedTicket();
    const counts = viewCounts(catalog);
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
    ensureSelection();
    await refreshRail();
    await refreshComposer();
    await refreshMacros("");

    const paint = () => {
      const ticket = selectedTicket();
      safeMount(viewTissue, panes.views, { views, counts: viewCounts(catalog), selectedViewId: viewId });
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
      ensureSelection();
      refreshRail().then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.LIST_SELECTED, ({ ticketId }) => {
      selectedId = ticketId;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      refreshRail().then(refreshComposer).then(() => refreshMacros(macroQuery)).then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_BODY, ({ text }) => {
      body = text;
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_INSERT, (payload) => {
      if (payload?.macroId) selectedMacroId = payload.macroId;
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
      const ticket = selectedTicket() || catalog.find((item) => item.id === ticketId) || null;
      loadSummary(ticket).then((text) => {
        summarizeText = text;
        paint();
      });
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
      ensureSelection();
      return refreshRail().then(refreshComposer).then(() => refreshMacros(macroQuery));
    },
    selectTicket(id) {
      selectedId = id;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      selectedMacroId = "";
      return refreshRail().then(refreshComposer).then(() => refreshMacros(macroQuery));
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
      await refreshMacros(query);
      composerTissue.update(composerInput(selectedTicket()));
      return snapshot();
    },
    async applyMacro(macroId, mode = "replace") {
      selectedMacroId = macroId;
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
    async requestSummarize() {
      const ticket = selectedTicket();
      summarizeText = await loadSummary(ticket);
      composerTissue.update(composerInput(ticket));
      return snapshot();
    },
    async ready() {
      ensureSelection();
      await refreshRail();
      await refreshComposer();
      await refreshMacros(macroQuery);
      return snapshot();
    },
  };
}
