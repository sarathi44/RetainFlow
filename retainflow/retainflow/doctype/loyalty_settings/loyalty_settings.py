# Copyright (c) 2026, Retainflow and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LoyaltySettings(Document):
	def validate(self):
		seen = set()
		for tier in self.tiers:
			key = (tier.tier_name or "").strip().lower()
			if key in seen:
				frappe.throw(_("Tier {0} is listed more than once").format(tier.tier_name))
			seen.add(key)

		# keep tiers ordered by threshold so the lowest is the entry tier
		self.tiers.sort(key=lambda t: t.threshold or 0)
		for i, tier in enumerate(self.tiers, start=1):
			tier.idx = i

	def on_update(self):
		from retainflow.loyalty import recalculate_all

		frappe.clear_document_cache("Loyalty Settings", "Loyalty Settings")
		# one perks row per tier
		frappe.get_single("Tier Perks").save(ignore_permissions=True)
		recalculate_all()
