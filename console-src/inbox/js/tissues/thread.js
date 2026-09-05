import { MAILBOX_TOPICS } from "../contracts.js";
import { clerkStatusEvents, listCustomerName, messageSpeaker, talkMessages } from "../shop/clerk-ticket.js";
import { esc, formatWeekday, formatWhen, initials, requestTypeChrome, screenStatus } from "../util.js";

/**
 * Thread tissue.
 * In: `{ ticket }` from helpdesk.get_ticket
 * Out: summarize on `composer/summarize`; escalate on `thread/escalate`.
 * Inbound From is the customer persona, not the AgentMail/shop mailbox login.
 * Status-change events are muted as `Closed · Tuesday`. Escalate writes
 * `Escalated · Tuesday` the same way. No Escalated badge. No Send.
 * Attachment images are small thumbs; click opens a simple lightbox.
 */
export function createThreadTissue({ mailbox }) {
  let model = { ticket: null };
  let lightbox = null;
  let host = null;

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
          <button type="button" class="bubble-thumb" data-attach-open data-attach-url="${esc(item.url)}" data-attach-alt="${esc(alt)}" aria-label="Expand ${esc(alt)}">
            <img src="${esc(item.url)}" alt="${esc(alt)}" loading="lazy" width="80" height="80" />
          </button>
          <figcaption>${esc(alt)}</figcaption>
        </figure>`;
      })
      .join("");
    return figures ? `<div class="bubble-attachments">${figures}</div>` : "";
  }

  function renderLightbox() {
    if (!lightbox?.url) return "";
    return `<div class="attach-lightbox-backdrop" data-attach-lightbox role="dialog" aria-modal="true" aria-label="Attachment">
      <figure class="attach-lightbox">
        <img src="${esc(lightbox.url)}" alt="${esc(lightbox.alt || "Attachment")}" />
        <figcaption>${esc(lightbox.alt || "Attachment")}</figcaption>
      </figure>
    </div>`;
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
      return `<div class="pane-inner"><p class="empty-pane">Select a ticket.</p></div>${renderLightbox()}`;
    }
    const count = talkMessages(ticket).length;
    const summarizeLabel = count === 1 ? "Summarize 1 message" : `Summarize ${count} messages`;
    const escalateControl = ticket.escalated
      ? ""
      : `<button type="button" class="btn-quiet" data-escalate="${esc(ticket.id)}">Escalate</button>`;
    const chrome = requestTypeChrome(ticket);
    const subtype = chrome?.subtype
      ? `<span class="thread-request-subtype mute">${esc(chrome.subtype)}</span>`
      : "";
    const mark = !chrome
      ? ""
      : chrome.handled
        ? `<p class="thread-request-handled mute">${esc(chrome.doneLabel)}</p>`
        : `<button type="button" class="btn-hairline" ${chrome.gateAttr}>${esc(chrome.markLabel)}</button>`;
    const typeLine = chrome
      ? `<div class="thread-request-row">
          <p class="thread-request mute" data-request-type="${esc(chrome.type)}"${chrome.severityAttr || ""}>${esc(chrome.title)}</p>
          ${subtype}
          ${mark}
        </div>`
      : "";
    return `<div class="pane-inner thread-inner">
      <header class="thread-head">
        <div>
          <h2>${esc(listCustomerName(ticket))}</h2>
          <p class="thread-subject">${esc(ticket.subject)}</p>
          ${typeLine}
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
    </div>${renderLightbox()}`;
  }

  function paint() {
    if (!host) return;
    host.innerHTML = render(model);
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox = null;
    paint();
  }

  function mount(el) {
    host = el;
    paint();
    el.onclick = (event) => {
      const openAttach = event.target.closest("[data-attach-open]");
      if (openAttach) {
        lightbox = {
          url: openAttach.dataset.attachUrl || "",
          alt: openAttach.dataset.attachAlt || "Attachment",
        };
        paint();
        return;
      }
      if (event.target.closest("[data-attach-lightbox]") === event.target) {
        closeLightbox();
        return;
      }
      const escalate = event.target.closest("[data-escalate]");
      if (escalate) {
        mailbox.publish(MAILBOX_TOPICS.THREAD_ESCALATE, { ticketId: escalate.dataset.escalate });
        return;
      }
      if (event.target.closest("[data-privacy-gate-open]")) {
        mailbox.publish(MAILBOX_TOPICS.PRIVACY_GATE_OPEN, {});
        return;
      }
      if (event.target.closest("[data-marketing-gate-open]")) {
        mailbox.publish(MAILBOX_TOPICS.MARKETING_GATE_OPEN, {});
        return;
      }
      if (event.target.closest("[data-bug-handled]")) {
        mailbox.publish(MAILBOX_TOPICS.BUG_HANDLED, { ticketId: model.ticket?.id });
        return;
      }
      const button = event.target.closest("[data-summarize]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.COMPOSER_SUMMARIZE, { ticketId: button.dataset.summarize });
    };
    el.onkeydown = (event) => {
      if (event.key === "Escape" && lightbox) {
        event.preventDefault?.();
        closeLightbox();
      }
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
