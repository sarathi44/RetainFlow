import frappe

# prototype defaults (Perks screen), by tier name
DEFAULT_PERKS = {
	"Bronze": {"points_multiplier": 1, "free_shipping": "None", "early_access": "None", "birthday_bonus": 50},
	"Silver": {
		"points_multiplier": 1.25,
		"free_shipping": "Over minimum order",
		"free_shipping_minimum": 999,
		"early_access": "24 hours",
		"birthday_bonus": 100,
	},
	"Gold": {
		"points_multiplier": 1.5,
		"free_shipping": "Always",
		"early_access": "48 hours",
		"birthday_bonus": 250,
		"support": "Priority",
	},
}


def execute():
	"""Create Tier Perks with one row per loyalty tier, seeded with the prototype's perks."""
	perks = frappe.get_single("Tier Perks")
	if perks.perks:
		return

	perks.requalification_rule = "Lifetime"  # matches the no-downgrade behaviour so far
	perks.grace_period_days = 30
	perks.nudge_gap = 2000
	perks.save(ignore_permissions=True)  # validate adds a row per tier

	for row in perks.perks:
		row.update(DEFAULT_PERKS.get(row.tier, {}))
	perks.save(ignore_permissions=True)
