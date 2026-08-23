from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection

from fake_whatsapp import DemoWhatsAppState, create_server, load_fixture


class FakeWhatsAppTests(unittest.TestCase):
    def setUp(self):
        self.state = DemoWhatsAppState(send_secret="local-test-secret", base_path="/connect-whatsapp/demo")
        self.server = create_server(host="127.0.0.1", port=0, state=self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, auth=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if auth:
            headers["Authorization"] = auth
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_fixture_is_connected_and_synthetic(self):
        data = load_fixture()
        self.assertEqual(data["identity"]["state"], "connected")
        self.assertTrue(all(message["synthetic"] for message in data["inbound"]))

    def test_status_and_fixture_inbox_are_local_simulation(self):
        status, payload = self.request("GET", "/wa/status")
        self.assertEqual(status, 200)
        self.assertTrue(payload["simulated"])
        status, payload = self.request("GET", "/wa/inbox")
        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 3)

    def test_outbound_requires_bearer_and_is_captured_not_delivered(self):
        status, _ = self.request("POST", "/connect-whatsapp/demo/send", {"text": "alert"})
        self.assertEqual(status, 401)
        status, payload = self.request(
            "POST", "/connect-whatsapp/demo/send", {"text": "[PRIORITY ALERT] #1001"},
            auth="Bearer local-test-secret",
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["simulated"])
        self.assertFalse(payload["delivered"])
        self.assertEqual(self.state.outbox[0]["text"], "[PRIORITY ALERT] #1001")

    def test_inbound_simulation_is_marked_synthetic(self):
        status, payload = self.request("POST", "/simulate/inbound", {"text": "hello demo"})
        self.assertEqual(status, 201)
        self.assertTrue(payload["synthetic"])
        self.assertEqual(self.state.inbox[-1]["text"], "hello demo")


if __name__ == "__main__":
    unittest.main()
