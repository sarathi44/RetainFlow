# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from retainflow.shopify_api import clean_shopify_url


class ShopifyProduct(Document):
	def onload(self):
		shop_url = frappe.db.get_single_value("Shopify Settings", "shopify_url")
		if shop_url:
			self.set_onload("shop_url", clean_shopify_url(shop_url))
