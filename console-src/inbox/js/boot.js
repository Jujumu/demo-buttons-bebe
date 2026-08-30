import { createInboxOrgan } from "./inbox.js";

const root = document.getElementById("inbox-root");
const organ = createInboxOrgan();
organ.mount(root);
