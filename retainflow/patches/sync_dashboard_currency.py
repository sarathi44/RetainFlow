import frappe

from retainflow.retainflow.doctype.shopify_settings.shopify_settings import update_dashboard_currency


def execute():
	"""Switch dashboard chart and number cards from the hardcoded INR to the shop's currency."""
	currency = frappe.db.get_single_value("Shopify Settings", "currency")
	if currency:
		update_dashboard_currency(currency)
