import { MAILBOX_TOPICS } from "../contracts.js";
import { esc } from "../util.js";

/**
 * View tissue. Counts come from helpdesk.list_tickets per view.
 * In: `{ views, counts, selectedViewId }`
 * Out: `{ viewId }` on `view/selected`
 */
export function createViewTissue({ mailbox }) {
  let model = { views: [], counts: {}, selectedViewId: "mine" };

  function project(input) {
    return {
      views: input.views || [],
      counts: input.counts || {},
      selectedViewId: input.selectedViewId || "mine",
    };
  }

  function render(next = model) {
    const items = next.views.map((view) => {
      const on = view.id === next.selectedViewId;
      const count = next.counts[view.id] ?? 0;
      return `<button type="button" class="view-item${on ? " is-selected" : ""}" data-view="${esc(view.id)}" aria-current="${on ? "true" : "false"}">
        <span class="view-label">${esc(view.label)}</span>
        <span class="view-count">${esc(count)}</span>
      </button>`;
    }).join("");
    return `<div class="pane-inner">
      <header class="pane-head">
        <div>
          <a class="console-link" href="../index.html">Console</a>
          <h1>Inbox</h1>
        </div>
      </header>
      <div class="view-list" role="list">${items}</div>
    </div>`;
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.onclick = (event) => {
      const button = event.target.closest("[data-view]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.VIEW_SELECTED, { viewId: button.dataset.view });
    };
  }

  return {
    id: "view",
    project,
    render,
    update(input) {
      model = project(input);
      return model;
    },
    mount,
  };
}
