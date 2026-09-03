import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const bootError = document.getElementById("boot-error");
function fail(msg) {
  bootError.style.display = "block";
  bootError.textContent = msg;
}

if (typeof gsap === "undefined") {
  fail("GSAP did not load. Check docs/tissues/vendor/gsap.min.js");
  throw new Error("gsap missing");
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const dur = (s) => (reduceMotion ? 0 : s);

const WIRE_LEGEND = `
  <div class="wire-key">
    <span>
      <svg class="wire-ico" viewBox="0 0 34 10" aria-hidden="true">
        <line x1="1" y1="3" x2="33" y2="3" stroke="#1c1916" stroke-width="1.8"/>
        <line x1="1" y1="7" x2="33" y2="7" stroke="#1c1916" stroke-width="1.8"/>
        <circle cx="3" cy="5" r="2.2" fill="#44403c"/>
        <circle cx="31" cy="5" r="2.2" fill="#44403c"/>
      </svg>
      Twin wire, jacked on both ends = ask and answer
    </span>
    <span>
      <svg class="wire-ico" viewBox="0 0 34 10" aria-hidden="true">
        <line x1="1" y1="5" x2="28" y2="5" stroke="#1c1916" stroke-width="2"/>
        <polygon points="28,2 33,5 28,8" fill="#1c1916"/>
      </svg>
      Single wire, arrow one way = push only
    </span>
    <span>This drawing is the demo helpdesk only — not Gorgias / Redo / KB.</span>
  </div>`;

const ORGANS = [
  {
    id: "mail",
    name: "Customer mail",
    form: "mail",
    kid: "A letter lands in the demo mailbox. Helpdesk intake turns it into a ticket — the inbox only reads after that.",
    color: 0xf9a8b4,
    pos: [-16, 1.5, 0],
    size: [3.6, 3.0, 2.6],
    tissues: [
      {
        name: "Inbound letter",
        shape: "mail",
        kid: "AgentMail unread mail. pull_mailbox maps it onto ingest_email. Prize / lottery junk never becomes a ticket.",
        inn: "AgentMail message",
        out: "helpdesk.ingest_email — not the inbox pane",
      },
    ],
  },
  {
    id: "inbox",
    name: "Inbox organ",
    form: "inbox",
    kid: "The four-pane window you look through. It is a client, not the product.",
    color: 0x60a5fa,
    pos: [-7.5, 1.8, 0],
    size: [4.4, 3.5, 3.0],
    tissues: [
      {
        name: "View",
        shape: "cards",
        kid: "Picks which pile of tickets you are looking at: assigned, all, snoozed, closed.",
        inn: "{ views, counts, selectedViewId }",
        out: "view/selected → { viewId }",
      },
      {
        name: "List",
        shape: "cards",
        kid: "The stack of tickets. The selected row gets a 4px ink bar — no grey wash.",
        inn: "helpdesk.list_tickets { view, limit }",
        out: "list/selected → { ticketId }",
      },
      {
        name: "Thread",
        shape: "chat",
        kid: "The conversation. Status lines like “Closed · Tuesday” are ticket events, not Shopify fulfillment.",
        inn: "helpdesk.get_ticket { ticketId }",
        out: "composer/summarize (a mute peek, not a send)",
      },
      {
        name: "Composer",
        shape: "pen",
        kid: "Where you type. AI may Insert or Discard a draft. Only you may Send.",
        inn: "ticket + draft + macros",
        out: "body / insert / discard / send",
      },
      {
        name: "Rail",
        shape: "inbox",
        nested: true,
        kid: "The side panel. It is an organ of its own — customer, this order, returns, past orders.",
        inn: "GIDs from the selected ticket",
        out: "Clerk shop data, look-only",
      },
    ],
  },
  {
    id: "helpdesk",
    name: "Helpdesk organ",
    form: "cluster",
    kid: "The real body. Every tissue is a black box: In → Out. MCP and CLI share the same room.",
    color: 0xfb923c,
    pos: [3.2, 2.0, 0],
    size: [5.4, 4.0, 3.6],
    tissues: [
      { name: "list_tickets", shape: "cards", kid: "Shows the ticket rows for a view. Names come from the mail From line, not Shopify displayName.", inn: "{ view, limit }", out: "id, customerName, subject, snippet, status…" },
      { name: "get_ticket", shape: "chat", kid: "Opens one conversation: messages plus status events.", inn: "{ ticketId }", out: "ticket + messages + statusEvents" },
      { name: "get_customer", shape: "person", kid: "Looks up the shopper. Email is defaultEmailAddress — never the old Customer.email field.", inn: "{ shop, customerId }", out: "ClerkCustomer" },
      { name: "get_order", shape: "package", kid: "Looks up this order: money, line items, tracking. Look only.", inn: "{ shop, orderId }", out: "ClerkOrder" },
      { name: "get_returns", shape: "loop", kid: "Looks up returns on Shopify. “Open” means Return.status OPEN — not ticket status. Not Redo.", inn: "{ shop, orderId }", out: "returns payload" },
      { name: "list_past_orders", shape: "package", kid: "Older orders, newest first. Peeking one does not replace This order.", inn: "{ shop, customerId }", out: "order-history rows" },
      { name: "draft_reply", shape: "pen", kid: "Writes a suggested reply. You Insert or Discard. It never hits Send.", inn: "{ ticketId, shop? }", out: "{ draft }" },
      { name: "summarize_thread", shape: "chat", kid: "A quiet peek at what the thread is about. Not a reply.", inn: "{ ticketId }", out: "{ summary }" },
      { name: "search_macros", shape: "stamp", kid: "Finds canned replies (shipping delay, returns, order status).", inn: "{ query? }", out: "{ macros: [{ id, title, body }] }" },
      { name: "apply_macro", shape: "stamp", kid: "Drops a canned reply into the box. Replace or append. Still not Send.", inn: "{ macroId, mode }", out: "text for the textarea" },
      { name: "ingest_email", shape: "mail", kid: "Turns a letter into a ticket — or marks prize-mail as spam.", inn: "{ from, subject, body, receivedAt }", out: "ticket row or { spam: true }" },
      { name: "ingest_chat", shape: "chat", kid: "Same as email, but from chat. No email address, so it joins on #1001-style order names only.", inn: "{ fromName, body, receivedAt }", out: "ticket row or spam" },
      { name: "pull_mailbox", shape: "mail", kid: "Reads the demo mailbox and feeds each letter into ingest_email. Never sends mail.", inn: "{ limit? }", out: "{ ingested, spam, skipped }" },
    ],
  },
  {
    id: "look",
    name: "Shopify (look-only)",
    form: "books",
    kid: "The only shop book in this demo. Returns, orders, and customers come from Shopify Admin — not Redo, not a KB.",
    color: 0xeab308,
    pos: [13.4, 1.7, 0],
    size: [4.2, 3.4, 3.0],
    tissues: [
      { name: "Shopify", shape: "bag", kid: "Admin GraphQL 2026-07, read-only. SHOPIFY_MUTATIONS_ENABLED stays 0. get_customer / get_order / get_returns / list_past_orders all read here (or fixtures).", inn: "customer / order GIDs", out: "Clerk customer, order, returns, history" },
    ],
  },
  {
    id: "send",
    name: "Human send gate",
    form: "gate",
    kid: "Composer safety door. Send writes onto the local thread. This demo does not email the customer back.",
    color: 0xf87171,
    pos: [-7.5, 1.6, 10],
    size: [4.8, 3.4, 3.0],
    tissues: [
      { name: "Send", shape: "gate", kid: "A human click in the composer. Appends a message on this ticket in the inbox. There is no helpdesk.send and no AgentMail outbound.", inn: "text in the composer", out: "local thread row — not a real email" },
      { name: "Insert / Discard", shape: "pen", kid: "What the draft strip may do. It fills or clears the box. It does not send.", inn: "{ draft }", out: "composer body, still unsent" },
    ],
  },
];

const RAIL = {
  id: "rail",
  name: "Rail organ",
  form: "inbox",
  color: 0x93c5fd,
  kid: "The right-hand panel. Four tissues. If one breaks, the others keep working.",
  tissues: [
    { name: "Customer", shape: "person", kid: "Who wrote in. Empty copy: “No customer on this ticket.” No Edit button.", inn: "{ shop, customerId }", out: "name, email, orders, spend" },
    { name: "This order", shape: "package", kid: "The order on this ticket, with little product pictures. Clicking past orders does not replace it.", inn: "{ shop, orderId }", out: "name, paid/fulfilled, line items, tracking" },
    { name: "Returns", shape: "loop", kid: "Shopify Return.status on this order. Open only if THIS ticket has an OPEN return. No Redo. No refund / cancel.", inn: "{ shop, orderId }", out: "Return.status" },
    { name: "Past orders", shape: "package", kid: "A peek list. Starts collapsed. Does not swap out This order.", inn: "{ shop, customerId }", out: "newest-first rows" },
  ],
};

// Helpdesk floor plan — clustered like the real handlers, not a necklace.
const HELPDESK_LAYOUT = {
  pull_mailbox: [-5.6, 1.05, 2.6],
  ingest_email: [-5.6, 1.05, 0.3],
  ingest_chat: [-5.6, 1.05, -2.0],
  list_tickets: [-1.9, 1.05, 5.2],
  get_ticket: [1.9, 1.05, 5.2],
  draft_reply: [5.6, 1.05, 2.8],
  summarize_thread: [5.6, 1.05, 0.7],
  search_macros: [5.6, 1.05, -1.4],
  apply_macro: [5.6, 1.05, -3.5],
  get_customer: [-3.4, 1.05, -4.6],
  get_order: [3.4, 1.05, -4.6],
  get_returns: [-3.4, 1.05, -7.6],
  list_past_orders: [3.4, 1.05, -7.6],
};

const host = document.getElementById("canvas-host");
const titleEl = document.getElementById("title");
const ledeEl = document.getElementById("lede");
const metaEl = document.getElementById("meta");
const crumbEl = document.getElementById("crumb");
const backBtn = document.getElementById("btn-back");
const resetBtn = document.getElementById("btn-reset");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xefe7dc);
scene.fog = new THREE.Fog(0xefe7dc, 40, 110);

const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 200);
camera.position.set(5, 15, 30);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
host.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.maxPolarAngle = Math.PI * 0.48;
controls.minDistance = 8;
controls.maxDistance = 52;
controls.target.set(1.5, 1.6, 3);
const homeCam = { x: 5, y: 15, z: 30, tx: 1.5, ty: 1.6, tz: 3 };

scene.add(new THREE.HemisphereLight(0xfff4e8, 0x8a9bb5, 0.85));
const key = new THREE.DirectionalLight(0xfff7ee, 1.35);
key.position.set(-12, 22, 14);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.near = 2;
key.shadow.camera.far = 70;
key.shadow.camera.left = -32;
key.shadow.camera.right = 32;
key.shadow.camera.top = 24;
key.shadow.camera.bottom = -24;
scene.add(key);
scene.add(new THREE.DirectionalLight(0xb9d4ff, 0.32).translateX(18).translateY(8).translateZ(-10));

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(52, 64),
  new THREE.MeshStandardMaterial({ color: 0xe7ddd0, roughness: 0.95, metalness: 0 })
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(52, 26, 0xd4cbbd, 0xe0d6c8);
grid.position.y = 0.01;
scene.add(grid);

function stdMat(color, extra = {}) {
  const c = new THREE.Color(color);
  return new THREE.MeshStandardMaterial({
    color: c,
    roughness: extra.roughness ?? 0.42,
    metalness: extra.metalness ?? 0.08,
    emissive: extra.emissive ?? c.clone().multiplyScalar(0.1),
    emissiveIntensity: extra.emissiveIntensity ?? 0.12,
    ...extra,
  });
}

function metalMat(color = 0x44403c) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: 0.28,
    metalness: 0.82,
    emissive: 0x111111,
    emissiveIntensity: 0.08,
  });
}

function paint(root) {
  root.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return root;
}

function legoMat(color) {
  return stdMat(color, { roughness: 0.2, metalness: 0.04, emissiveIntensity: 0.07 });
}

function shadeHex(hex, f) {
  return new THREE.Color(hex).multiplyScalar(f).getHex();
}

function addStuds(parent, width, depth, yTop, color, s = 1) {
  const pitch = 0.48 * s;
  const nx = Math.max(2, Math.round(width / pitch));
  const nz = Math.max(2, Math.round(depth / pitch));
  const mat = legoMat(color);
  const x0 = -((nx - 1) / 2) * pitch;
  const z0 = -((nz - 1) / 2) * pitch;
  const h = 0.15 * s;
  const r = 0.13 * s;
  for (let ix = 0; ix < nx; ix++) {
    for (let iz = 0; iz < nz; iz++) {
      const stud = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 10), mat);
      stud.position.set(x0 + ix * pitch, yTop + h / 2, z0 + iz * pitch);
      parent.add(stud);
    }
  }
}

function legoBrick(w, h, d, color) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), legoMat(color)));
  const layers = Math.max(2, Math.round(h / 0.38));
  const grooveMat = legoMat(shadeHex(color, 0.78));
  for (let i = 1; i < layers; i++) {
    const groove = new THREE.Mesh(new THREE.BoxGeometry(w + 0.03, 0.045, d + 0.03), grooveMat);
    groove.position.y = -h / 2 + (i * h) / layers;
    g.add(groove);
  }
  addStuds(g, w * 0.86, d * 0.86, h / 2, color);
  return g;
}

function addWindow(parent, x, y, z, ww, hh) {
  const frame = new THREE.Mesh(new THREE.BoxGeometry(ww + 0.08, hh + 0.08, 0.08), legoMat(0xfffdf9));
  frame.position.set(x, y, z);
  parent.add(frame);
  const glass = new THREE.Mesh(new THREE.BoxGeometry(ww, hh, 0.06), legoMat(0x7dd3fc));
  glass.position.set(x, y, z + 0.03);
  parent.add(glass);
}

function addDoor(parent, x, y, z, ww, hh, color = 0x1c1916) {
  const door = new THREE.Mesh(new THREE.BoxGeometry(ww, hh, 0.1), legoMat(color));
  door.position.set(x, y, z);
  parent.add(door);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 8), metalMat(0xfbbf24));
  knob.position.set(x + ww * 0.28, y, z + 0.08);
  parent.add(knob);
}

function addPitchedRoof(parent, w, h, d, roofColor) {
  const slope = new THREE.BoxGeometry(w * 1.12, 0.2, d * 0.72);
  const left = new THREE.Mesh(slope, legoMat(roofColor));
  left.rotation.x = 0.72;
  left.position.set(0, h / 2 + 0.42, -d * 0.22);
  parent.add(left);
  const right = new THREE.Mesh(slope.clone(), legoMat(roofColor));
  right.rotation.x = -0.72;
  right.position.set(0, h / 2 + 0.42, d * 0.22);
  parent.add(right);
  const ridge = new THREE.Mesh(new THREE.BoxGeometry(w * 1.14, 0.14, 0.2), legoMat(shadeHex(roofColor, 0.75)));
  ridge.position.y = h / 2 + 0.78;
  parent.add(ridge);
  addStuds(parent, w * 0.35, 0.35, h / 2 + 0.86, roofColor, 0.85);
}

function makeLegoBuilding({ color, w, h, d, roof = false, roofColor = 0xb91c1c, facade = "house", sign, signScale = 0.5 }) {
  const g = new THREE.Group();
  g.add(legoBrick(w, h, d, color));
  const z = d / 2 + 0.02;
  if (facade === "house") {
    addDoor(g, 0, -h * 0.18, z, 0.55, h * 0.55, 0x7c2d12);
    addWindow(g, -w * 0.28, h * 0.12, z, 0.55, 0.5);
    addWindow(g, w * 0.28, h * 0.12, z, 0.55, 0.5);
  } else if (facade === "inbox") {
    addWindow(g, -w * 0.2, h * 0.12, z, 0.7, 0.55);
    addWindow(g, w * 0.2, h * 0.12, z, 0.7, 0.55);
    addWindow(g, -w * 0.2, -h * 0.16, z, 0.7, 0.55);
    addWindow(g, w * 0.2, -h * 0.16, z, 0.7, 0.55);
  } else if (facade === "cluster") {
    for (const x of [-w * 0.28, 0, w * 0.28]) {
      addWindow(g, x, h * 0.18, z, 0.48, 0.4);
      addWindow(g, x, -h * 0.08, z, 0.48, 0.4);
    }
    addDoor(g, 0, -h * 0.32, z, 0.62, h * 0.32, 0x9a3412);
  } else if (facade === "books") {
    addWindow(g, -w * 0.22, 0.05, z, 0.45, h * 0.55);
    addWindow(g, w * 0.22, 0.05, z, 0.45, h * 0.55);
    addDoor(g, 0, -h * 0.18, z, 0.5, h * 0.5, 0x92400e);
  } else if (facade === "gate") {
    addDoor(g, 0, -h * 0.08, z, 1.15, h * 0.72, 0x1c1916);
    addWindow(g, -w * 0.32, h * 0.18, z, 0.4, 0.4);
    addWindow(g, w * 0.32, h * 0.18, z, 0.4, 0.4);
  }
  if (roof) addPitchedRoof(g, w, h, d, roofColor);
  const signMesh = makeShape(sign, 0xfff7ed, signScale);
  signMesh.position.y = roof ? h / 2 + 1.35 : h / 2 + 0.72;
  g.add(signMesh);
  return paint(g);
}

function makeLegoMini(color, sign, signScale = 0.42) {
  const g = new THREE.Group();
  g.add(legoBrick(1.7, 1.15, 1.5, color));
  const signMesh = makeShape(sign, 0xfff7ed, signScale);
  signMesh.position.y = 1.05;
  g.add(signMesh);
  return paint(g);
}

function makeLegoOrgan(organ) {
  const w = organ.size[0] * 0.92;
  const h = organ.size[1] * 0.72;
  const d = Math.max(organ.size[2], 2.3);
  const facade = organ.id === "mail" ? "house"
    : organ.id === "inbox" ? "inbox"
    : organ.id === "helpdesk" ? "cluster"
    : organ.id === "look" ? "books"
    : "gate";
  return makeLegoBuilding({
    color: organ.color,
    w,
    h,
    d,
    roof: organ.id === "mail" || organ.id === "send",
    roofColor: organ.id === "mail" ? 0xdc2626 : 0x7f1d1d,
    facade,
    sign: organ.form,
    signScale: organ.id === "helpdesk" ? 0.42 : 0.52,
  });
}

function addHit(group, w, h, d) {
  const hit = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshBasicMaterial({ visible: false })
  );
  hit.name = "hit";
  group.add(hit);
  return group;
}

function orientY(obj, dir) {
  obj.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
}

function formMail(color, s = 1) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(2.9 * s, 1.85 * s, 0.28 * s), stdMat(color));
  g.add(body);
  const flap = new THREE.Mesh(new THREE.ConeGeometry(1.55 * s, 1.35 * s, 3), stdMat(color, { roughness: 0.5 }));
  flap.rotation.set(Math.PI, 0, Math.PI / 2);
  flap.position.set(0, 0.22 * s, 0.22 * s);
  g.add(flap);
  const stripe = new THREE.Mesh(new THREE.BoxGeometry(2.5 * s, 0.08 * s, 0.3 * s), stdMat(0x1c1916));
  stripe.position.y = -0.55 * s;
  g.add(stripe);
  return paint(g);
}

function formInbox(color, s = 1) {
  const g = new THREE.Group();
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(3.8 * s, 2.55 * s, 0.28 * s), stdMat(0x1c1916));
  g.add(bezel);
  const screen = new THREE.Mesh(new THREE.BoxGeometry(3.5 * s, 2.25 * s, 0.12 * s), stdMat(color));
  screen.position.z = 0.14 * s;
  g.add(screen);
  const vbar = new THREE.Mesh(new THREE.BoxGeometry(0.08 * s, 2.2 * s, 0.16 * s), stdMat(0x1c1916));
  vbar.position.z = 0.2 * s;
  g.add(vbar);
  const hbar = new THREE.Mesh(new THREE.BoxGeometry(3.45 * s, 0.08 * s, 0.16 * s), stdMat(0x1c1916));
  hbar.position.z = 0.2 * s;
  g.add(hbar);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.22 * s, 0.7 * s, 12), metalMat());
  neck.position.y = -1.55 * s;
  g.add(neck);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.95 * s, 1.05 * s, 0.16 * s, 24), metalMat());
  base.position.y = -1.95 * s;
  g.add(base);
  return paint(g);
}

function formCluster(color, s = 1) {
  const g = new THREE.Group();
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.35 * s, 0), stdMat(color, { roughness: 0.32 }));
  g.add(core);
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2;
    const y = ((i % 3) - 1) * 0.7 * s;
    const cube = new THREE.Mesh(new THREE.BoxGeometry(0.7 * s, 0.55 * s, 0.55 * s), stdMat(0xffedd5));
    cube.position.set(Math.cos(a) * 1.7 * s, y, Math.sin(a) * 1.7 * s);
    g.add(cube);
  }
  return paint(g);
}

function formBooks(color, s = 1) {
  const g = new THREE.Group();
  const cols = [color, 0xf59e0b, 0xca8a04];
  [-0.9, 0, 0.95].forEach((x, i) => {
    const h = (2.4 - i * 0.25) * s;
    const book = new THREE.Mesh(new THREE.BoxGeometry(0.55 * s, h, 1.7 * s), stdMat(cols[i]));
    book.position.set(x * s, h / 2 - 1.2 * s, 0);
    book.rotation.y = (i - 1) * 0.08;
    g.add(book);
  });
  const shackle = new THREE.Mesh(new THREE.TorusGeometry(0.28 * s, 0.07 * s, 8, 16, Math.PI), metalMat(0x292524));
  shackle.position.set(1.35 * s, 0.55 * s, 0.55 * s);
  shackle.rotation.z = Math.PI;
  g.add(shackle);
  const lock = new THREE.Mesh(new THREE.BoxGeometry(0.42 * s, 0.38 * s, 0.22 * s), metalMat(0x292524));
  lock.position.set(1.35 * s, 0.22 * s, 0.55 * s);
  g.add(lock);
  return paint(g);
}

function formGate(color, s = 1) {
  const g = new THREE.Group();
  [-1.2, 1.2].forEach((x) => {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.18 * s, 0.22 * s, 3.1 * s, 12), stdMat(color));
    post.position.set(x * s, 0, 0);
    g.add(post);
  });
  const arch = new THREE.Mesh(new THREE.TorusGeometry(1.22 * s, 0.16 * s, 8, 20, Math.PI), stdMat(color));
  arch.rotation.z = Math.PI;
  arch.position.y = 1.35 * s;
  g.add(arch);
  const bar = new THREE.Mesh(new THREE.BoxGeometry(2.1 * s, 0.22 * s, 0.22 * s), stdMat(0x1c1916));
  bar.position.y = 0.15 * s;
  g.add(bar);
  return paint(g);
}

function formPerson(color, s = 1) {
  const g = new THREE.Group();
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.38 * s, 16, 12), stdMat(color));
  head.position.y = 0.85 * s;
  g.add(head);
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.42 * s, 0.7 * s, 6, 12), stdMat(color));
  body.position.y = -0.05 * s;
  g.add(body);
  return paint(g);
}

function formPackage(color, s = 1) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.BoxGeometry(1.5 * s, 1.15 * s, 1.5 * s), stdMat(color)));
  const tape = new THREE.Mesh(new THREE.BoxGeometry(1.55 * s, 0.12 * s, 0.18 * s), stdMat(0x1c1916));
  tape.position.y = 0.2 * s;
  g.add(tape);
  return paint(g);
}

function formChat(color, s = 1) {
  const g = new THREE.Group();
  const bubble = new THREE.Mesh(new THREE.SphereGeometry(0.72 * s, 16, 12), stdMat(color));
  bubble.scale.set(1.15, 0.9, 0.85);
  g.add(bubble);
  const tail = new THREE.Mesh(new THREE.ConeGeometry(0.28 * s, 0.4 * s, 8), stdMat(color));
  tail.rotation.z = 0.7;
  tail.position.set(-0.55 * s, -0.55 * s, 0.2 * s);
  g.add(tail);
  return paint(g);
}

function formCards(color, s = 1) {
  const g = new THREE.Group();
  for (let i = 0; i < 3; i++) {
    const card = new THREE.Mesh(new THREE.BoxGeometry(1.6 * s, 0.18 * s, 1.1 * s), stdMat(i === 2 ? 0x1c1916 : color));
    card.position.set(i * 0.08 * s, (i - 1) * 0.28 * s, i * 0.06 * s);
    card.rotation.z = (i - 1) * 0.08;
    g.add(card);
  }
  return paint(g);
}

function formPen(color, s = 1) {
  const g = new THREE.Group();
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * s, 0.12 * s, 1.7 * s, 10), stdMat(color));
  shaft.rotation.z = Math.PI / 3;
  g.add(shaft);
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.12 * s, 0.35 * s, 10), stdMat(0x1c1916));
  tip.rotation.z = Math.PI / 3;
  tip.position.set(0.62 * s, -0.36 * s, 0);
  g.add(tip);
  const pad = new THREE.Mesh(new THREE.BoxGeometry(1.4 * s, 0.08 * s, 1.1 * s), stdMat(0xfffdf9));
  pad.position.y = -0.55 * s;
  g.add(pad);
  return paint(g);
}

function formLoop(color, s = 1) {
  const g = new THREE.Group();
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.7 * s, 0.16 * s, 10, 24), stdMat(color));
  ring.rotation.x = Math.PI / 2.6;
  g.add(ring);
  const arrow = new THREE.Mesh(new THREE.ConeGeometry(0.22 * s, 0.4 * s, 8), stdMat(color));
  arrow.position.set(0.7 * s, 0.35 * s, 0);
  arrow.rotation.z = -0.9;
  g.add(arrow);
  return paint(g);
}

function formBag(color, s = 1) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.BoxGeometry(1.35 * s, 1.15 * s, 0.7 * s), stdMat(color)));
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.35 * s, 0.07 * s, 8, 16, Math.PI), metalMat());
  handle.position.y = 0.75 * s;
  handle.rotation.z = Math.PI;
  g.add(handle);
  return paint(g);
}

function formBook(color, s = 1) {
  const g = new THREE.Group();
  const book = new THREE.Mesh(new THREE.BoxGeometry(1.15 * s, 1.55 * s, 0.38 * s), stdMat(color));
  g.add(book);
  const spine = new THREE.Mesh(new THREE.BoxGeometry(0.12 * s, 1.55 * s, 0.4 * s), stdMat(0x1c1916));
  spine.position.x = -0.52 * s;
  g.add(spine);
  return paint(g);
}

function formStamp(color, s = 1) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.BoxGeometry(1.3 * s, 0.35 * s, 1.3 * s), stdMat(color)));
  g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.35 * s, 0.45 * s, 0.7 * s, 12), stdMat(0x1c1916)));
  g.children[1].position.y = 0.5 * s;
  return paint(g);
}

const FORMS = {
  mail: formMail,
  inbox: formInbox,
  cluster: formCluster,
  books: formBooks,
  gate: formGate,
  person: formPerson,
  package: formPackage,
  chat: formChat,
  cards: formCards,
  pen: formPen,
  loop: formLoop,
  bag: formBag,
  book: formBook,
  stamp: formStamp,
};

function makeShape(kind, color, scale = 1) {
  const fn = FORMS[kind] || formPackage;
  return fn(color, scale);
}

function makeLabel(text, w = 512, h = 160, fill = "#1c1916") {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "rgba(255,253,249,0.94)";
  roundRect(ctx, 8, 24, w - 16, h - 48, 18);
  ctx.fill();
  ctx.fillStyle = fill;
  ctx.font = "700 40px Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const max = w - 48;
  let size = 40;
  ctx.font = `700 ${size}px Arial`;
  while (ctx.measureText(text).width > max && size > 22) {
    size -= 2;
    ctx.font = `700 ${size}px Arial`;
  }
  ctx.fillText(text, w / 2, h / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  spr.scale.set(4.4, 1.35, 1);
  spr.renderOrder = 10;
  spr.raycast = () => {};
  return spr;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

const overview = new THREE.Group();
scene.add(overview);
const detail = new THREE.Group();
detail.visible = false;
scene.add(detail);

const clickables = [];
const overviewPackets = [];
const detailPackets = [];

function offsetFace(organ, n) {
  const p = new THREE.Vector3(...organ.pos);
  const d = n.clone().normalize();
  p.x += d.x * organ.size[0] / 2;
  p.y += d.y * organ.size[1] / 2;
  p.z += d.z * organ.size[2] / 2;
  return p;
}

function facePoint(organ, other) {
  const p = new THREE.Vector3(...organ.pos);
  const q = new THREE.Vector3(...other.pos);
  const d = q.clone().sub(p);
  const hx = organ.size[0] / 2;
  const hy = organ.size[1] / 2;
  const hz = organ.size[2] / 2;
  const ax = Math.abs(d.x);
  const ay = Math.abs(d.y);
  const az = Math.abs(d.z);
  if (ax >= az && ax >= ay) p.x += Math.sign(d.x) * hx;
  else if (az >= ax && az >= ay) p.z += Math.sign(d.z) * hz;
  else p.y += Math.sign(d.y || 1) * hy;
  return p;
}

function makeSocket(at, toward) {
  const g = new THREE.Group();
  g.position.copy(at);
  const dir = toward.clone().sub(at).normalize();
  const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.44, 0.14, 16), metalMat(0x292524));
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.38, 12), metalMat(0x78716c));
  pin.position.y = 0.22;
  g.add(flange);
  g.add(pin);
  orientY(g, dir);
  paint(g);
  g.raycast = () => {};
  return g;
}

function makeArrow(at, dir, color) {
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.4, 0.78, 12), stdMat(color, { roughness: 0.35 }));
  cone.position.copy(at);
  orientY(cone, dir);
  paint(cone);
  cone.raycast = () => {};
  return cone;
}

function cableCurve(a, b, lift, side) {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const dir = b.clone().sub(a).normalize();
  const bin = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0));
  if (bin.lengthSq() < 0.001) bin.set(1, 0, 0);
  bin.normalize().multiplyScalar(side);
  mid.y += lift;
  mid.add(bin);
  const a2 = a.clone().add(bin);
  const b2 = b.clone().add(bin);
  return new THREE.CatmullRomCurve3([a2, mid, b2]);
}

function addTube(curve, color, radius, parent = overview) {
  const mesh = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 56, radius, 8, false),
    new THREE.MeshStandardMaterial({
      color,
      roughness: 0.35,
      metalness: 0.45,
      emissive: new THREE.Color(color).multiplyScalar(0.08),
    })
  );
  mesh.castShadow = true;
  mesh.raycast = () => {};
  parent.add(mesh);
  return mesh;
}

function addPulse(curve, color, speed, reverse = false, parent = overview, packetList = overviewPackets) {
  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(0.16, 12, 12),
    new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.7 })
  );
  ball.castShadow = true;
  ball.raycast = () => {};
  parent.add(ball);
  packetList.push({ curve, ball, t: Math.random(), speed, reverse });
}

function brickFace(from, to, half = 0.95) {
  const a = from.clone();
  const d = to.clone().sub(from);
  const ax = Math.abs(d.x);
  const ay = Math.abs(d.y);
  const az = Math.abs(d.z);
  if (ax >= az && ax >= ay) a.x += Math.sign(d.x || 1) * half;
  else if (az >= ax && az >= ay) a.z += Math.sign(d.z || 1) * half;
  else a.y += Math.sign(d.y || 1) * half;
  return a;
}

function addSpokeAt(parent, packetList, from, to, color, opts = {}) {
  const a = opts.raw ? from.clone() : brickFace(from, to, opts.halfA ?? 0.95);
  const b = opts.raw ? to.clone() : brickFace(to, from, opts.halfB ?? 0.55);
  parent.add(makeSocket(a, b));
  parent.add(makeSocket(b, a));
  const curve = cableCurve(a, b, opts.lift ?? 0.4, opts.side ?? 0);
  addTube(curve, color, opts.radius ?? 0.04, parent);
  addPulse(curve, color, opts.speed ?? 0.0032, false, parent, packetList);
}

function addDuplexAt(parent, packetList, from, to, color, opts = {}) {
  const a = opts.raw ? from.clone() : brickFace(from, to, opts.halfA ?? 0.95);
  const b = opts.raw ? to.clone() : brickFace(to, from, opts.halfB ?? 0.95);
  parent.add(makeSocket(a, b));
  parent.add(makeSocket(b, a));
  const lift = opts.lift ?? 1.2;
  const side = opts.side ?? 0.28;
  const radius = opts.radius ?? 0.06;
  const c1 = cableCurve(a, b, lift, side);
  const c2 = cableCurve(a, b, lift, -side);
  addTube(c1, color, radius, parent);
  addTube(c2, color, radius, parent);
  addPulse(c1, color, opts.speed ?? 0.0045, false, parent, packetList);
  addPulse(c2, color, opts.speed ?? 0.0045, true, parent, packetList);
}

function addSimplexAt(parent, packetList, from, to, color, opts = {}) {
  const a = opts.raw ? from.clone() : brickFace(from, to, opts.halfA ?? 0.95);
  const b = opts.raw ? to.clone() : brickFace(to, from, opts.halfB ?? 0.95);
  const dir = b.clone().sub(a).normalize();
  parent.add(makeSocket(a, b));
  const curve = cableCurve(a, b, opts.lift ?? 1.05, opts.side ?? 0);
  addTube(curve, color, opts.radius ?? 0.08, parent);
  const tip = b.clone().addScaledVector(dir, -0.18);
  parent.add(makeArrow(tip, dir, color));
  addPulse(curve, color, opts.speed ?? 0.0055, false, parent, packetList);
}

function addDuplexWire(from, to, color) {
  const a = facePoint(from, to);
  const b = facePoint(to, from);
  overview.add(makeSocket(a, b));
  overview.add(makeSocket(b, a));
  const c1 = cableCurve(a, b, 1.85, 0.42);
  const c2 = cableCurve(a, b, 1.85, -0.42);
  addTube(c1, color, 0.075);
  addTube(c2, color, 0.075);
  addPulse(c1, color, 0.0045, false);
  addPulse(c2, color, 0.0045, true);
}

function addSimplexWire(from, to, color, opts = {}) {
  const a = opts.fromAxis ? offsetFace(from, opts.fromAxis) : facePoint(from, to);
  const b = opts.toAxis ? offsetFace(to, opts.toAxis) : facePoint(to, from);
  const dir = b.clone().sub(a).normalize();
  overview.add(makeSocket(a, b));
  const curve = cableCurve(a, b, opts.lift ?? 1.05, opts.side ?? 0);
  addTube(curve, color, 0.09);
  const tip = b.clone().addScaledVector(dir, -0.2);
  overview.add(makeArrow(tip, dir, color));
  addPulse(curve, color, 0.0055, false);
}

function posOf(wrap) {
  return wrap.position.clone();
}

for (const organ of ORGANS) {
  const group = new THREE.Group();
  group.position.set(...organ.pos);
  const visual = makeLegoOrgan(organ);
  visual.name = "visual";
  group.add(visual);
  addHit(group, organ.size[0], organ.size[1] + 1.8, Math.max(organ.size[2], 2.4));
  group.userData = { kind: "organ", organ };
  overview.add(group);
  const label = makeLabel(organ.name);
  label.position.set(organ.pos[0], organ.pos[1] + organ.size[1] / 2 + 2.2, organ.pos[2]);
  overview.add(label);
  organ.mesh = group;
  organ.label = label;
  clickables.push(group);
  gsap.to(visual.position, {
    y: 0.16,
    duration: 2.5 + Math.random() * 0.5,
    yoyo: true,
    repeat: -1,
    ease: "sine.inOut",
    delay: Math.random(),
  });
}

const byId = Object.fromEntries(ORGANS.map((o) => [o.id, o]));
// Demo path only: mailbox → helpdesk intake (not into the inbox pane).
addSimplexWire(byId.mail, byId.helpdesk, 0x3b82f6, {
  lift: 4.6,
  side: 2.4,
  fromAxis: new THREE.Vector3(1, 0.15, 0.35),
  toAxis: new THREE.Vector3(-1, 0.1, 0.2),
});
// Inbox is a client: ask / answer on the same dispatch() path.
addDuplexWire(byId.inbox, byId.helpdesk, 0xf97316);
// Shop reads: Shopify Admin (or fixtures). No Redo. No KB.
addDuplexWire(byId.helpdesk, byId.look, 0xca8a04);
// Human Send lives in the composer. It stops here — local thread only.
addSimplexWire(byId.inbox, byId.send, 0xdc2626, {
  fromAxis: new THREE.Vector3(0, 0, 1),
  toAxis: new THREE.Vector3(0, 0, -1),
  lift: 1.4,
});

const stack = [];
let hovered = null;
let pointerDown = null;

function showWorld() {
  stack.length = 0;
  overview.visible = true;
  detail.visible = false;
  clearDetail();
  flyTo(homeCam.x, homeCam.y, homeCam.z, homeCam.tx, homeCam.ty, homeCam.tz);
  setCard(
    "Whole body",
    "Click an organ to walk inside",
    "Mail goes into helpdesk intake. The inbox only asks and answers. Send stays in the composer — it does not email out.",
    WIRE_LEGEND
  );
  backBtn.disabled = true;
}

function setCard(crumb, title, lede, meta) {
  crumbEl.textContent = crumb;
  titleEl.textContent = title;
  ledeEl.textContent = lede;
  metaEl.innerHTML = meta || "";
}

function flyTo(x, y, z, tx, ty, tz) {
  controls.enabled = false;
  gsap.to(camera.position, { x, y, z, duration: dur(1.15), ease: "power3.inOut" });
  gsap.to(controls.target, {
    x: tx,
    y: ty,
    z: tz,
    duration: dur(1.15),
    ease: "power3.inOut",
    onUpdate: () => controls.update(),
    onComplete: () => {
      controls.enabled = true;
    },
  });
}

function clearDetail() {
  while (detail.children.length) {
    const ch = detail.children[0];
    detail.remove(ch);
  }
  detailPackets.length = 0;
  for (let i = clickables.length - 1; i >= 0; i--) {
    if (clickables[i].userData.kind === "tissue") clickables.splice(i, 1);
  }
}

function roundCanvasRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawInboxWireframe() {
  const W = 1920;
  const H = 1080;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  const ink = "#1C1916";
  const paper = "#FFFDF9";
  const ground = "#F4F0EA";
  const mute = "#5C564F";
  const line = "rgba(28,25,22,0.14)";
  ctx.fillStyle = ground;
  ctx.fillRect(0, 0, W, H);
  const viewW = 274;
  const listW = 411;
  const railW = 411;
  const threadW = W - viewW - listW - railW;
  const xs = [0, viewW, viewW + listW, viewW + listW + threadW];
  const ws = [viewW, listW, threadW, railW];
  const titles = ["View", "List", "Thread + composer", "Rail"];

  for (let i = 0; i < 4; i++) {
    ctx.fillStyle = paper;
    ctx.fillRect(xs[i], 0, ws[i], H);
    ctx.strokeStyle = line;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(xs[i] + 0.5, 0);
    ctx.lineTo(xs[i] + 0.5, H);
    ctx.stroke();
    ctx.fillStyle = mute;
    ctx.font = "600 22px Arial";
    ctx.fillText(titles[i], xs[i] + 22, 42);
  }

  // View list
  const views = ["Assigned to me", "Unassigned", "All", "Snoozed", "Closed"];
  views.forEach((name, i) => {
    const y = 78 + i * 56;
    if (i === 2) {
      ctx.fillStyle = ink;
      ctx.fillRect(xs[0], y - 18, 8, 44);
      ctx.font = "600 26px Arial";
    } else {
      ctx.fillStyle = mute;
      ctx.font = "400 26px Arial";
    }
    ctx.fillText(name, xs[0] + 28, y + 12);
  });

  // Ticket rows
  const rows = [
    ["Ada Demo", "Where is order #1001?"],
    ["Sam", "Broken rattle"],
    ["Priya", "Start a return"],
  ];
  rows.forEach((row, i) => {
    const y = 78 + i * 92;
    if (i === 0) {
      ctx.fillStyle = ink;
      ctx.fillRect(xs[1], y - 8, 8, 72);
    }
    ctx.fillStyle = ink;
    ctx.font = "600 26px Arial";
    ctx.fillText(row[0], xs[1] + 28, y + 18);
    ctx.fillStyle = mute;
    ctx.font = "400 22px Arial";
    ctx.fillText(row[1], xs[1] + 28, y + 48);
    ctx.strokeStyle = line;
    ctx.beginPath();
    ctx.moveTo(xs[1] + 16, y + 72);
    ctx.lineTo(xs[1] + ws[1] - 16, y + 72);
    ctx.stroke();
  });

  // Thread bubbles
  const tx = xs[2] + 28;
  roundCanvasRect(ctx, tx, 78, 420, 88, 12);
  ctx.fillStyle = "#efe8de";
  ctx.fill();
  ctx.fillStyle = ink;
  ctx.font = "400 22px Arial";
  ctx.fillText("Hi — any update on #1001?", tx + 18, 128);
  roundCanvasRect(ctx, tx + 80, 188, 460, 72, 12);
  ctx.fillStyle = "#e8f0e6";
  ctx.fill();
  ctx.fillStyle = mute;
  ctx.font = "400 20px Arial";
  ctx.fillText("Closed · Tuesday", tx + 98, 232);

  // Draft strip
  roundCanvasRect(ctx, tx, 290, threadW - 56, 86, 10);
  ctx.strokeStyle = line;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = mute;
  ctx.font = "600 18px Arial";
  ctx.fillText("Suggested draft  ·  Insert   Discard", tx + 16, 324);
  ctx.font = "400 20px Arial";
  ctx.fillStyle = ink;
  ctx.fillText("Hi Ada — #1001 is still packing.", tx + 16, 356);

  // Composer box
  roundCanvasRect(ctx, tx, 400, threadW - 56, 280, 12);
  ctx.strokeStyle = ink;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = mute;
  ctx.font = "400 18px Arial";
  ctx.fillText("To  Ada Demo", tx + 16, 432);
  ctx.fillStyle = "#d6d3d1";
  ctx.fillRect(tx + 16, 452, threadW - 88, 140);
  ctx.fillStyle = mute;
  ctx.font = "400 20px Arial";
  ctx.fillText("Type a reply…", tx + 28, 490);

  roundCanvasRect(ctx, tx + 16, 612, 140, 48, 6);
  ctx.fillStyle = ink;
  ctx.fill();
  ctx.fillStyle = paper;
  ctx.font = "600 22px Arial";
  ctx.fillText("Send", tx + 56, 644);
  roundCanvasRect(ctx, tx + 170, 612, 180, 48, 6);
  ctx.strokeStyle = ink;
  ctx.stroke();
  ctx.fillStyle = ink;
  ctx.font = "600 20px Arial";
  ctx.fillText("Send & close", tx + 188, 644);

  // Rail cards
  const cards = ["Customer", "This order", "Returns", "Past orders"];
  const peeks = ["Ada Demo", "#1001 · Paid", "No returns", "3 orders"];
  cards.forEach((name, i) => {
    const y = 78 + i * 230;
    roundCanvasRect(ctx, xs[3] + 22, y, railW - 44, 210, 10);
    ctx.strokeStyle = line;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = ink;
    ctx.font = "600 26px Arial";
    ctx.fillText(name, xs[3] + 40, y + 44);
    ctx.fillStyle = mute;
    ctx.font = "400 22px Arial";
    ctx.fillText(peeks[i], xs[3] + 40, y + 84);
  });

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return { tex, xs, ws, W, H };
}

function drawRailWireframe() {
  const W = 900;
  const H = 1080;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#F4F0EA";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#FFFDF9";
  ctx.fillRect(24, 24, W - 48, H - 48);
  ctx.fillStyle = "#5C564F";
  ctx.font = "600 22px Arial";
  ctx.fillText("Rail", 48, 64);
  const cards = [
    ["Customer", "Who wrote in"],
    ["This order", "The order on this ticket"],
    ["Returns", "Open only if THIS ticket has OPEN"],
    ["Past orders", "Peek — does not replace This order"],
  ];
  cards.forEach((row, i) => {
    const y = 100 + i * 230;
    roundCanvasRect(ctx, 48, y, W - 96, 200, 10);
    ctx.strokeStyle = "rgba(28,25,22,0.16)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "#1C1916";
    ctx.font = "600 32px Arial";
    ctx.fillText(row[0], 72, y + 56);
    ctx.fillStyle = "#5C564F";
    ctx.font = "400 24px Arial";
    ctx.fillText(row[1], 72, y + 100);
  });
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function addBillboardFrame(group, w, h) {
  const bezel = new THREE.Mesh(
    new THREE.BoxGeometry(w + 0.28, h + 0.28, 0.16),
    legoMat(0x1c1916)
  );
  bezel.position.z = -0.1;
  group.add(bezel);
  const postL = new THREE.Mesh(new THREE.BoxGeometry(0.18, h * 0.55, 0.18), legoMat(0x44403c));
  postL.position.set(-w * 0.42, -h * 0.28, -0.28);
  group.add(postL);
  const postR = postL.clone();
  postR.position.x = w * 0.42;
  group.add(postR);
  const foot = new THREE.Mesh(new THREE.BoxGeometry(w * 0.7, 0.16, 1.1), legoMat(0x292524));
  foot.position.set(0, -h / 2 - 0.35, 0.1);
  group.add(foot);
}

function tissueByName(organ, name) {
  return organ.tissues.find((t) => t.name === name);
}

function addHub(kind, color, label, position, scale = 0.4) {
  const wrap = new THREE.Group();
  wrap.position.copy(position);
  wrap.add(makeLegoMini(color, kind, scale));
  detail.add(wrap);
  const lab = makeLabel(label, 640, 160, "#1c1916");
  lab.scale.set(2.5, 0.76, 1);
  lab.position.set(position.x, position.y + 1.55, position.z);
  detail.add(lab);
  return wrap;
}

function worldPoint(obj, nudge = new THREE.Vector3()) {
  const p = new THREE.Vector3();
  obj.updateWorldMatrix(true, false);
  obj.getWorldPosition(p);
  return p.add(nudge);
}

function wireInboxStudio(paneHits) {
  const mailbox = addHub("mail", 0xf9a8b4, "Inbox mailbox", new THREE.Vector3(0, 0.95, 4.2), 0.42);
  const hub = mailbox.position.clone();
  hub.y = 1.2;
  const order = ["View", "List", "Thread", "Composer", "Rail"];
  order.forEach((name, i) => {
    const hit = paneHits[name];
    if (!hit) return;
    const pane = worldPoint(hit, new THREE.Vector3(0, 0, 0.85));
    addSpokeAt(detail, detailPackets, pane, hub, 0x78716c, {
      raw: true,
      lift: 0.35 + (i % 2) * 0.2,
      side: (i - 2) * 0.18,
      radius: 0.04,
    });
  });
  const list = paneHits.List && worldPoint(paneHits.List, new THREE.Vector3(0.15, 0.1, 1.05));
  const thread = paneHits.Thread && worldPoint(paneHits.Thread, new THREE.Vector3(-0.1, 0.55, 1.05));
  const composer = paneHits.Composer && worldPoint(paneHits.Composer, new THREE.Vector3(0, 0.25, 1.05));
  const rail = paneHits.Rail && worldPoint(paneHits.Rail, new THREE.Vector3(-0.15, 0.1, 1.05));
  const view = paneHits.View && worldPoint(paneHits.View, new THREE.Vector3(0.15, 0.1, 1.05));
  if (view && list) {
    addSimplexAt(detail, detailPackets, view, list, 0x44403c, {
      raw: true, lift: 2.6, side: 0.7, radius: 0.085,
    });
  }
  if (list && thread) {
    addSimplexAt(detail, detailPackets, list, thread, 0x1c1916, {
      raw: true, lift: 3.15, side: -0.15, radius: 0.09,
    });
  }
  if (list && rail) {
    addSimplexAt(detail, detailPackets, list, rail, 0x0369a1, {
      raw: true, lift: 3.4, side: 0.45, radius: 0.09,
    });
  }
  if (list && composer) {
    addSimplexAt(detail, detailPackets, list, composer, 0x78716c, {
      raw: true, lift: 2.35, side: -0.7, radius: 0.08,
    });
  }
  if (thread && composer) {
    addSimplexAt(detail, detailPackets, thread, composer, 0x57534e, {
      raw: true, lift: 1.85, side: 0.55, radius: 0.08,
    });
    addSimplexAt(detail, detailPackets, composer, thread, 0xdc2626, {
      raw: true, lift: 1.35, side: -0.55, radius: 0.09,
    });
  }
}

function wireRailStudio(cardHits) {
  const shop = addHub("bag", 0xeab308, "Look-only shop", new THREE.Vector3(-4.4, 1.05, 1.6), 0.4);
  const hub = shop.position.clone();
  hub.y = 1.25;
  cardHits.forEach((hit, i) => {
    const pane = worldPoint(hit, new THREE.Vector3(-0.4, 0, 0.4));
    addDuplexAt(detail, detailPackets, pane, hub, 0xca8a04, {
      raw: true,
      lift: 0.8 + i * 0.18,
      side: (i - 1.5) * 0.28,
      radius: 0.05,
    });
  });
}

function wireHelpdesk(wraps) {
  const core = new THREE.Vector3(0, 1.2, 0);
  const names = Object.keys(wraps);
  names.forEach((name, i) => {
    addSpokeAt(detail, detailPackets, posOf(wraps[name]), core, 0xd6d3d1, {
      lift: 0.35,
      side: (i % 2 === 0 ? 0.12 : -0.12),
      radius: 0.038,
      halfA: 0.9,
      halfB: 0.5,
    });
  });
  const pair = (a, b, color, opts) => {
    if (!wraps[a] || !wraps[b]) return;
    addSimplexAt(detail, detailPackets, posOf(wraps[a]), posOf(wraps[b]), color, opts);
  };
  // pull_mailbox calls ingest_email directly (not a second ingest path).
  pair("pull_mailbox", "ingest_email", 0x3b82f6, { lift: 1.6, side: 0.55, radius: 0.085 });
  // After intake, list_tickets / get_ticket read the same first-party ticket store.
  pair("ingest_email", "list_tickets", 0x2563eb, { lift: 2.1, side: -0.7, radius: 0.075 });
  pair("ingest_chat", "list_tickets", 0x2563eb, { lift: 2.4, side: 0.85, radius: 0.075 });
  pair("ingest_email", "get_ticket", 0x1d4ed8, { lift: 2.6, side: 0.4, radius: 0.07 });
  pair("ingest_chat", "get_ticket", 0x1d4ed8, { lift: 2.85, side: -0.5, radius: 0.07 });
  // Composer tools read the thread (tickets.get_ticket) when the client does not pass it.
  pair("get_ticket", "draft_reply", 0x44403c, { lift: 2.35, side: 0.85, radius: 0.08 });
  pair("get_ticket", "summarize_thread", 0x57534e, { lift: 2.65, side: -0.7, radius: 0.08 });
  // Four shop tools share shop.py. They do not call each other.
  const shopHub = addHub("bag", 0xeab308, "shop.py", new THREE.Vector3(0, 1.05, -6.15), 0.38);
  const shopPos = shopHub.position.clone();
  shopPos.y = 1.25;
  ["get_customer", "get_order", "get_returns", "list_past_orders"].forEach((name, i) => {
    if (!wraps[name]) return;
    addDuplexAt(detail, detailPackets, posOf(wraps[name]), shopPos, 0xca8a04, {
      lift: 1.55,
      side: (i - 1.5) * 0.38,
      radius: 0.07,
      halfA: 0.85,
      halfB: 0.5,
    });
  });
  if (wraps.draft_reply) {
    addSimplexAt(detail, detailPackets, posOf(wraps.draft_reply), shopPos, 0xa16207, {
      lift: 3.4,
      side: 1.15,
      radius: 0.09,
    });
  }
}

function mountInboxStudio(organ, crumbPrefix) {
  const { tex, xs, ws, W, H } = drawInboxWireframe();
  const width = 13.6;
  const height = width * (H / W);
  const board = new THREE.Group();
  board.position.set(0, height / 2 + 1.15, -0.6);
  board.rotation.x = -0.06;
  addBillboardFrame(board, width, height);
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(width, height),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.55, metalness: 0.02 })
  );
  screen.position.z = 0.02;
  board.add(screen);
  detail.add(board);
  paint(board);

  const paneHits = {};
  const paneNames = ["View", "List", "Thread", "Rail"];
  const composerSplit = 0.58;
  paneNames.forEach((name, i) => {
    const tissue = name === "Thread" ? tissueByName(organ, "Thread") : tissueByName(organ, name);
    if (!tissue) return;
    const px = xs[i] / W;
    const pw = ws[i] / W;
    const paneW = width * pw;
    const paneH = name === "Thread" ? height * composerSplit : height;
    const hit = new THREE.Mesh(
      new THREE.PlaneGeometry(paneW - 0.08, paneH - 0.08),
      new THREE.MeshStandardMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.0,
        emissive: 0x60a5fa,
        emissiveIntensity: 0,
      })
    );
    const cx = -width / 2 + (px + pw / 2) * width;
    const cy = name === "Thread" ? height / 2 - paneH / 2 : 0;
    hit.position.set(cx, cy, 0.06);
    hit.userData = { kind: "tissue", tissue, organ, pane: name };
    board.add(hit);
    clickables.push(hit);
    paneHits[name] = hit;
  });

  const composer = tissueByName(organ, "Composer");
  if (composer) {
    const pw = ws[2] / W;
    const paneW = width * pw;
    const paneH = height * (1 - composerSplit);
    const hit = new THREE.Mesh(
      new THREE.PlaneGeometry(paneW - 0.08, paneH - 0.08),
      new THREE.MeshStandardMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.0,
        emissive: 0x60a5fa,
        emissiveIntensity: 0,
      })
    );
    const px = xs[2] / W;
    const cx = -width / 2 + (px + pw / 2) * width;
    const cy = -height / 2 + paneH / 2;
    hit.position.set(cx, cy, 0.06);
    hit.userData = { kind: "tissue", tissue: composer, organ, pane: "Composer" };
    board.add(hit);
    clickables.push(hit);
    paneHits.Composer = hit;
  }

  board.updateWorldMatrix(true, true);
  wireInboxStudio(paneHits);

  gsap.from(board.scale, { x: 0.2, y: 0.2, z: 0.2, duration: dur(0.7), ease: "back.out(1.4)" });
  flyTo(0, 7.2, 18.5, 0, 3.1, 1.0);
  setCard(
    crumbPrefix || `Inside · ${organ.name}`,
    "Inbox UI wireframe",
    "Panes drop letters in the mailbox. They do not peek in each other's rooms. Click a pane.",
    "view/selected → list. list/selected → thread, rail, composer. Summarize is thread → composer. Send is composer → local thread."
  );
}

function mountRailStudio(organ, crumbPrefix) {
  const tex = drawRailWireframe();
  const width = 6.4;
  const height = 7.7;
  const board = new THREE.Group();
  board.position.set(0, height / 2 + 1.1, -0.4);
  addBillboardFrame(board, width, height);
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(width, height),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.55, metalness: 0.02 })
  );
  screen.position.z = 0.02;
  board.add(screen);
  detail.add(board);
  paint(board);
  const cardHits = [];
  organ.tissues.forEach((tissue, i) => {
    const paneH = height * 0.2;
    const hit = new THREE.Mesh(
      new THREE.PlaneGeometry(width * 0.82, paneH),
      new THREE.MeshStandardMaterial({
        transparent: true,
        opacity: 0,
        color: 0xffffff,
        emissive: 0x60a5fa,
        emissiveIntensity: 0,
      })
    );
    hit.position.set(0, height * 0.32 - i * (paneH + 0.12), 0.06);
    hit.userData = { kind: "tissue", tissue, organ, pane: tissue.name };
    board.add(hit);
    clickables.push(hit);
    cardHits.push(hit);
  });
  board.updateWorldMatrix(true, true);
  wireRailStudio(cardHits);
  gsap.from(board.scale, { x: 0.2, y: 0.2, z: 0.2, duration: dur(0.6), ease: "back.out(1.4)" });
  flyTo(0, 5.6, 14.2, -1.2, 3.0, 0.2);
  setCard(
    crumbPrefix || `Inside · ${organ.name}`,
    "Rail wireframe",
    "Four cards load at the same time. None of them plug into each other. Past orders does not replace This order.",
    "Each card asks helpdesk (look-only Shopify). If one card breaks, the others stay up."
  );
}

function enterOrgan(organ, crumbPrefix) {
  stack.push(organ);
  overview.visible = false;
  detail.visible = true;
  clearDetail();
  backBtn.disabled = false;

  const wide = organ.id === "inbox" || organ.id === "rail" || organ.id === "helpdesk";
  const radius = organ.id === "helpdesk" ? 12.4 : wide ? 11 : 8.4;
  const platform = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, 0.28, 48),
    stdMat(organ.color, { roughness: 0.6, emissiveIntensity: 0.08 })
  );
  platform.position.y = 0.14;
  platform.receiveShadow = true;
  detail.add(platform);

  if (organ.id === "inbox") {
    mountInboxStudio(organ, crumbPrefix);
    return;
  }
  if (organ.id === "rail") {
    mountRailStudio(organ, crumbPrefix);
    return;
  }

  const tissues = organ.tissues;
  const n = tissues.length;
  const wraps = {};
  tissues.forEach((t, i) => {
    const slot = organ.id === "helpdesk" ? HELPDESK_LAYOUT[t.name] : null;
    const wrap = new THREE.Group();
    if (slot) wrap.position.set(...slot);
    else {
      const ang = (i / n) * Math.PI * 2 - Math.PI / 2;
      const r = n > 8 ? 6.2 : 5.4;
      wrap.position.set(Math.cos(ang) * r, 1.05, Math.sin(ang) * r);
    }
    const visual = makeLegoMini(t.nested ? 0x7dd3fc : organ.color, t.shape || organ.form, 0.4);
    wrap.add(visual);
    addHit(wrap, 2.2, 2.4, 2.2);
    wrap.userData = { kind: "tissue", tissue: t, organ };
    detail.add(wrap);
    clickables.push(wrap);
    wraps[t.name] = wrap;
    const lab = makeLabel(t.name, 640, 160, t.nested ? "#075985" : "#9a3412");
    lab.scale.set(2.7, 0.82, 1);
    lab.position.set(wrap.position.x, 2.65, wrap.position.z);
    detail.add(lab);
    gsap.from(wrap.scale, {
      x: 0.01,
      y: 0.01,
      z: 0.01,
      duration: dur(0.5),
      delay: dur(0.04 * i),
      ease: "back.out(1.6)",
    });
  });

  const core = makeLegoMini(organ.color, organ.form || "cluster", 0.38);
  core.position.set(0, 0.95, 0);
  core.userData = { kind: "organCore", organ };
  detail.add(core);

  if (organ.id === "helpdesk") {
    const lab = makeLabel("dispatch()", 640, 160, "#9a3412");
    lab.scale.set(2.8, 0.84, 1);
    lab.position.set(0, 2.55, 0);
    detail.add(lab);
    wireHelpdesk(wraps);
    flyTo(0, 16.2, 22.5, 0, 0.5, -1.1);
    setCard(
      crumbPrefix || `Inside · ${organ.name}`,
      organ.name,
      "Every tool plugs into dispatch() — MCP, CLI, and the inbox HTTP door share that room.",
      "Blue arrow: pull_mailbox calls ingest_email, then tickets show in list_tickets. Gold: shop.py is the shared look-only Shopify door. Search and apply macros stay on dispatch only."
    );
    return;
  }

  flyTo(0, 11.5, 16.5, 0, 0.8, 0);
  setCard(
    crumbPrefix || `Inside · ${organ.name}`,
    organ.name,
    organ.kid,
    organ.id === "send"
      ? "Insert/Discard fills the box. Send writes the local thread. They do not plug into each other, and neither emails the customer."
      : "Each tissue is a little LEGO brick. The sign on top is its one job."
  );
}

function selectTissue(tissue, organ) {
  if (tissue.nested) {
    enterOrgan(RAIL, `Inside · ${organ.name} · Rail`);
    return;
  }
  setCard(
    `Tissue · ${organ.name}`,
    tissue.name,
    tissue.kid,
    `<div><strong>In</strong> <code>${escapeHtml(tissue.inn)}</code></div>
     <div style="margin-top:6px"><strong>Out</strong> <code>${escapeHtml(tissue.out)}</code></div>
     <div style="margin-top:8px">Black box: stuff goes in, something comes out. You do not peek inside.</div>`
  );
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

backBtn.addEventListener("click", () => {
  if (stack.length <= 1) showWorld();
  else {
    stack.pop();
    const prev = stack.pop();
    enterOrgan(prev);
  }
});
resetBtn.addEventListener("click", () => showWorld());
const infoCard = document.getElementById("info-card");
const infoBtn = document.getElementById("btn-info");
infoBtn.addEventListener("click", () => {
  const off = infoCard.classList.toggle("is-off");
  infoBtn.setAttribute("aria-pressed", off ? "false" : "true");
  infoBtn.classList.toggle("is-on", !off);
});

const ray = new THREE.Raycaster();
const pointer = new THREE.Vector2();
function ndc(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
}

function rootOf(obj) {
  let o = obj;
  while (o) {
    if (o.userData?.kind === "organ" || o.userData?.kind === "tissue") return o;
    o = o.parent;
  }
  return null;
}

function hits(ev) {
  ndc(ev);
  ray.setFromCamera(pointer, camera);
  const visible = clickables.filter((m) => {
    let o = m;
    while (o) {
      if (!o.visible) return false;
      o = o.parent;
    }
    return true;
  });
  return ray.intersectObjects(visible, true);
}

function setEmissive(root, value) {
  if (!root) return;
  root.traverse((o) => {
    if (o.isMesh && o.material && "emissiveIntensity" in o.material && o.material.visible !== false) {
      o.material.emissiveIntensity = value;
    }
  });
}

renderer.domElement.addEventListener("pointerdown", (ev) => {
  pointerDown = { x: ev.clientX, y: ev.clientY };
});
renderer.domElement.addEventListener("pointermove", (ev) => {
  const obj = rootOf(hits(ev)[0]?.object);
  if (hovered && hovered !== obj) setEmissive(hovered, 0.12);
  hovered = obj;
  if (hovered) setEmissive(hovered, 0.4);
  renderer.domElement.style.cursor = hovered ? "pointer" : "grab";
});
renderer.domElement.addEventListener("pointerup", (ev) => {
  if (!pointerDown) return;
  const dx = ev.clientX - pointerDown.x;
  const dy = ev.clientY - pointerDown.y;
  pointerDown = null;
  if (dx * dx + dy * dy > 16) return;
  const obj = rootOf(hits(ev)[0]?.object);
  if (!obj) return;
  const { kind, organ, tissue } = obj.userData;
  if (kind === "organ") enterOrgan(organ);
  else if (kind === "tissue") selectTissue(tissue, organ);
});

function resize() {
  const w = host.clientWidth || window.innerWidth;
  const h = host.clientHeight || window.innerHeight;
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
window.addEventListener("resize", resize);
resize();

function tick() {
  controls.update();
  const moving = overview.visible ? overviewPackets : detailPackets;
  for (const p of moving) {
    p.t = (p.t + p.speed) % 1;
    const u = p.reverse ? 1 - p.t : p.t;
    p.ball.position.copy(p.curve.getPointAt(u));
  }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
showWorld();
const bootInside = new URLSearchParams(location.search).get("inside");
if (bootInside === "rail") enterOrgan(RAIL);
else if (bootInside) {
  const organ = ORGANS.find((o) => o.id === bootInside);
  if (organ) enterOrgan(organ);
}
window.__bb = { enterOrgan, showWorld, ORGANS, RAIL, camera, controls };
