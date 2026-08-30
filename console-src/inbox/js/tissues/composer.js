import { MAILBOX_TOPICS } from "../contracts.js";
import { esc } from "../util.js";

/**
 * Composer tissue.
 * In: `{ ticket, draft, summarize, macros, body }`
 * Out: body / insert / discard / send. AI strip never Sends.
 */
export function createComposerTissue({ mailbox }) {
  let model = {
    ticket: null,
    draft: "",
    summarize: "",
    macros: [],
    body: "",
    strip: "",
    query: "",
  };

  function project(input) {
    return {
      ticket: input.ticket || null,
      draft: input.draft || "",
      summarize: input.summarize || "",
      macros: input.macros || [],
      body: input.body || "",
      strip: input.strip ?? input.draft ?? "",
      query: input.query || "",
    };
  }

  function sendDisabled(next = model) {
    return !String(next.body || "").trim();
  }

  function hideSendAndClose(next = model) {
    return next.ticket?.status === "closed";
  }

  function recipient(ticket) {
    if (!ticket) return { name: "", email: "" };
    return {
      name: ticket.messages?.[0]?.name || "",
      email: ticket.toEmail || "",
    };
  }

  function render(next = model) {
    const ticket = next.ticket;
    if (!ticket) return `<div class="composer empty-pane">Select a ticket to reply.</div>`;
    const to = recipient(ticket);
    const q = next.query.trim().toLowerCase();
    const macros = next.macros.filter((macro) => {
      if (!q) return true;
      return `${macro.name} ${macro.tags?.join(" ") || ""}`.toLowerCase().includes(q);
    });
    const macroItems = macros.map((macro) => (
      `<label class="macro-row"><input type="checkbox" data-macro="${esc(macro.id)}"> <span>${esc(macro.name)}</span></label>`
    )).join("");
    const peek = next.summarize
      ? `<div class="summarize-peek" data-summarize-peek>
          <p class="draft-kicker">Thread</p>
          <p class="summarize-text">${esc(next.summarize)}</p>
        </div>`
      : "";
    const strip = next.strip
      ? `<div class="draft-strip" data-draft-strip>
          <div>
            <p class="draft-kicker">AI draft</p>
            <p class="draft-text">${esc(next.strip)}</p>
          </div>
          <div class="draft-actions">
            <button type="button" class="btn-quiet" data-insert>Insert</button>
            <button type="button" class="btn-quiet" data-discard>Discard</button>
          </div>
        </div>`
      : "";
    const sendClose = hideSendAndClose(next)
      ? ""
      : `<button type="button" class="btn-hairline" data-send-close ${sendDisabled(next) ? "disabled" : ""}>Send &amp; close</button>`;
    return `<section class="composer" data-composer>
      ${peek}
      <div class="composer-to"><span>To</span> <strong>${esc(to.name)}</strong> <span class="mute">${esc(to.email)}</span></div>
      <div class="composer-box">
        <input class="macro-search" data-macro-search type="search" placeholder="Search macros by name or tags" value="${esc(next.query)}">
        <div class="macro-list">${macroItems}</div>
        ${strip}
        <textarea data-body placeholder="Write the reply. The human always sends.">${esc(next.body)}</textarea>
      </div>
      <div class="composer-actions">
        <button type="button" class="btn-ink btn-send" data-send ${sendDisabled(next) ? "disabled" : ""}>Send</button>
        ${sendClose}
      </div>
    </section>`;
  }

  function emitBody(text) {
    model = { ...model, body: text };
    mailbox.publish(MAILBOX_TOPICS.COMPOSER_BODY, { text });
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.oninput = (event) => {
      if (event.target.matches("[data-body]")) emitBody(event.target.value);
      if (event.target.matches("[data-macro-search]")) {
        model = { ...model, query: event.target.value };
        const keep = event.target;
        const start = keep.selectionStart;
        el.innerHTML = render(model);
        const again = el.querySelector("[data-macro-search]");
        if (again) {
          again.focus();
          again.setSelectionRange(start, start);
        }
      }
    };
    el.onchange = (event) => {
      const box = event.target.closest("[data-macro]");
      if (!box) return;
      const macro = model.macros.find((item) => item.id === box.dataset.macro);
      if (!macro) return;
      const next = model.body ? `${model.body}\n\n${macro.body}` : macro.body;
      emitBody(next);
      mailbox.publish(MAILBOX_TOPICS.COMPOSER_INSERT, { text: macro.body });
      el.innerHTML = render({ ...model, body: next });
    };
    el.onclick = (event) => {
      if (event.target.closest("[data-insert]")) {
        const text = model.strip || model.draft || "";
        const next = model.body ? `${model.body}\n\n${text}` : text;
        emitBody(next);
        model = { ...model, body: next, strip: "" };
        mailbox.publish(MAILBOX_TOPICS.COMPOSER_INSERT, { text });
        el.innerHTML = render(model);
        return;
      }
      if (event.target.closest("[data-discard]")) {
        model = { ...model, strip: "" };
        mailbox.publish(MAILBOX_TOPICS.COMPOSER_DISCARD, {});
        el.innerHTML = render(model);
        return;
      }
      if (event.target.closest("[data-send-close]")) {
        if (sendDisabled(model) || hideSendAndClose(model)) return;
        mailbox.publish(MAILBOX_TOPICS.COMPOSER_SEND, { text: model.body, close: true });
        return;
      }
      if (event.target.closest("[data-send]")) {
        if (sendDisabled(model)) return;
        mailbox.publish(MAILBOX_TOPICS.COMPOSER_SEND, { text: model.body, close: false });
      }
    };
  }

  return {
    id: "composer",
    project,
    render,
    sendDisabled,
    hideSendAndClose,
    update(input) {
      model = project({ ...model, ...input });
      return model;
    },
    mount,
  };
}
