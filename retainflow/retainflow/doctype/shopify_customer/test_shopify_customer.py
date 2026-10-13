# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retainflow.retainflow.doctype.shopify_settings.shopify_settings import ShopifySettings
from retainflow.shopify_api import sync_customers, sync_single_customer


class IntegrationTestShopifyCustomer(IntegrationTestCase):
	CUSTOMER_PAYLOAD: ClassVar[dict] = {
		"id": 9000000003,
		"first_name": "John",
		"last_name": "Doe",
		"email": "john.doe@example.com",
		"phone": "+1 555 0100",
		"state": "enabled",
		"verified_email": True,
		"accepts_marketing": False,
		"tags": "vip, wholesale",
		"orders_count": 5,
		"total_spent": "250.50",
		"currency": "USD",
		"note": "Repeat customer",
		"created_at": "2026-10-13T10:00:00-05:00",
		"updated_at": "2026-10-13T11:00:00-05:00",
		"default_address": {
			"id": 9000000004,
			"name": "John Doe",
			"address1": "123 Main St",
			"city": "Austin",
			"province": "Texas",
			"zip": "78701",
			"country": "United States",
			"phone": "+1 555 0100",
		},
		"addresses": [
			{
				"id": 9000000004,
				"name": "John Doe",
				"address1": "123 Main St",
				"address2": "Apt 4B",
				"city": "Austin",
				"province": "Texas",
				"zip": "78701",
				"country": "United States",
				"phone": "+1 555 0100",
			}
		],
	}

	def tearDown(self):
		frappe.db.delete("Shopify Customer Address", {"parenttype": "Shopify Customer"})
		frappe.db.delete("Shopify Customer", {"shopify_customer_id": str(self.CUSTOMER_PAYLOAD["id"])})
		frappe.db.delete("Shopify Sync Log", {"sync_type": "Customers"})
		frappe.db.commit()

	def test_sync_customers_creates_log(self):
		with (
			patch("retainflow.shopify_api.fetch_shopify_customers", return_value=[self.CUSTOMER_PAYLOAD]),
			patch(
				"retainflow.shopify_api.get_configured_credentials",
				return_value=("test-store.myshopify.com", "test_client_id", "test_secret"),
			),
			patch.object(
				# Never write tracking fields into the live Shopify Settings single
				ShopifySettings,
				"db_set",
			),
		):
			result = sync_customers(limit=10)

		self.assertEqual(result["status"], "success")
		self.assertEqual(result["synced_count"], 1)

		logs = frappe.get_all(
			"Shopify Sync Log",
			filters={"sync_type": "Customers", "status": "Success"},
			fields=["synced_count", "total_records", "sync_limit"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].synced_count, 1)
		self.assertEqual(logs[0].sync_limit, 10)

	def test_sync_single_customer_upsert(self):
		customer_id = sync_single_customer(self.CUSTOMER_PAYLOAD, "test-store.myshopify.com")
		self.assertEqual(customer_id, str(self.CUSTOMER_PAYLOAD["id"]))

		doc = frappe.get_doc("Shopify Customer", customer_id)
		self.assertEqual(doc.customer_name, "John Doe")
		self.assertEqual(doc.email, "john.doe@example.com")
		self.assertEqual(doc.state, "enabled")
		self.assertEqual(doc.verified_email, 1)
		self.assertEqual(doc.orders_count, 5)
		self.assertEqual(doc.total_spent, 250.50)
		self.assertEqual(len(doc.addresses), 1)
		self.assertEqual(doc.addresses[0].address1, "123 Main St")
		self.assertEqual(doc.addresses[0].is_default, 1)

		# Upsert: sync again with a changed name, no duplicate should be created
		updated = dict(self.CUSTOMER_PAYLOAD)
		updated["first_name"] = "Jonathan"
		sync_single_customer(updated, "test-store.myshopify.com")

		self.assertEqual(frappe.db.count("Shopify Customer", {"shopify_customer_id": customer_id}), 1)
		doc = frappe.get_doc("Shopify Customer", customer_id)
		self.assertEqual(doc.customer_name, "Jonathan Doe")

	def test_sync_single_customer_fallback_name(self):
		anonymous = dict(self.CUSTOMER_PAYLOAD)
		anonymous["id"] = 9000000005
		anonymous["first_name"] = None
		anonymous["last_name"] = None
		try:
			customer_id = sync_single_customer(anonymous, "test-store.myshopify.com")
			doc = frappe.get_doc("Shopify Customer", customer_id)
			self.assertEqual(doc.customer_name, "john.doe@example.com")
		finally:
			frappe.db.delete(
				"Shopify Customer Address", {"parenttype": "Shopify Customer", "parent": customer_id}
			)
			frappe.db.delete("Shopify Customer", customer_id)
			frappe.db.commit()
