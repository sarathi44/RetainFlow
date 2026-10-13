# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from retainflow.shopify_api import sync_single_order


class IntegrationTestShopifyOrder(IntegrationTestCase):
	def setUp(self):
		if frappe.db.exists("Shopify Order", "999888777"):
			frappe.delete_doc("Shopify Order", "999888777", force=True)

	def tearDown(self):
		if frappe.db.exists("Shopify Order", "999888777"):
			frappe.delete_doc("Shopify Order", "999888777", force=True)

	def test_order_creation_and_totals(self):
		order = frappe.get_doc(
			{
				"doctype": "Shopify Order",
				"shopify_order_id": "999888777",
				"shopify_order_name": "#9999",
				"financial_status": "paid",
				"fulfillment_status": "fulfilled",
				"total_tax": 5.0,
				"total_shipping": 10.0,
				"items": [
					{
						"title": "Widget A",
						"quantity": 2,
						"price": 25.0,
						"total_discount": 0.0,
					},
					{
						"title": "Widget B",
						"quantity": 1,
						"price": 50.0,
						"total_discount": 10.0,
					},
				],
			}
		)
		order.insert(ignore_permissions=True)

		self.assertEqual(order.name, "999888777")
		self.assertEqual(order.subtotal_price, 90.0)  # (2*25) + (1*50 - 10)
		self.assertEqual(order.total_price, 105.0)  # 90 + 5 + 10

	def test_sync_single_order(self):
		raw_order_data = {
			"id": 999888777,
			"name": "#1042",
			"created_at": "2026-10-12T10:00:00Z",
			"financial_status": "paid",
			"fulfillment_status": "unfulfilled",
			"current_subtotal_price": "100.00",
			"total_tax": "10.00",
			"total_discounts": "0.00",
			"current_total_price": "110.00",
			"currency": "USD",
			"email": "customer@example.com",
			"customer": {
				"first_name": "Jane",
				"last_name": "Doe",
				"email": "customer@example.com",
			},
			"shipping_address": {
				"name": "Jane Doe",
				"address1": "123 Main St",
				"city": "Boston",
				"province": "MA",
				"zip": "02108",
				"country": "United States",
			},
			"line_items": [
				{
					"id": 112233,
					"title": "Premium T-Shirt",
					"variant_title": "Blue / L",
					"quantity": 2,
					"price": "50.00",
					"sku": "TSHIRT-BLU-L",
					"product_id": 556677,
					"variant_id": 889900,
				}
			],
		}

		order_id = sync_single_order(raw_order_data, "test-store.myshopify.com")
		self.assertEqual(order_id, "999888777")

		doc = frappe.get_doc("Shopify Order", order_id)
		self.assertEqual(doc.shopify_order_name, "#1042")
		self.assertEqual(doc.customer_name, "Jane Doe")
		self.assertEqual(doc.financial_status, "paid")
		self.assertEqual(doc.fulfillment_status, "unfulfilled")
		self.assertEqual(len(doc.items), 1)
		self.assertEqual(doc.items[0].sku, "TSHIRT-BLU-L")
		self.assertEqual(doc.items[0].amount, 100.0)
