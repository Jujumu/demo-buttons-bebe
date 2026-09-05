import { MAILBOX_TOPICS } from "../contracts.js";
import { clerkStatusEvents, listCustomerName, messageSpeaker, talkMessages } from "../shop/clerk-ticket.js";
import { bugMetaPeek, esc, formatWeekday, formatWhen, initials, requestTypeTitle, screenStatus } from "../util.js";

/**
 * Thread tissue.
 * In: `{ ticket }` from helpdesk.get_ticket
 * Out: summarize on `composer/summarize`; escalate on `thread/escalate`.
 * Inbound From is the customer persona, not the AgentMail/shop mailbox login.
 * Status-change events are muted as `Closed · Tuesday`. Escalate writes
 * `Escalated · Tuesday` the same way. No Escalated badge. No Send.
 */
export function createThreadTissue({ mailbox }) {
  let model = { ticket: null };

  function project(input) {
    return { ticket: input.ticket || null };
  }

  function renderAttachments(message) {
    const rows = Array.isArray(message.attachments) ? message.attachments : [];
    if (!rows.length) return "";
    const figures = rows
      .filter((item) => item && item.url)
      .map((item) => {
        const alt = item.alt || "Attachment";
        return `<figure class="bubble-attach">
          <img src="${esc(item.url)}" alt="${esc(alt)}" loading="lazy" />
          <figcaption>${esc(alt)}</figcaption>
        </figure>`;
      })
      .join("");
    return figures ? `<div class="bubble-attachments">${figures}</div>` : "";
  }

  function renderMessage(ticket, message) {
    const speaker = messageSpeaker(ticket, message);
    const email = speaker.email
      ? `<span class="from-email">${esc(speaker.email)}</span>`
      : "";
    return `<article class="bubble ${speaker.role}">
      <div class="bubble-meta">
        <span class="avatar">${esc(initials(speaker.name))}</span>
        <strong>From ${esc(speaker.name)}</strong>
        ${email}
        <time>${esc(formatWhen(message.at))}</time>
      </div>
      <p>${esc(message.body)}</p>
      ${renderAttachments(message)}
    </article>`;
  }

  function isEscalateEvent(event) {
    return /^escalated\b/i.test(event?.note || "") || String(event?.status || "").toLowerCase() === "escalated";
  }

  function renderStatus(event) {
    const escalated = isEscalateEvent(event);
    const word = escalated ? "Escalated" : screenStatus(event.status);
    const mark = escalated ? " data-escalated" : "";
    return `<p class="status-line"${mark}>${esc(word)} · ${esc(formatWeekday(event.at))}</p>`;
  }

  function timeline(ticket) {
    const events = clerkStatusEvents(ticket);
    const items = [
      ...talkMessages(ticket).map((message) => ({ at: message.at, html: renderMessage(ticket, message) })),
      ...events.map((event) => ({ at: event.at, html: renderStatus(event) })),
    ];
    if (ticket.escalated && !events.some(isEscalateEvent)) {
      const at = ticket.updatedAt || ticket.statusEvents?.at?.(-1)?.at || "";
      items.push({ at, html: renderStatus({ at, status: ticket.status, note: "escalated" }) });
    }
    items.sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")));
    return items.map((item) => item.html).join("");
  }

  function render(next = model) {
    const ticket = next.ticket;
    if (!ticket) {
      return `<div class="pane-inner"><p class="empty-pane">Select a ticket.</p></div>`;
    }
    const count = talkMessages(ticket).length;
    const summarizeLabel = count === 1 ? "Summarize 1 message" : `Summarize ${count} messages`;
    const escalateControl = ticket.escalated
      ? ""
      : `<button type="button" class="btn-quiet" data-escalate="${esc(ticket.id)}">Escalate</button>`;
    const typeTitle = requestTypeTitle(ticket.requestType);
    const typeLine = typeTitle
      ? `<p class="thread-request mute" data-request-type="${esc(ticket.requestType)}">${esc(typeTitle)}</p>`
      : "";
    const bugMeta = bugMetaPeek(ticket.severity, ticket.device);
    const bugLine = bugMeta
      ? `<p class="thread-request mute" data-severity="${esc(ticket.severity || "")}"${ticket.device ? ` data-device="${esc(ticket.device)}"` : ""}>${esc(bugMeta)}</p>`
      : "";
    return `<div class="pane-inner thread-inner">
      <header class="thread-head">
        <div>
          <h2>${esc(listCustomerName(ticket))}</h2>
          <p class="thread-subject">${esc(ticket.subject)}</p>
          ${typeLine}
          ${bugLine}
        </div>
        <div class="thread-head-actions">
          <span class="status-badge">${esc(screenStatus(ticket.status))}</span>
          ${escalateControl}
        </div>
      </header>
      <div class="thread-scroll">${timeline(ticket)}</div>
      <div class="summarize-row">
        <button type="button" class="btn-quiet" data-summarize="${esc(ticket.id)}">${esc(summarizeLabel)}</button>
      </div>
    </div>`;
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.onclick = (event) => {
      const escalate = event.target.closest("[data-escalate]");
      if (escalate) {
        mailbox.publish(MAILBOX_TOPICS.THREAD_ESCALATE, { ticketId: escalate.dataset.escalate });
        return;
      }
      const button = event.target.closest("[data-summarize]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.COMPOSER_SUMMARIZE, { ticketId: button.dataset.summarize });
    };
  }

  return {
    id: "thread",
    project,
    render,
    update(input) {
      model = project(input);
      return model;
    },
    mount,
  };
}
