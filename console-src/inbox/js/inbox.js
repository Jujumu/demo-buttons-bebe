import { MAILBOX_TOPICS } from "./contracts.js";
import { SHOP, macros, ticketInView, tickets as fixtureTickets, viewCounts, views } from "./fixtures/cute-things.js";
import { createMailbox } from "./mailbox.js";
import { createFixtureShop } from "./shop/fixture-shop.js";
import { createComposerTissue } from "./tissues/composer.js";
import { createListTissue } from "./tissues/list.js";
import { createRailOrgan } from "./tissues/rail.js";
import { createThreadTissue } from "./tissues/thread.js";
import { createViewTissue } from "./tissues/view.js";
import { forbiddenControlHits } from "./util.js";

function caduceusStub(ticket) {
  if (!ticket) return { draft: "", summarize: "" };
  return {
    draft: ticket.stubDraft || "",
    summarize: ticket.stubSummary || "",
  };
}

function withRecipient(ticket, shop) {
  if (!ticket) return null;
  let email = "";
  try {
    const customer = ticket.customerId
      ? shop.getCustomer({ shop: SHOP, customerId: ticket.customerId })
      : null;
    email = customer?.defaultEmailAddress?.emailAddress || "";
  } catch {
    email = "";
  }
  return {
    ...ticket,
    toEmail: email,
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
  const shop = opts.shop || createFixtureShop({ fail: opts.fail });
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
      <aside class="pane pane-views" data-pane="views"></aside>
      <section class="pane pane-list" data-pane="list"></section>
      <section class="pane pane-thread" data-pane="thread">
        <div data-slot="thread"></div>
        <div data-slot="composer"></div>
      </section>
      <aside class="pane pane-rail" data-pane="rail"></aside>
    </div>`;
  }

  function composerInput(ticket) {
    const ai = caduceusStub(ticket);
    const activeStrip = discarded ? "" : (strip || summarizeText || ai.draft || "");
    return {
      ticket: withRecipient(ticket, shop),
      draft: ai.draft,
      summarize: summarizeText || ai.summarize,
      macros,
      body,
      strip: activeStrip,
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
      <aside class="pane pane-views" data-pane="views">${viewTissue.render(viewModel)}</aside>
      <section class="pane pane-list" data-pane="list">${listTissue.render(listModel)}</section>
      <section class="pane pane-thread" data-pane="thread">${threadTissue.render(threadModel)}${composerTissue.render(composerModel)}</section>
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
      summarize: summarizeText || caduceusStub(ticket).summarize,
    };
  }

  async function refreshRail() {
    const ticket = selectedTicket();
    await rail.load({
      shop: SHOP,
      customerId: ticket?.customerId,
      orderId: ticket?.orderId,
    });
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
      ensureSelection();
      refreshRail().then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.LIST_SELECTED, ({ ticketId }) => {
      selectedId = ticketId;
      body = "";
      strip = "";
      summarizeText = "";
      discarded = false;
      refreshRail().then(paint);
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_BODY, ({ text }) => {
      body = text;
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_INSERT, () => {
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_DISCARD, () => {
      strip = "";
      discarded = true;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SUMMARIZE, () => {
      const ticket = selectedTicket();
      summarizeText = caduceusStub(ticket).summarize;
      strip = summarizeText;
      discarded = false;
      paint();
    });
    mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SEND, ({ text, close }) => {
      const ticket = selectedTicket();
      if (!ticket || !String(text || "").trim()) return;
      ticket.messages = [
        ...(ticket.messages || []),
        {
          id: `out-${Date.now()}`,
          fromAgent: true,
          name: "Cute Things",
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
      ensureSelection();
      return refreshRail();
    },
    selectTicket(id) {
      selectedId = id;
      return refreshRail();
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
    async ready() {
      ensureSelection();
      await refreshRail();
      return snapshot();
    },
  };
}
