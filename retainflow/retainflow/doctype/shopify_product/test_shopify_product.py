# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retainflow.retainflow.doctype.shopify_settings.shopify_settings import ShopifySettings
from retainflow.shopify_api import sync_products, sync_single_product


class IntegrationTestShopifyProduct(IntegrationTestCase):
	PRODUCT_PAYLOAD: ClassVar[dict] = {
		"id": 9000000001,
		"title": "Test Product",
		"handle": "test-product",
		"status": "active",
		"vendor": "Test Vendor",
		"product_type": "Test Type",
		"tags": "test, sample",
		"created_at": "2026-10-13T10:00:00-05:00",
		"published_at": "2026-10-13T10:00:00-05:00",
		"updated_at": "2026-10-13T11:00:00-05:00",
		"image": {"src": "https://cdn.shopify.com/test-product.jpg"},
		"variants": [
			{
				"id": 9000000002,
				"title": "Blue / M",
				"sku": "TP-BLU-M",
				"price": "19.99",
				"compare_at_price": "24.99",
				"inventory_quantity": 12,
				"barcode": "1234567890",
				"option1": "Blue",
				"option2": "M",
			},
			{
				"id": 9000000003,
				"title": "Blue / L",
				"sku": "TP-BLU-L",
				"price": "19.99",
				"inventory_quantity": 8,
				"option1": "Blue",
				"option2": "L",
			},
		],
	}

	def tearDown(self):
		frappe.db.delete("Shopify Product Variant", {"parenttype": "Shopify Product"})
		frappe.db.delete("Shopify Product", {"shopify_product_id": str(self.PRODUCT_PAYLOAD["id"])})
		frappe.db.delete("Shopify Sync Log", {"sync_type": "Products"})
		frappe.db.commit()

	def test_sync_products_creates_log(self):
		with (
			patch("retainflow.shopify_api.fetch_shopify_products", return_value=[self.PRODUCT_PAYLOAD]),
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
			result = sync_products(limit=10)

		self.assertEqual(result["status"], "success")
		self.assertEqual(result["synced_count"], 1)

		logs = frappe.get_all(
			"Shopify Sync Log",
			filters={"sync_type": "Products", "status": "Success"},
			fields=["synced_count", "total_records", "sync_limit"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].synced_count, 1)
		self.assertEqual(logs[0].sync_limit, 10)

	def test_sync_single_product_upsert(self):
		product_id = sync_single_product(self.PRODUCT_PAYLOAD, "test-store.myshopify.com")
		self.assertEqual(product_id, str(self.PRODUCT_PAYLOAD["id"]))

		doc = frappe.get_doc("Shopify Product", product_id)
		self.assertEqual(doc.product_title, "Test Product")
		self.assertEqual(doc.status, "active")
		self.assertEqual(doc.featured_image, "https://cdn.shopify.com/test-product.jpg")
		self.assertEqual(doc.inventory_stock_qty, 20)  # 12 + 8 across variants
		self.assertEqual(len(doc.variants), 2)
		self.assertEqual(doc.variants[0].sku, "TP-BLU-M")
		self.assertEqual(doc.variants[0].inventory_quantity, 12)

		# Upsert: sync again with a changed title, no duplicate should be created
		updated = dict(self.PRODUCT_PAYLOAD)
		updated["title"] = "Test Product (Updated)"
		sync_single_product(updated, "test-store.myshopify.com")

		self.assertEqual(frappe.db.count("Shopify Product", {"shopify_product_id": product_id}), 1)
		doc = frappe.get_doc("Shopify Product", product_id)
		self.assertEqual(doc.product_title, "Test Product (Updated)")
