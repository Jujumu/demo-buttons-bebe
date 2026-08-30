/**
 * Mailbox-style wiring. Tissues publish typed envelopes; they never peek
 * inside another tissue. A listener that throws is isolated.
 */

export function createMailbox() {
  /** @type {Map<string, Set<Function>>} */
  const listeners = new Map();
  /** @type {Array<{ topic: string, payload: unknown, error: string }>} */
  const failures = [];

  function subscribe(topic, fn) {
    if (!listeners.has(topic)) listeners.set(topic, new Set());
    listeners.get(topic).add(fn);
    return () => listeners.get(topic)?.delete(fn);
  }

  function publish(topic, payload) {
    const set = listeners.get(topic);
    if (!set) return;
    for (const fn of set) {
      try {
        fn(payload);
      } catch (err) {
        failures.push({ topic, payload, error: String(err?.message || err) });
      }
    }
  }

  return {
    subscribe,
    publish,
    failures: () => failures.slice(),
  };
}
