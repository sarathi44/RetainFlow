# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

from unittest.mock import patch, MagicMock
import frappe
from frappe.tests import IntegrationTestCase
from retainflow.shopify_api import clean_shopify_url, test_shopify_connection


class IntegrationTestShopifySettings(IntegrationTestCase):
	def test_clean_shopify_url(self):
		self.assertEqual(clean_shopify_url("https://my-store.myshopify.com/"), "my-store.myshopify.com")
		self.assertEqual(clean_shopify_url("http://my-store.myshopify.com"), "my-store.myshopify.com")
		self.assertEqual(clean_shopify_url("  my-store.myshopify.com  "), "my-store.myshopify.com")

	@patch("requests.get")
	def test_connection_success(self, mock_get):
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

		settings = frappe.get_single("Shopify Settings")
		settings.shopify_url = "test-store.myshopify.com"
		settings.access_token = "shpat_test12345"
		settings.api_version = "2024-10"

		result = settings.test_connection()

		self.assertEqual(result["status"], "success")
		self.assertEqual(settings.shop_name, "Test Store")
		self.assertEqual(settings.connection_status, "Connected")
		self.assertEqual(settings.currency, "USD")
