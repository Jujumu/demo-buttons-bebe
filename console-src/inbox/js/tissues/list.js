import { MAILBOX_TOPICS } from "../contracts.js";
import { listCustomerName } from "../shop/clerk-ticket.js";
import { esc, formatWhen, requestTypeLabel, screenStatus, severityLabel } from "../util.js";

/**
 * List tissue. Client of helpdesk.list_tickets + view switcher.
 * In: `{ tickets, selectedTicketId, views, counts, selectedViewId, collapsed, unreadIds, checkedIds, query }`
 * Out: `{ ticketId }` on `list/selected`, `{ viewId }` on `view/selected`,
 *      `{ ticketId, checked }` on `list/checked`, `{ action }` on `list/bulk`,
 *      `{ query }` on `list/search`, `{ collapsed }` on `list/collapsed`
 * Selected row: pale accent wash + narrow accent edge. Uses first-party
 * customerName, snippet, and helpdesk status (open / closed / snoozed) —
 * never Return.status.
 * Chrome: Inbox title + filter (views) / sort / search / collapse — no separate views pane.
 * Search narrows the current view. It is not a view.
 * Filter menu includes Open (`status === "open"`), Escalated (`escalated`),
 * Trash (`archived`), and Spam (`spam`).
 * Open queues omit the Open chip. Escalated queues omit an Escalated chip.
 */

export function ticketMatchesQuery(ticket, query) {
  const needle = String(query ?? "").trim().toLowerCase();
  if (!needle) return true;
  const name = listCustomerName(ticket);
  const hay = [name, ticket.subject, ticket.snippet, ticket.id]
    .map((part) => String(part ?? "").toLowerCase());
  return hay.some((part) => part.includes(needle));
}

const ICON_FILTER = `<svg class="list-tool-icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M2.5 4h11M2.5 8h11M2.5 12h11"/>
  <circle fill="currentColor" cx="5.5" cy="4" r="1.35"/>
  <circle fill="currentColor" cx="10.5" cy="8" r="1.35"/>
  <circle fill="currentColor" cx="7" cy="12" r="1.35"/>
</svg>`;

const ICON_SORT = `<svg class="list-tool-icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M5.25 3.25v9.5M5.25 3.25 3.5 5M5.25 3.25 7 5M10.75 12.75v-9.5M10.75 12.75 9 11M10.75 12.75 12.5 11"/>
</svg>`;

const ICON_CLOSE = `<svg class="list-tool-icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" d="M4.25 4.25l7.5 7.5M11.75 4.25l-7.5 7.5"/>
</svg>`;

const ICON_CHEVRON = `<svg class="list-scope-chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="M2.75 4.5 6 7.75 9.25 4.5"/>
</svg>`;

const ICON_EXPAND = `<svg class="list-expand-icon" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
  <path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M5 2.5 9.5 7 5 11.5"/>
</svg>`;

const ICON_CLOCK = `<svg class="list-bulk-icon" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
  <circle fill="none" stroke="currentColor" stroke-width="1.4" cx="7" cy="7" r="5"/>
  <path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M7 4.25V7l1.85 1.35"/>
</svg>`;

export function createListTissue({ mailbox }) {
  let model = {
    tickets: [],
    selectedTicketId: null,
    views: [],
    counts: {},
    selectedViewId: "mine",
    collapsed: false,
    unreadIds: [],
    checkedIds: [],
    query: "",
  };
  let ui = { sort: "default", filterOpen: false, bulkOpen: false, assignOpen: false };
  let host = null;

  function project(input) {
    return {
      tickets: input.tickets || [],
      selectedTicketId: input.selectedTicketId || null,
      views: input.views || [],
      counts: input.counts || {},
      selectedViewId: input.selectedViewId || "mine",
      collapsed: Boolean(input.collapsed),
      unreadIds: Array.isArray(input.unreadIds) ? input.unreadIds : [],
      checkedIds: Array.isArray(input.checkedIds) ? input.checkedIds : [],
      query: String(input.query ?? ""),
    };
  }

  function listedTickets(next = model) {
    const rows = (next.tickets || []).filter((ticket) => ticketMatchesQuery(ticket, next.query));
    return sortedTickets(rows);
  }

  function sortedTickets(tickets) {
    let rows = Array.isArray(tickets) ? [...tickets] : [];
    if (ui.sort === "newest" || ui.sort === "oldest") {
      rows.sort((a, b) => {
        const left = Date.parse(a.updatedAt || 0) || 0;
        const right = Date.parse(b.updatedAt || 0) || 0;
        return ui.sort === "oldest" ? left - right : right - left;
      });
    }
    return rows;
  }

  function renderViewMenu(next) {
    const items = (next.views || []).map((view) => {
      const on = view.id === next.selectedViewId;
      const count = next.counts?.[view.id] ?? 0;
      return `<button type="button" class="list-menu-item${on ? " is-selected" : ""}" data-view="${esc(view.id)}" role="option" aria-selected="${on ? "true" : "false"}">
        <span class="list-menu-label">${esc(view.label)}</span>
        <span class="list-menu-count">${esc(count)}</span>
      </button>`;
    }).join("");
    return `<div class="list-scope-menu list-view-menu${ui.filterOpen ? " is-open" : ""}" role="listbox" ${ui.filterOpen ? "" : "hidden"}>
      ${items}
    </div>`;
  }

  function renderToolbar(next = model) {
    return `<header class="pane-head list-toolbar">
      <a class="console-link" href="../index.html">Console</a>
      <div class="list-toolbar-row">
        <div class="list-scope">
          <button type="button" class="list-scope-btn" data-list-inbox aria-label="Inbox" title="Open the views menu">
            <span class="list-scope-label">Inbox</span>
            ${ICON_CHEVRON}
          </button>
        </div>
        <div class="list-tools" role="group" aria-label="List tools">
          ${renderSearch(next)}
          <div class="list-filter-wrap">
            <button type="button" class="list-tool-btn" data-list-filter title="Views" aria-label="Views" aria-haspopup="listbox" aria-expanded="${ui.filterOpen ? "true" : "false"}" aria-pressed="${ui.filterOpen ? "true" : "false"}">${ICON_FILTER}</button>
            ${renderViewMenu(next)}
          </div>
          <button type="button" class="list-tool-btn" data-list-sort title="Sort ${ui.sort === "oldest" ? "newest first" : ui.sort === "newest" ? "oldest first" : "newest first"}" aria-label="Sort list">${ICON_SORT}</button>
          <button type="button" class="list-tool-btn" data-list-collapse title="Collapse list" aria-label="Collapse ticket list">${ICON_CLOSE}</button>
        </div>
      </div>
    </header>`;
  }

  function renderSearch(next = model) {
    const query = String(next.query ?? "");
    const clear = query.trim()
      ? `<button type="button" class="list-search-clear" data-list-search-clear aria-label="Clear search">${ICON_CLOSE}</button>`
      : "";
    return `<label class="list-search-wrap">
      <input type="search" class="list-search" data-list-search placeholder="Search tickets" aria-label="Search tickets" value="${esc(query)}">
      ${clear}
    </label>`;
  }

  function renderSelectionBar(next, tickets) {
    const checked = new Set(next.checkedIds || []);
    const total = tickets.length;
    const count = tickets.filter((ticket) => checked.has(ticket.id)).length;
    if (!count) return "";
    const allOn = total > 0 && count === total;
    const label = allOn ? "All selected" : `${count} selected`;
    const assignMenu = ui.assignOpen
      ? `<div class="list-assign-menu" role="menu">
          <button type="button" class="list-menu-item" data-bulk-action="assign" data-assignee="me">Agent</button>
          <button type="button" class="list-menu-item" data-bulk-action="assign" data-assignee="">Unassigned</button>
        </div>`
      : "";
    return `<div class="list-select-bar" data-select-bar>
      <label class="ticket-check list-select-all">
        <input type="checkbox" data-select-all ${allOn ? "checked" : ""} aria-label="Select all visible tickets">
      </label>
      <span class="list-select-label">${esc(label)}</span>
      <div class="list-bulk">
        <button type="button" class="list-bulk-btn" data-bulk-menu aria-haspopup="menu" aria-expanded="${ui.bulkOpen ? "true" : "false"}">Actions</button>
        <div class="list-bulk-menu${ui.bulkOpen ? " is-open" : ""}" role="menu" ${ui.bulkOpen ? "" : "hidden"}>
          <button type="button" class="list-menu-item" data-bulk-action="mark_read">Mark as read</button>
          <button type="button" class="list-menu-item" data-bulk-action="mark_unread">Mark as unread</button>
          <button type="button" class="list-menu-item" data-bulk-action="assign-open" aria-expanded="${ui.assignOpen ? "true" : "false"}">Assign</button>
          ${assignMenu}
          <button type="button" class="list-menu-item" data-bulk-action="snooze">${ICON_CLOCK} Snooze</button>
          <button type="button" class="list-menu-item" data-bulk-action="trash">Delete</button>
        </div>
      </div>
      <button type="button" class="list-tool-btn" data-select-clear title="Clear selection" aria-label="Clear selection">${ICON_CLOSE}</button>
    </div>`;
  }

  function renderRow(ticket, selectedId, unreadIds, checkedIds) {
    const on = ticket.id === selectedId;
    const unread = unreadIds.includes(ticket.id);
    const checked = checkedIds.includes(ticket.id);
    const status = ticket.status || "";
    const statusWord = status === "open" ? "" : screenStatus(status);
    const typeWord = requestTypeLabel(ticket.requestType);
    const severityWord = severityLabel(ticket.severity);
    const statusHtml = statusWord
      ? `<span class="ticket-status">${esc(statusWord)}</span>`
      : "";
    const typeHtml = typeWord
      ? `<span class="ticket-badge ticket-request" data-request-type="${esc(ticket.requestType)}">${esc(typeWord)}</span>`
      : "";
    const severityHtml = severityWord
      ? `<span class="ticket-badge ticket-severity" data-severity="${esc(ticket.severity)}">${esc(severityWord)}</span>`
      : "";
    const typeAttr = typeWord ? ` data-request-type="${esc(ticket.requestType)}"` : "";
    const severityAttr = severityWord ? ` data-severity="${esc(ticket.severity)}"` : "";
    const deviceAttr = ticket.device ? ` data-device="${esc(ticket.device)}"` : "";
    const unreadClass = unread ? " is-unread" : "";
    const unreadMark = unread
      ? `<span class="ticket-unread-mark" aria-hidden="true"></span>`
      : "";
    const name = listCustomerName(ticket);
    return `<div class="ticket-item${checked ? " is-checked" : ""}">
      <label class="ticket-check">
        <input type="checkbox" data-ticket-select="${esc(ticket.id)}" ${checked ? "checked" : ""} aria-label="Select ${esc(name)}">
      </label>
      <button type="button" class="ticket-row${on ? " is-selected" : ""}${unreadClass}" data-ticket="${esc(ticket.id)}" data-status="${esc(status)}"${typeAttr}${severityAttr}${deviceAttr} aria-current="${on ? "true" : "false"}">
        <span class="ticket-bar" aria-hidden="true"></span>
        <span class="ticket-top">
          <span class="ticket-who">${unreadMark}<span class="ticket-name">${esc(name)}</span></span>
          <span class="ticket-meta">
            ${typeHtml}
            ${severityHtml}
            ${statusHtml}
            <time class="ticket-time" datetime="${esc(ticket.updatedAt || "")}" title="${esc(formatWhen(ticket.updatedAt))}">${esc(formatWhen(ticket.updatedAt, { relative: true }))}</time>
          </span>
        </span>
        <span class="ticket-subject">${esc(ticket.subject)}</span>
        <span class="ticket-snippet">${esc(ticket.snippet || "")}</span>
      </button>
    </div>`;
  }

  function render(next = model) {
    if (next.collapsed) {
      return `<div class="pane-inner">
        <button type="button" class="list-expand-btn" data-list-expand aria-label="Expand ticket list" title="Show ticket list">
          ${ICON_EXPAND}
          <span class="list-expand-label">List</span>
        </button>
      </div>`;
    }
    const tickets = listedTickets(next);
    const unreadIds = next.unreadIds || [];
    const checkedIds = next.checkedIds || [];
    const empty = String(next.query ?? "").trim()
      ? `<p class="empty-pane">No matches.</p>`
      : `<p class="empty-pane">No tickets in this view.</p>`;
    const rows = tickets.length
      ? tickets.map((ticket) => renderRow(ticket, next.selectedTicketId, unreadIds, checkedIds)).join("")
      : empty;
    return `<div class="pane-inner">
      ${renderToolbar(next)}
      ${renderSelectionBar(next, tickets)}
      <div class="ticket-list" role="list">${rows}</div>
    </div>`;
  }

  function paint() {
    if (!host) return;
    const active = typeof document !== "undefined" ? document.activeElement : null;
    const keep = Boolean(active?.closest?.("[data-list-search]") && host.contains?.(active));
    const start = keep ? active.selectionStart : null;
    const end = keep ? active.selectionEnd : null;
    host.innerHTML = render(model);
    if (!keep) return;
    const field = host.querySelector?.("[data-list-search]");
    field?.focus?.();
    if (start != null) field?.setSelectionRange?.(start, end);
  }

  function applyQuery(query) {
    model = { ...model, query: String(query ?? "") };
    ui = { ...ui, filterOpen: false, bulkOpen: false, assignOpen: false };
    mailbox.publish(MAILBOX_TOPICS.LIST_SEARCH, { query: model.query });
    paint();
  }

  function mount(el) {
    host = el;
    paint();
    el.onkeydown = (event) => {
      if (event.key !== "Escape") return;
      const field = event.target?.closest?.("[data-list-search]");
      if (!field) return;
      event.preventDefault?.();
      applyQuery("");
    };
    el.oninput = (event) => {
      const field = event.target?.closest?.("[data-list-search]");
      if (!field) return;
      applyQuery(field.value ?? event.target?.value ?? "");
    };
    el.onclick = (event) => {
      if (event.target.closest("[data-list-search-clear]")) {
        event.preventDefault();
        applyQuery("");
        return;
      }
      const selectOne = event.target.closest("[data-ticket-select]");
      if (selectOne) {
        event.preventDefault();
        event.stopPropagation();
        const ticketId = selectOne.dataset.ticketSelect;
        const on = !(model.checkedIds || []).includes(ticketId);
        mailbox.publish(MAILBOX_TOPICS.LIST_CHECKED, { ticketId, checked: on });
        return;
      }
      if (event.target.closest("[data-select-all]")) {
        event.preventDefault();
        const visible = listedTickets(model).map((ticket) => ticket.id);
        const allOn = visible.length > 0 && visible.every((id) => (model.checkedIds || []).includes(id));
        mailbox.publish(MAILBOX_TOPICS.LIST_CHECKED_ALL, { checked: !allOn });
        return;
      }
      if (event.target.closest("[data-select-clear]")) {
        mailbox.publish(MAILBOX_TOPICS.LIST_CLEAR_CHECKED, {});
        ui = { ...ui, bulkOpen: false, assignOpen: false };
        paint();
        return;
      }
      if (event.target.closest("[data-bulk-menu]")) {
        ui = { ...ui, bulkOpen: !ui.bulkOpen, assignOpen: false, filterOpen: false };
        paint();
        return;
      }
      const bulk = event.target.closest("[data-bulk-action]");
      if (bulk) {
        const action = bulk.dataset.bulkAction;
        if (action === "assign-open") {
          ui = { ...ui, assignOpen: !ui.assignOpen, bulkOpen: true };
          paint();
          return;
        }
        ui = { ...ui, bulkOpen: false, assignOpen: false };
        paint();
        mailbox.publish(MAILBOX_TOPICS.LIST_BULK, {
          action,
          assignee: bulk.dataset.assignee,
        });
        return;
      }
      const viewPick = event.target.closest("[data-view]");
      if (viewPick) {
        ui = { ...ui, filterOpen: false };
        paint();
        mailbox.publish(MAILBOX_TOPICS.VIEW_SELECTED, { viewId: viewPick.dataset.view });
        return;
      }
      if (event.target.closest("[data-list-filter]")) {
        ui = { ...ui, filterOpen: !ui.filterOpen };
        paint();
        return;
      }
      if (event.target.closest("[data-list-inbox]")) {
        // Title affordance — views live under the filter control.
        ui = { ...ui, filterOpen: !ui.filterOpen };
        paint();
        return;
      }
      if (event.target.closest("[data-list-sort]")) {
        const nextSort =
          ui.sort === "default" ? "newest" : ui.sort === "newest" ? "oldest" : "default";
        ui = { ...ui, sort: nextSort, filterOpen: false };
        paint();
        return;
      }
      if (event.target.closest("[data-list-collapse]")) {
        mailbox.publish(MAILBOX_TOPICS.LIST_COLLAPSED, { collapsed: true });
        return;
      }
      if (event.target.closest("[data-list-expand]")) {
        mailbox.publish(MAILBOX_TOPICS.LIST_COLLAPSED, { collapsed: false });
        return;
      }
      const button = event.target.closest("[data-ticket]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.LIST_SELECTED, { ticketId: button.dataset.ticket });
    };
  }

  return {
    id: "list",
    project,
    render,
    update(input) {
      model = project(input);
      return model;
    },
    openBulk(open = true) {
      ui = { ...ui, bulkOpen: Boolean(open), assignOpen: false, filterOpen: false };
      paint();
    },
    mount,
  };
}
