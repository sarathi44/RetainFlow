# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from retainflow.loyalty import get_tiers

# child-row defaults are not applied to rows added through append()
ROW_DEFAULTS = {
	"points_multiplier": 1,
	"free_shipping": "None",
	"early_access": "None",
	"birthday_bonus": 0,
	"support": "Standard",
}


class TierPerks(Document):
	def validate(self):
		self.sync_rows_with_tiers()

	def sync_rows_with_tiers(self):
		"""Keep exactly one row per Loyalty Settings tier, in tier order."""
		tiers = [t.tier_name for t in get_tiers(frappe.get_single("Loyalty Settings"))]
		rows = {}
		for row in self.perks:
			if row.tier in rows:
				frappe.throw(_("Tier {0} is listed more than once").format(row.tier))
			rows[row.tier] = row

		self.perks = []
		for tier in tiers:
			values = rows[tier].as_dict() if tier in rows else {}
			values.pop("idx", None)
			values.update(tier=tier, shopify_tag="rf-tier-" + frappe.scrub(tier).replace("_", "-"))
			for field, default in ROW_DEFAULTS.items():
				if values.get(field) in (None, ""):
					values[field] = default
			self.append("perks", values)
