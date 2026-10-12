# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ShopifyOrder(Document):
	def before_insert(self):
		if not self.shopify_order_id:
			self.shopify_order_id = str(frappe.generate_hash(length=10))
		if not self.shopify_order_name:
			self.shopify_order_name = f"#{self.shopify_order_id}"

	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		if self.items:
			subtotal = 0.0
			for item in self.items:
				item.amount = (flt(item.price) * flt(item.quantity)) - flt(item.total_discount or 0.0)
				subtotal += item.amount
			if not self.subtotal_price or self.is_new():
				self.subtotal_price = subtotal
			if not self.total_price or self.is_new():
				self.total_price = (
					self.subtotal_price
					+ flt(self.total_tax)
					+ flt(self.total_shipping)
					- flt(self.total_discounts)
				)
