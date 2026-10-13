# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from retainflow.retainflow.doctype.shopify_settings.shopify_settings import ShopifySettings
from retainflow.shopify_api import clean_shopify_url


class IntegrationTestShopifySettings(IntegrationTestCase):
	def test_clean_shopify_url(self):
		self.assertEqual(clean_shopify_url("https://my-store.myshopify.com/"), "my-store.myshopify.com")
		self.assertEqual(clean_shopify_url("http://my-store.myshopify.com"), "my-store.myshopify.com")
		self.assertEqual(clean_shopify_url("  my-store.myshopify.com  "), "my-store.myshopify.com")

	@patch("requests.get")
	@patch("retainflow.shopify_api.get_access_token")
	def test_connection_success(self, mock_token, mock_get):
		mock_token.return_value = "mock_access_token"
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {
			"shop": {
				"name": "Test Store",
				"email": "owner@teststore.com",
				"currency": "USD",
				"iana_timezone": "America/New_York",
				"myshopify_domain": "test-store.myshopify.com",
			}
		}
		mock_get.return_value = mock_response

		# Snapshot the live single so we can prove the test never touched it
		live_before = {
			field: frappe.db.get_single_value("Shopify Settings", field)
			for field in ("shopify_url", "client_id", "connection_status", "shop_name")
		}

		# Use an unsaved document and stub save(): the live Shopify Settings
		# (which holds the real credentials) must never be modified by tests
		settings = frappe.new_doc("Shopify Settings")
		settings.shopify_url = "test-store.myshopify.com"
		settings.client_id = "test_client_id"
		settings.client_secret = "test_client_secret"

		with patch.object(ShopifySettings, "save"):
			result = settings.test_connection()

		self.assertEqual(result["status"], "success")
		self.assertEqual(settings.shop_name, "Test Store")
		self.assertEqual(settings.connection_status, "Connected")
		self.assertEqual(settings.currency, "USD")

		# Live settings untouched
		live_after = {
			field: frappe.db.get_single_value("Shopify Settings", field)
			for field in ("shopify_url", "client_id", "connection_status", "shop_name")
		}
		self.assertEqual(live_before, live_after)
