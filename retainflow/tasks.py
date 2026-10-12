import frappe
from retainflow.shopify_api import sync_orders


def hourly():
	"""Scheduled task run hourly."""
	settings = frappe.get_single("Shopify Settings")
	if settings.enable_sync and settings.sync_frequency == "Hourly":
		sync_orders(limit=settings.order_sync_limit or 50)


def daily():
	"""Scheduled task run daily."""
	settings = frappe.get_single("Shopify Settings")
	if settings.enable_sync and settings.sync_frequency == "Daily":
		sync_orders(limit=settings.order_sync_limit or 50)
