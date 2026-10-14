# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from retainflow.shopify_api import (
	clean_shopify_url,
	sync_customers,
	sync_orders,
	sync_products,
	test_shopify_connection,
)

DASHBOARD_DOCS = {
	"Dashboard Chart": ["Shopify Orders Trend"],
	"Number Card": [
		"Shopify Total Orders",
		"Shopify Total Revenue",
		"Shopify Pending Orders",
		"Shopify Fulfilled Orders",
	],
}


def update_dashboard_currency(currency):
	"""Keep dashboard chart and number cards on the workspace in the shop's currency."""
	if not currency:
		return
	for doctype, names in DASHBOARD_DOCS.items():
		for name in names:
			if frappe.db.exists(doctype, name):
				frappe.db.set_value(doctype, name, "currency", currency, update_modified=False)


class ShopifySettings(Document):
	def validate(self):
		if self.shopify_url:
			self.shopify_url = clean_shopify_url(self.shopify_url)

	@frappe.whitelist()
	def test_connection(self):
		"""
		Tests connection to Shopify API using current or passed client credentials.
		"""
		client_secret = None
		try:
			client_secret = self.get_password("client_secret")
		except Exception:
			pass
		if not client_secret:
			client_secret = self.client_secret

		if not self.shopify_url or not self.client_id or not client_secret:
			frappe.throw("Please provide Shopify Store URL, Client ID and Client API Secret.")

		try:
			shop_info = test_shopify_connection(
				shop_url=self.shopify_url,
				client_id=self.client_id,
				client_secret=client_secret,
			)

			self.shop_name = shop_info.get("shop_name")
			self.shop_email = shop_info.get("shop_email")
			self.currency = shop_info.get("currency")
			self.timezone = shop_info.get("timezone")
			self.myshopify_domain = shop_info.get("myshopify_domain")
			self.connection_status = "Connected"
			self.save(ignore_permissions=True)
			update_dashboard_currency(self.currency)
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
			frappe.throw(f"Connection test failed: {e!s}")

	@frappe.whitelist()
	def sync_orders_now(self):
		"""
		Triggers order synchronization from Shopify.
		"""
		limit = self.order_sync_limit or 50
		return sync_orders(limit=limit)

	@frappe.whitelist()
	def sync_products_now(self):
		"""
		Triggers product synchronization from Shopify.
		"""
		return sync_products(limit=50)

	@frappe.whitelist()
	def sync_customers_now(self):
		"""
		Triggers customer synchronization from Shopify.
		"""
		return sync_customers(limit=50)
