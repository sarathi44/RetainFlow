"""
RetainFlow loyalty engine.

Points are posted once per eligible order into Loyalty Points Entry at the
rate in force when the order is evaluated, times the multiplier of the
customer's tier at that moment (Tier Perks), and are never reversed
automatically. A customer's totals and tier are derived from that ledger and
stored on Shopify Customer.

Tiers move up immediately when the threshold is met within the window of the
requalification rule (Tier Perks). They only move down in the scheduled tier
review: never under "Lifetime", on 1 January under "Calendar year", and after
the grace period under "Rolling 12 months".
"""

import math

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_datetime, get_first_day, getdate, now_datetime

HISTORICAL_AFTER_START_ONLY = "Only orders after the program start date"
TIER_BASIS_POINTS = "Cumulative earned points"

RULE_ROLLING = "Rolling 12 months"
RULE_CALENDAR = "Calendar year"
RULE_LIFETIME = "Lifetime"


def get_settings():
	return frappe.get_cached_doc("Loyalty Settings")


def get_tiers(settings=None) -> list:
	"""Tiers ordered by threshold, lowest (entry tier) first."""
	settings = settings or get_settings()
	return sorted(settings.tiers, key=lambda t: flt(t.threshold))


def is_vip_tier(tier_name: str | None, settings=None) -> bool:
	return any(t.tier_name == tier_name and cint(t.is_vip) for t in get_tiers(settings))


def get_perks():
	return frappe.get_cached_doc("Tier Perks")


def get_tier_perk(tier_name: str | None, perks=None):
	perks = perks or get_perks()
	return next((p for p in perks.perks if p.tier == tier_name), None)


def get_multiplier(tier_name: str | None, perks=None) -> float:
	perk = get_tier_perk(tier_name, perks)
	return flt(perk.points_multiplier) if perk and flt(perk.points_multiplier) > 0 else 1.0


def get_tier_benefit(tier_name: str | None, settings=None) -> str:
	return next((t.benefit or "" for t in get_tiers(settings) if t.tier_name == tier_name), "")


def eligible_amount(order) -> float:
	"""Merchandise minus discounts; shipping, tax, duties and tips are excluded."""
	return max(flt(order.subtotal_price), 0.0)


def is_eligible(order, settings) -> bool:
	if not cint(settings.earning_enabled):
		return False
	if not order.shopify_customer:
		return False  # guest orders do not earn
	if order.financial_status != "paid" or order.order_status == "cancelled":
		return False
	if (
		settings.historical_orders == HISTORICAL_AFTER_START_ONLY
		and settings.effective_from
		and get_datetime(order.order_date) < get_datetime(settings.effective_from)
	):
		return False
	return True


def award_points(order, settings=None) -> bool:
	"""Post points for an order once. Returns True when a new entry was created."""
	settings = settings or get_settings()
	if frappe.db.exists("Loyalty Points Entry", {"shopify_order": order.name}):
		return False
	if not is_eligible(order, settings):
		return False

	amount = eligible_amount(order)
	rate = flt(settings.points_per_unit)
	tier = frappe.db.get_value("Shopify Customer", order.shopify_customer, "loyalty_tier")
	multiplier = get_multiplier(tier)
	frappe.get_doc(
		{
			"doctype": "Loyalty Points Entry",
			"shopify_customer": order.shopify_customer,
			"shopify_order": order.name,
			"posting_date": order.order_date or now_datetime(),
			"eligible_amount": amount,
			"currency": order.currency,
			"rate": rate,
			"multiplier": multiplier,
			"points": math.floor(amount * rate * multiplier + 1e-9),
		}
	).insert(ignore_permissions=True)
	return True


def earned_tier_index(value: float, tiers: list) -> int:
	"""Index of the highest tier whose threshold `value` meets."""
	earned = 0
	for i, tier in enumerate(tiers):
		if value >= flt(tier.threshold):
			earned = i
	return earned


def pick_tier(value: float, current_tier: str | None, settings=None) -> str | None:
	"""Highest tier whose threshold is met, never below the customer's current tier."""
	tiers = get_tiers(settings)
	if not tiers:
		return None

	rank = {t.tier_name: i for i, t in enumerate(tiers)}
	earned = earned_tier_index(value, tiers)

	# moving down only happens in the tier review; a tier removed from the program no longer holds
	if current_tier in rank and rank[current_tier] > earned:
		earned = rank[current_tier]
	return tiers[earned].tier_name


def qualifying_window(rule: str, today=None, for_review: bool = False) -> tuple:
	"""
	(start, end) dates of the ledger counted towards a tier. For upgrades it is the
	window up to now; for the review under "Calendar year" it is the year just ended.
	"""
	today = getdate(today)
	if rule == RULE_ROLLING:
		return add_months(today, -12), None
	if rule == RULE_CALENDAR:
		this_year = today.replace(month=1, day=1)
		if for_review:
			return this_year.replace(year=this_year.year - 1), this_year
		return this_year, None
	return None, None


def tier_basis_value(customer: str, settings, start=None, end=None) -> float:
	"""Eligible spend or earned points in the ledger between start (incl.) and end (excl.)."""
	column = "points" if settings.tier_basis == TIER_BASIS_POINTS else "eligible_amount"
	conditions, values = ["shopify_customer = %(customer)s"], {"customer": customer}
	if start:
		conditions.append("posting_date >= %(start)s")
		values["start"] = start
	if end:
		conditions.append("posting_date < %(end)s")
		values["end"] = end
	return flt(
		frappe.db.sql(
			f"select coalesce(sum({column}), 0) from `tabLoyalty Points Entry` where {' and '.join(conditions)}",
			values,
		)[0][0]
	)


def update_customer(customer: str, settings=None):
	"""Refresh a customer's stored loyalty totals and tier from the ledger."""
	settings = settings or get_settings()
	totals = frappe.db.sql(
		"""
		select count(*) as orders, coalesce(sum(eligible_amount), 0) as spend,
			coalesce(sum(points), 0) as points, max(posting_date) as last_order
		from `tabLoyalty Points Entry`
		where shopify_customer = %s
		""",
		customer,
		as_dict=True,
	)[0]

	start, end = qualifying_window(get_perks().requalification_rule)
	basis_value = tier_basis_value(customer, settings, start, end)
	current = frappe.db.get_value(
		"Shopify Customer", customer, ["loyalty_tier", "tier_downgrade_to"], as_dict=True
	)
	tier = pick_tier(basis_value, current.loyalty_tier, settings)

	values = {
		"eligible_orders": cint(totals.orders),
		"eligible_spend": flt(totals.spend),
		"loyalty_points": cint(totals.points),
		"last_eligible_order": totals.last_order,
		"loyalty_tier": tier,
	}
	# requalified for their tier before a pending downgrade took effect
	tiers = get_tiers(settings)
	if (
		current.tier_downgrade_to
		and tiers
		and earned_tier_index(basis_value, tiers) >= tier_rank(tier, settings)
	):
		values.update(tier_downgrade_to=None, tier_downgrade_due=None)

	frappe.db.set_value("Shopify Customer", customer, values, update_modified=False)


def tier_rank(tier_name: str | None, settings=None) -> int:
	return next((i for i, t in enumerate(get_tiers(settings)) if t.tier_name == tier_name), -1)


def update_tier_members(settings=None):
	"""Write the member count of every tier into Loyalty Settings."""
	settings = settings or get_settings()
	counts = dict(
		frappe.db.sql(
			"""select loyalty_tier, count(*) from `tabShopify Customer`
			where coalesce(loyalty_tier, '') != '' group by loyalty_tier"""
		)
	)
	for tier in settings.tiers:
		frappe.db.set_value(
			"Loyalty Tier", tier.name, "members", cint(counts.get(tier.tier_name)), update_modified=False
		)
	frappe.clear_document_cache("Loyalty Settings", "Loyalty Settings")


def process_order(order):
	"""Called when a Shopify Order is saved: award its points and refresh its customer."""
	if not order.shopify_customer:
		return
	settings = get_settings()
	award_points(order, settings)
	update_customer(order.shopify_customer, settings)
	update_tier_members(settings)


def link_orders_to_customer(customer_id: str):
	"""Attach orders synced before their customer existed, then evaluate them."""
	orders = frappe.get_all(
		"Shopify Order",
		filters={"shopify_customer_id": customer_id, "shopify_customer": ("is", "not set")},
		pluck="name",
		order_by="order_date asc",
	)
	for name in orders:
		frappe.db.set_value("Shopify Order", name, "shopify_customer", customer_id, update_modified=False)

	settings = get_settings()
	for name in orders:
		# refresh after each order so a mid-history upgrade applies its multiplier to later orders
		award_points(frappe.get_doc("Shopify Order", name), settings)
		update_customer(customer_id, settings)
	update_customer(customer_id, settings)
	update_tier_members(settings)


def recalculate_all():
	"""Award any missing points and refresh every customer (e.g. after a settings change)."""
	frappe.clear_document_cache("Loyalty Settings", "Loyalty Settings")
	settings = get_settings()

	for name in frappe.get_all(
		"Shopify Order", filters={"shopify_customer": ("is", "set")}, pluck="name", order_by="order_date asc"
	):
		order = frappe.get_doc("Shopify Order", name)
		if award_points(order, settings):
			update_customer(order.shopify_customer, settings)

	for customer in frappe.get_all("Shopify Customer", pluck="name"):
		update_customer(customer, settings)

	update_tier_members(settings)


# --- Tier review (requalification) ---


def next_review_date(rule: str, today=None):
	today = getdate(today)
	if rule == RULE_ROLLING:
		return add_months(get_first_day(today), 1)
	if rule == RULE_CALENDAR:
		return today.replace(year=today.year + 1, month=1, day=1)
	return None


def review_targets(rule: str, today=None) -> dict:
	"""{customer: tier they would move down to} if the review ran today."""
	settings = get_settings()
	tiers = get_tiers(settings)
	if rule == RULE_LIFETIME or not tiers:
		return {}

	start, end = qualifying_window(rule, today, for_review=True)
	targets = {}
	for c in frappe.get_all(
		"Shopify Customer", filters={"loyalty_tier": ("is", "set")}, fields=["name", "loyalty_tier"]
	):
		earned = earned_tier_index(tier_basis_value(c.name, settings, start, end), tiers)
		if earned < tier_rank(c.loyalty_tier, settings):
			targets[c.name] = tiers[earned].tier_name
	return targets


def run_tier_review(today=None):
	"""
	Daily: on review day, demote (Calendar year) or schedule a demotion after the
	grace period (Rolling 12 months); every day, apply demotions that are due.
	"""
	today = getdate(today)
	perks = get_perks()
	rule = perks.requalification_rule

	if rule == RULE_LIFETIME:
		frappe.db.sql(
			"""update `tabShopify Customer` set tier_downgrade_to = null, tier_downgrade_due = null
			where tier_downgrade_to is not null"""
		)
		return

	is_review_day = today.day == 1 and (rule == RULE_ROLLING or today.month == 1)
	if is_review_day:
		targets = review_targets(rule, today)
		grace = cint(perks.grace_period_days) if rule == RULE_ROLLING else 0
		for customer, target in targets.items():
			if grace:
				if not frappe.db.get_value("Shopify Customer", customer, "tier_downgrade_to"):
					frappe.db.set_value(
						"Shopify Customer",
						customer,
						{"tier_downgrade_to": target, "tier_downgrade_due": add_days(today, grace)},
						update_modified=False,
					)
			else:
				demote(customer, target)

	# grace period over: demote only if still short at the end of it
	targets = None
	for c in frappe.get_all(
		"Shopify Customer",
		filters={"tier_downgrade_due": ("<=", today), "tier_downgrade_to": ("is", "set")},
		pluck="name",
	):
		targets = targets if targets is not None else review_targets(rule, today)
		if c in targets:
			demote(c, targets[c])
		else:
			frappe.db.set_value(
				"Shopify Customer",
				c,
				{"tier_downgrade_to": None, "tier_downgrade_due": None},
				update_modified=False,
			)

	update_tier_members()


def demote(customer: str, tier: str):
	frappe.db.set_value(
		"Shopify Customer",
		customer,
		{"loyalty_tier": tier, "tier_downgrade_to": None, "tier_downgrade_due": None},
		update_modified=False,
	)


# --- "Almost there" nudge ---


def get_nudges(gap: float, customer: str | None = None) -> list[dict]:
	"""Customers within `gap` of the next tier above their current one, closest first."""
	settings = get_settings()
	tiers = get_tiers(settings)
	start, end = qualifying_window(get_perks().requalification_rule)
	filters = {"name": customer} if customer else {}

	nudges = []
	for c in frappe.get_all(
		"Shopify Customer", filters=filters, fields=["name", "customer_name", "loyalty_tier"]
	):
		rank = tier_rank(c.loyalty_tier, settings)
		if rank + 1 >= len(tiers):
			continue
		next_tier = tiers[rank + 1]
		remaining = flt(next_tier.threshold) - tier_basis_value(c.name, settings, start, end)
		if 0 < remaining <= flt(gap):
			nudges.append(
				{
					"customer": c.name,
					"customer_name": c.customer_name,
					"next_tier": next_tier.tier_name,
					"gap": remaining,
					"basis": "points" if settings.tier_basis == TIER_BASIS_POINTS else "spend",
				}
			)
	return sorted(nudges, key=lambda n: n["gap"])


@frappe.whitelist()
def get_tier_perks_overview(rule: str | None = None, gap: float | None = None) -> dict:
	"""Review preview and nudge list for the Tier Perks form (uses unsaved form values)."""
	frappe.only_for("System Manager")
	perks = get_perks()
	rule = rule or perks.requalification_rule
	gap = perks.nudge_gap if gap is None else flt(gap)
	review = next_review_date(rule)
	return {
		"next_review": str(review) if review else None,
		"moving_down": len(review_targets(rule, review)) if review else 0,
		"nudges": get_nudges(gap),
		"currency": frappe.db.get_single_value("Shopify Settings", "currency") or "INR",
	}
