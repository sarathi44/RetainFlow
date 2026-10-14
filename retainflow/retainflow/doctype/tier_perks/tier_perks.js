// Copyright (c) 2026, Retainflow and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tier Perks", {
	refresh(frm) {
		frm.trigger("render_overview");
	},

	requalification_rule(frm) {
		frm.trigger("render_overview");
	},

	nudge_gap(frm) {
		frm.trigger("render_overview");
	},

	render_overview(frm) {
		frappe.call({
			method: "retainflow.loyalty.get_tier_perks_overview",
			args: { rule: frm.doc.requalification_rule, gap: frm.doc.nudge_gap },
			callback(r) {
				const o = r.message;
				if (!o) return;
				const review = o.next_review
					? __("Next review {0} · <b>{1}</b> customers would move down", [
							frappe.datetime.str_to_user(o.next_review),
							o.moving_down,
					  ])
					: __("Lifetime tiers are never reviewed, so nobody moves down.");
				frm.get_field("review_overview").$wrapper.html(
					`<div class="text-muted" style="padding-top: 28px">${review}</div>`
				);

				const rows = o.nudges.length
					? o.nudges
							.map(
								(n) => `<tr>
									<td><a href="/customers/${encodeURIComponent(n.customer)}">${frappe.utils.escape_html(
									n.customer_name
								)}</a></td>
									<td>${frappe.utils.escape_html(n.next_tier)}</td>
									<td class="text-right">${
										n.basis === "points"
											? format_number(n.gap) + " " + __("points")
											: format_currency(n.gap, o.currency)
									} ${__("to go")}</td>
								</tr>`
							)
							.join("")
					: `<tr><td class="text-muted" colspan="3">${__(
							"No customers within this range."
					  )}</td></tr>`;
				frm.get_field("nudge_overview").$wrapper.html(
					`<table class="table table-sm" style="margin-top: 8px">${rows}</table>`
				);
			},
		});
	},
});
