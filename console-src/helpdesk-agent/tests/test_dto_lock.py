from __future__ import annotations

import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.dispatch import dispatch
from helpdesk.dto import billing_label, clerk_returns, tracking_label
from helpdesk.fixtures_live_holes import C_MULTI, O_1001, O_1002
from helpdesk.fixtures_sample import ADA, CASEY, ORDER_ADA, ORDER_CASEY_B
from helpdesk.names import LIVE_HOLE_SHOP, SAMPLE_SHOP


class _ForceLiveHoles(unittest.TestCase):
    def setUp(self) -> None:
        self._previous = os.environ.get("HELPDESK_SOURCE")
        os.environ["HELPDESK_SOURCE"] = "live-holes"

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop("HELPDESK_SOURCE", None)
        else:
            os.environ["HELPDESK_SOURCE"] = self._previous


class DtoLockTests(_ForceLiveHoles):
    def test_number_of_orders_is_string(self) -> None:
        customer = dispatch(
            "helpdesk.get_customer", {"shop": SAMPLE_SHOP, "customerId": ADA}
        )["customer"]
        self.assertIsInstance(customer["numberOfOrders"], str)
        self.assertEqual(customer["numberOfOrders"], "1")
        self.assertEqual(customer["defaultEmailAddress"]["emailAddress"], "ada@demo-helpdesk.example")
        self.assertNotIn("email", customer)

    def test_current_total_is_money_bag(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})["order"]
        bag = order["currentTotalPriceSet"]
        self.assertIn("shopMoney", bag)
        self.assertIn("presentmentMoney", bag)
        self.assertEqual(set(bag["shopMoney"]), {"amount", "currencyCode"})
        self.assertIsInstance(bag["shopMoney"]["amount"], str)

    def test_line_price_is_original_unit_price_set(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})["order"]
        line = order["lineItems"]["nodes"][0]
        self.assertIn("originalUnitPriceSet", line)
        self.assertIn("shopMoney", line["originalUnitPriceSet"])
        self.assertNotIn("price", line)

    def test_null_sku_omitted(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})["order"]
        line = order["lineItems"]["nodes"][0]
        self.assertNotIn("sku", line)
        self.assertNotIn("null", str(line).lower())

    def test_line_item_image_url(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})["order"]
        line = order["lineItems"]["nodes"][0]
        self.assertIn("image", line)
        self.assertTrue(str(line["image"]["url"]).startswith("https://"))
        hole = dispatch("helpdesk.get_order", {"shop": LIVE_HOLE_SHOP, "orderId": O_1002})["order"]
        hole_line = hole["lineItems"]["nodes"][0]
        self.assertIn("url", hole_line["image"])
        self.assertTrue(str(hole_line["image"]["url"]).startswith("https://"))

    def test_missing_billing_is_no_billing(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})["order"]
        self.assertIsNone(order["billingAddress"])
        self.assertEqual(billing_label(order["billingAddress"]), "No billing")

    def test_live_holes_match_clerk_lock(self) -> None:
        order = dispatch("helpdesk.get_order", {"shop": LIVE_HOLE_SHOP, "orderId": O_1001})["order"]
        self.assertEqual(order["displayFinancialStatus"], "PAID")
        self.assertEqual(order["displayFulfillmentStatus"], "UNFULFILLED")
        self.assertIsNone(order["billingAddress"])
        self.assertEqual(order["fulfillments"], [])
        self.assertEqual(tracking_label(order["fulfillments"]), "No tracking")
        self.assertNotIn("sku", order["lineItems"]["nodes"][0])
        self.assertEqual(order["lineItems"]["nodes"][0]["unfulfilledQuantity"], 1)
        tracked = dispatch("helpdesk.get_order", {"shop": LIVE_HOLE_SHOP, "orderId": O_1002})["order"]
        info = tracked["fulfillments"][0]["trackingInfo"][0]
        self.assertEqual(tracking_label(tracked["fulfillments"]), "Has tracking")
        self.assertEqual(info["number"], "AI-DEMO-1002")
        self.assertEqual(info["url"], "https://example.com/ai-demo/1002")
        self.assertEqual(info["company"], "Demo Carrier")
        self.assertNotIn("sku", tracked["lineItems"]["nodes"][0])
        self.assertEqual(tracked["lineItems"]["nodes"][0]["unfulfilledQuantity"], 0)
        self.assertEqual(tracked["fulfillments"][0]["displayStatus"], "IN_TRANSIT")

    def test_partial_ship_exposes_unfulfilled_quantity(self) -> None:
        from helpdesk.fixtures_sample import ORDER_PARTIAL, SKY

        order = dispatch("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_PARTIAL})["order"]
        self.assertEqual(order["displayFulfillmentStatus"], "PARTIALLY_FULFILLED")
        lines = order["lineItems"]["nodes"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["unfulfilledQuantity"], 0)
        self.assertEqual(lines[1]["unfulfilledQuantity"], 1)
        self.assertEqual(lines[0]["title"], "Muslin Swaddle")
        self.assertEqual(lines[1]["title"], "Knit Baby Booties")
        self.assertEqual(tracking_label(order["fulfillments"]), "Has tracking")
        self.assertEqual(order["fulfillments"][0]["displayStatus"], "IN_TRANSIT")
        shipped = order["fulfillments"][0]["fulfillmentLineItems"]["nodes"][0]
        self.assertEqual(shipped["lineItem"]["title"], "Muslin Swaddle")
        self.assertEqual(shipped["quantity"], 1)
        customer = dispatch("helpdesk.get_customer", {"shop": SAMPLE_SHOP, "customerId": SKY})["customer"]
        self.assertEqual(customer["displayName"], "Sky Jensen")

        hole = dispatch("helpdesk.get_order", {"shop": LIVE_HOLE_SHOP, "orderId": ORDER_PARTIAL})["order"]
        self.assertEqual(hole["displayFulfillmentStatus"], "PARTIALLY_FULFILLED")
        self.assertEqual(hole["lineItems"]["nodes"][0]["unfulfilledQuantity"], 0)
        self.assertEqual(hole["lineItems"]["nodes"][1]["unfulfilledQuantity"], 1)

    def test_past_orders_newest_first_money_bag_shop_money(self) -> None:
        rows = dispatch(
            "helpdesk.list_past_orders", {"shop": SAMPLE_SHOP, "customerId": CASEY}
        )["orders"]
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual([row["name"] for row in rows], ["#9003", "#9002"])
        self.assertIn("shopMoney", rows[0]["currentTotalPriceSet"])
        self.assertIn("displayFulfillmentStatus", rows[0])
        self.assertNotIn("total", rows[0])
        self.assertNotIn("fulfillmentStatus", rows[0])
        multi = dispatch(
            "helpdesk.list_past_orders", {"shop": LIVE_HOLE_SHOP, "customerId": C_MULTI}
        )["orders"]
        self.assertEqual([row["name"] for row in multi], ["#1004", "#1003"])

    def test_empty_order_does_not_use_ada_open_return(self) -> None:
        payload = dispatch(
            "helpdesk.get_returns", {"shop": SAMPLE_SHOP, "orderId": ORDER_CASEY_B}
        )
        self.assertEqual(payload["returns"]["nodes"], [])
        self.assertFalse(payload["inProgress"])


class ReturnEnumTests(_ForceLiveHoles):
    def test_open_is_return_status_not_order_return_status(self) -> None:
        payload = dispatch(
            "helpdesk.get_returns", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA}
        )
        self.assertTrue(payload["inProgress"])
        self.assertEqual(payload["returns"]["nodes"][0]["status"], "OPEN")
        self.assertEqual(payload["orderReturnStatus"], "IN_PROGRESS")
        self.assertNotEqual(payload["orderReturnStatus"], "OPEN")

    def test_order_return_status_in_progress_alone_is_not_open(self) -> None:
        mapped = clerk_returns({"returnStatus": "IN_PROGRESS", "returns": {"nodes": []}})
        self.assertEqual(mapped["orderReturnStatus"], "IN_PROGRESS")
        self.assertEqual(mapped["returns"]["nodes"], [])
        self.assertFalse(mapped["inProgress"])

    def test_live_returns_empty(self) -> None:
        payload = dispatch(
            "helpdesk.get_returns", {"shop": LIVE_HOLE_SHOP, "orderId": O_1001}
        )
        self.assertEqual(payload["orderReturnStatus"], "NO_RETURN")
        self.assertEqual(payload["returns"]["nodes"], [])
        self.assertFalse(payload["inProgress"])


if __name__ == "__main__":
    unittest.main()
