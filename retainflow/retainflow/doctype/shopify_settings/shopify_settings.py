# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from retainflow.shopify_api import clean_shopify_url, test_shopify_connection, sync_orders


class ShopifySettings(Document):
	def validate(self):
		if self.shopify_url:
			self.shopify_url = clean_shopify_url(self.shopify_url)

	@frappe.whitelist()
	def test_connection(self):
		"""
		Tests connection to Shopify API using current or passed credentials.
		"""
		token = None
		try:
			token = self.get_password("access_token")
		except Exception:
			pass
		if not token:
			token = self.access_token

		if not self.shopify_url or not token:
			frappe.throw("Please provide both Shopify Store URL and Admin API Access Token.")

		api_version = self.api_version or "2024-10"

		try:
			shop_info = test_shopify_connection(
				shop_url=self.shopify_url,
				access_token=token,
				api_version=api_version,
			)

			self.shop_name = shop_info.get("shop_name")
			self.shop_email = shop_info.get("shop_email")
			self.currency = shop_info.get("currency")
			self.timezone = shop_info.get("timezone")
			self.myshopify_domain = shop_info.get("myshopify_domain")
			self.connection_status = "Connected"
			self.save(ignore_permissions=True)
			frappe.db.commit()

			return {
				"status": "success",
				"message": f"Successfully connected to Shopify store '{self.shop_name}'!",
				"shop": shop_info,
			}
		except Exception as e:
			self.connection_status = "Error"
			self.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.throw(f"Connection test failed: {str(e)}")

	@frappe.whitelist()
	def sync_orders_now(self):
		"""
		Triggers order synchronization from Shopify.
		"""
		limit = self.order_sync_limit or 50
		return sync_orders(limit=limit)
