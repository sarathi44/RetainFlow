// Copyright (c) 2026, Retainflow and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shopify Customer", {
	refresh(frm) {
		// Set state indicator
		const state_color =
			{
				enabled: "green",
				invited: "orange",
				disabled: "grey",
			}[frm.doc.state] || "grey";

		frm.page.set_indicator(
			frm.doc.state ? frm.doc.state.toUpperCase() : "UNKNOWN",
			state_color
		);

		// Button: Open in Shopify Admin
		if (frm.doc.shopify_customer_url) {
			frm.add_custom_button(__("Open in Shopify Admin"), () => {
				window.open(frm.doc.shopify_customer_url, "_blank");
			}).addClass("btn-primary");
		}

		// Button: Shopify Settings
		frm.add_custom_button(
			__("Shopify Settings"),
			() => {
				frappe.set_route("Form", "Shopify Settings");
			},
			__("Actions")
		);
	},
});
