import { MAILBOX_TOPICS } from "../contracts.js";
import { esc } from "../util.js";

function macroTitle(macro) {
  return macro.title || macro.name || "";
}

function macroHaystack(macro) {
  return `${macro.id || ""} ${macroTitle(macro)} ${(macro.tags || []).join(" ")} ${macro.body || ""}`.toLowerCase();
}

export function composeMacroText(macro, currentBody = "", mode = "replace") {
  const text = macro?.body || "";
  const current = String(currentBody || "");
  if (mode === "append" && current.trim()) return `${current.trimEnd()}\n\n${text}`;
  return text;
}

/**
 * Composer tissue.
 * In: `{ ticket, draft, summarize, macros, body }`
 * Out: body / insert / discard / send. AI strip and macros never Send.
 * Macro search lives inside the composer box. Replace overwrites; Append adds.
 * Draft-strip Insert stays named Insert. The strip sits above the composer box.
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
    selectedMacroId: "",
    searchOpen: true,
    writeGate: null,
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
      selectedMacroId: input.selectedMacroId || "",
      searchOpen: input.searchOpen ?? true,
      writeGate: input.writeGate || null,
    };
  }

  function sendDisabled(next = model) {
    return !String(next.body || "").trim();
  }

  function hideSendAndClose(next = model) {
    return next.ticket?.status === "closed";
  }

  function visibleMacros(next = model) {
    const q = String(next.query || "").trim().toLowerCase();
    return (next.macros || []).filter((macro) => !q || macroHaystack(macro).includes(q));
  }

  function selectedMacro(next = model) {
    return (next.macros || []).find((item) => item.id === next.selectedMacroId) || null;
  }

  function recipient(ticket) {
    if (!ticket) return { name: "", email: "" };
    return {
      name: ticket.customerName || ticket.messages?.[0]?.name || "",
      email: ticket.toEmail || "",
    };
  }

  function render(next = model) {
    const ticket = next.ticket;
    if (!ticket) return `<div class="composer empty-pane">Select a ticket to reply.</div>`;
    const to = recipient(ticket);
    const gate = next.writeGate || {};
    const refused = Array.isArray(gate.refused) ? gate.refused : ["refund", "cancel"];
    const moneyGated = refused.includes("refund") || refused.includes("cancel") || gate.mutationsEnabled === false;
    const writeGate = moneyGated
      ? `<p class="write-gate" data-write-gate>Refunds and cancels are gated.</p>`
      : "";
    const macros = visibleMacros(next);
    const selected = selectedMacro(next);
    const macroItems = macros.map((macro) => (
      `<button type="button" class="macro-row${macro.id === next.selectedMacroId ? " is-selected" : ""}" data-macro="${esc(macro.id)}">
        <span class="macro-bar"></span>
        <span class="macro-title">${esc(macroTitle(macro))}</span>
      </button>`
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
    const idle = sendDisabled(next);
    const sendClose = hideSendAndClose(next)
      ? ""
      : `<button type="button" class="btn-hairline${idle ? " is-disabled" : ""}" data-send-close ${idle ? "disabled" : ""}>Send &amp; close</button>`;
    const macroLocked = selected ? "" : "disabled";
    const searchOpen = next.searchOpen !== false;
    const picker = searchOpen
      ? `<div class="macro-list" data-macro-list>${macroItems || `<p class="macro-empty">No macros match.</p>`}</div>
        <div class="macro-actions">
          <button type="button" class="btn-quiet" data-macro-insert ${macroLocked}>Replace</button>
          <button type="button" class="btn-quiet" data-macro-append ${macroLocked}>Append</button>
        </div>`
      : "";
    return `<section class="composer" data-composer>
      ${peek}
      <div class="composer-to"><span>To</span> <strong>${esc(to.name)}</strong> <span class="mute">${esc(to.email)}</span></div>
      ${writeGate}
      ${strip}
      <div class="composer-box" data-macro-open="${searchOpen ? "true" : "false"}">
        <input class="macro-search" data-macro-search type="search" placeholder="Search macros by name or tags" value="${esc(next.query)}" aria-label="Search macros">
        ${picker}
        <textarea data-body placeholder="Write the reply. The human always sends.">${esc(next.body)}</textarea>
      </div>
      <div class="composer-actions">
        <button type="button" class="btn-ink btn-send${idle ? " is-disabled" : ""}" data-send ${idle ? "disabled" : ""}>Send</button>
        ${sendClose}
      </div>
    </section>`;
  }

  function emitBody(text) {
    model = { ...model, body: text };
    mailbox.publish(MAILBOX_TOPICS.COMPOSER_BODY, { text });
  }

  function applySelected(mode) {
    const macro = selectedMacro(model);
    if (!macro) return;
    const text = composeMacroText(macro, model.body, mode);
    emitBody(text);
    model = {
      ...model,
      body: text,
      searchOpen: false,
      query: "",
      selectedMacroId: "",
    };
    mailbox.publish(MAILBOX_TOPICS.COMPOSER_INSERT, { text, mode, macroId: macro.id });
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.oninput = (event) => {
      if (event.target.matches("[data-body]")) emitBody(event.target.value);
      if (event.target.matches("[data-macro-search]")) {
        model = { ...model, query: event.target.value, searchOpen: true };
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
    el.onclick = (event) => {
      if (event.target.matches?.("[data-macro-search]") && model.searchOpen === false) {
        model = { ...model, searchOpen: true };
        el.innerHTML = render(model);
        const again = el.querySelector("[data-macro-search]");
        if (again) again.focus();
        return;
      }
      const row = event.target.closest("[data-macro]");
      if (row) {
        model = { ...model, selectedMacroId: row.dataset.macro };
        el.innerHTML = render(model);
        return;
      }
      if (event.target.closest("[data-macro-insert]")) {
        applySelected("replace");
        el.innerHTML = render(model);
        return;
      }
      if (event.target.closest("[data-macro-append]")) {
        applySelected("append");
        el.innerHTML = render(model);
        return;
      }
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
    visibleMacros,
    selectedMacro,
    update(input) {
      model = project({ ...model, ...input });
      return model;
    },
    mount,
  };
}
