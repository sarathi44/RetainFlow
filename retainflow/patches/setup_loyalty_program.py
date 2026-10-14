import json

import frappe
from frappe.utils import now_datetime

from retainflow.loyalty import recalculate_all

DEFAULT_TIERS = [
	{"tier_name": "Bronze", "threshold": 0, "benefit": "Welcome recognition", "is_vip": 0},
	{"tier_name": "Silver", "threshold": 5000, "benefit": "Early access to sales", "is_vip": 1},
	{"tier_name": "Gold", "threshold": 15000, "benefit": "Priority support and gifts", "is_vip": 1},
]


def execute():
	"""Create the default loyalty program, link existing orders to customers and post their points."""
	link_existing_orders()

	settings = frappe.get_single("Loyalty Settings")
	if not settings.tiers:
		settings.earning_enabled = 1
		settings.points_per_unit = 0.1
		settings.effective_from = settings.effective_from or now_datetime()
		settings.historical_orders = "Award once for imported eligible orders"
		settings.tier_basis = "Cumulative spend"
		for tier in DEFAULT_TIERS:
			settings.append("tiers", tier)
		settings.save(ignore_permissions=True)  # on_update recalculates

	recalculate_all()


def link_existing_orders():
	"""Fill the Shopify customer ID on orders synced before the field existed."""
	for order in frappe.get_all(
		"Shopify Order", filters={"shopify_customer_id": ("is", "not set")}, fields=["name", "raw_json"]
	):
		try:
			customer_id = str((json.loads(order.raw_json or "{}").get("customer") or {}).get("id") or "")
		except ValueError:
			continue
		if not customer_id:
			continue
		values = {"shopify_customer_id": customer_id}
		if frappe.db.exists("Shopify Customer", customer_id):
			values["shopify_customer"] = customer_id
		frappe.db.set_value("Shopify Order", order.name, values, update_modified=False)
