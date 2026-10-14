import frappe

from retainflow.loyalty import run_tier_review
from retainflow.shopify_api import sync_customers, sync_orders


def run_scheduled_sync(settings):
	"""Customers first, so new orders can be linked to them and earn loyalty points."""
	try:
		sync_customers(limit=50)
	except Exception:
		# already written to the Error Log and Sync Log; orders still sync
		frappe.db.rollback()
	sync_orders(limit=settings.order_sync_limit or 50)


def hourly():
	"""Scheduled task run hourly."""
	settings = frappe.get_single("Shopify Settings")
	if settings.enable_sync and settings.sync_frequency == "Hourly":
		run_scheduled_sync(settings)


def daily():
	"""Scheduled task run daily."""
	settings = frappe.get_single("Shopify Settings")
	if settings.enable_sync and settings.sync_frequency == "Daily":
		run_scheduled_sync(settings)

	run_tier_review()
