"""
Whitelisted API endpoints for the RetainFlow Vue frontend.
"""

import frappe
from frappe.utils import cint, flt, fmt_money, get_datetime, now_datetime

from retainflow.loyalty import (
	get_nudges,
	get_perks,
	get_settings,
	get_tier_benefit,
	get_tier_perk,
	is_vip_tier,
)

# Recency segments (RetainFlow product spec)
AT_RISK_AFTER_DAYS = 45
INACTIVE_AFTER_DAYS = 90


def get_store_context() -> dict:
	"""Store-level info shown in the page chrome."""
	settings = frappe.db.get_singles_dict("Shopify Settings")
	return {
		"shop_name": settings.get("shop_name") or "Shopify admin",
		"myshopify_domain": settings.get("myshopify_domain") or "",
		"currency": settings.get("currency") or "INR",
		"total_customers": frappe.db.count("Shopify Customer"),
	}


def get_segments(orders: int, is_vip: bool, days_since_last: int | None) -> list[str]:
	segments = []
	if orders == 0:
		return ["No eligible orders"]
	if orders == 1:
		segments.append("New")
	else:
		segments.append("Repeat")
	if is_vip:
		segments.append("VIP")
	if days_since_last is not None:
		if days_since_last > INACTIVE_AFTER_DAYS:
			segments.append("Inactive")
		elif days_since_last >= AT_RISK_AFTER_DAYS:
			segments.append("At Risk")
	return segments


def get_loyalty_metrics(customer) -> dict:
	"""Stored ledger totals, tier and derived segments for one customer."""
	settings = get_settings()
	days_since_last = None
	if customer.last_eligible_order:
		days_since_last = max((now_datetime() - get_datetime(customer.last_eligible_order)).days, 0)

	is_vip = is_vip_tier(customer.loyalty_tier, settings)
	perks = get_perks()
	perk = get_tier_perk(customer.loyalty_tier, perks)
	nudge = get_nudges(perks.nudge_gap, customer.name)
	return {
		"orders": cint(customer.eligible_orders),
		"spend": flt(customer.eligible_spend),
		"points": cint(customer.loyalty_points),
		"tier": customer.loyalty_tier or "",
		"tier_benefit": get_tier_benefit(customer.loyalty_tier, settings),
		"is_vip": is_vip,
		"segments": get_segments(cint(customer.eligible_orders), is_vip, days_since_last),
		"perks": describe_perks(perk, customer.currency or get_store_currency()),
		"nudge": nudge[0] if nudge else None,
		"downgrade_to": customer.tier_downgrade_to or "",
		"downgrade_due": str(customer.tier_downgrade_due or ""),
		"days_since_last": days_since_last,
	}


def get_store_currency() -> str:
	return frappe.db.get_single_value("Shopify Settings", "currency") or "INR"


def describe_perks(perk, currency: str | None = None) -> list[dict]:
	"""Readable perk list for a tier's Tier Perk row."""
	if not perk:
		return []
	shipping = perk.free_shipping
	if shipping == "Over minimum order":
		shipping = f"Over {fmt_money(perk.free_shipping_minimum, currency=currency)}"
	return [
		{"label": "Points multiplier", "value": f"{flt(perk.points_multiplier):g}×"},  # noqa: RUF001
		{"label": "Free shipping", "value": shipping or "None"},
		{"label": "Early access to sales", "value": perk.early_access or "None"},
		{
			"label": "Birthday bonus",
			"value": f"{cint(perk.birthday_bonus)} points" if cint(perk.birthday_bonus) else "None",
		},
		{"label": "Support", "value": perk.support or "Standard"},
		{"label": "Shopify tag", "value": perk.shopify_tag or ""},
	]


@frappe.whitelist()
def get_customer(name: str) -> dict:
	"""
	Returns a single Shopify Customer record with loyalty metrics,
	addresses and recent orders for the RetainFlow customer page.
	"""
	doc = frappe.get_doc("Shopify Customer", name)
	doc.check_permission("read")

	orders = frappe.get_all(
		"Shopify Order",
		filters={"shopify_customer": doc.name},
		fields=[
			"name",
			"shopify_order_name",
			"order_date",
			"financial_status",
			"fulfillment_status",
			"order_status",
			"total_price",
			"currency",
			"shopify_order_url",
		],
		order_by="order_date desc",
		limit=20,
	)

	return {
		"store": get_store_context(),
		"customer": {
			"docname": doc.name,
			"name": doc.customer_name,
			"shopify_id": doc.shopify_customer_id,
			"email": doc.email or "",
			"phone": doc.phone or "",
			"state": doc.state,
			"verified_email": cint(doc.verified_email),
			"accepts_marketing": cint(doc.accepts_marketing),
			"tags": [t.strip() for t in (doc.tags or "").split(",") if t.strip()],
			"note": doc.note or "",
			"currency": doc.currency or "INR",
			"shopify_orders_count": cint(doc.orders_count),
			"shopify_total_spent": flt(doc.total_spent),
			"created_at_shopify": str(doc.created_at_shopify or ""),
			"updated_at_shopify": str(doc.updated_at_shopify or ""),
			"shopify_customer_url": doc.shopify_customer_url or "",
			"addresses": [
				{
					"name": a.customer_address_name or "",
					"lines": [
						x
						for x in (
							a.address1,
							a.address2,
							" ".join(p for p in (a.city, a.province, a.zip) if p),
							a.country,
						)
						if x
					],
					"phone": a.phone or "",
					"is_default": cint(a.is_default),
				}
				for a in doc.addresses
			],
			**get_loyalty_metrics(doc),
		},
		"ledger": [
			{
				"date": str(e.posting_date or ""),
				"order": e.shopify_order_name or e.shopify_order,
				"eligible_amount": flt(e.eligible_amount),
				"currency": e.currency or doc.currency or "INR",
				"rate": flt(e.rate),
				"multiplier": flt(e.multiplier) or 1,
				"points": cint(e.points),
			}
			for e in frappe.get_all(
				"Loyalty Points Entry",
				filters={"shopify_customer": doc.name},
				fields=[
					"posting_date",
					"shopify_order",
					"shopify_order.shopify_order_name as shopify_order_name",
					"eligible_amount",
					"currency",
					"rate",
					"multiplier",
					"points",
				],
				order_by="posting_date desc",
				limit=50,
			)
		],
		"orders": [
			{
				"name": o.shopify_order_name or o.name,
				"date": str(o.order_date or ""),
				"financial_status": o.financial_status or "",
				"fulfillment_status": o.fulfillment_status or "",
				"order_status": o.order_status or "",
				"total": flt(o.total_price),
				"currency": o.currency or doc.currency or "INR",
				"url": o.shopify_order_url or "",
			}
			for o in orders
		],
	}
