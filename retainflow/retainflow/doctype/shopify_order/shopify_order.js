// Copyright (c) 2026, Retainflow and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shopify Order", {
	refresh(frm) {
		// Set dashboard indicators
		const fin_color = {
			paid: "green",
			pending: "orange",
			authorized: "blue",
			partially_paid: "yellow",
			refunded: "red",
			voided: "darkgrey",
		}[frm.doc.financial_status] || "grey";

		const ful_color = {
			fulfilled: "green",
			unfulfilled: "orange",
			partially_fulfilled: "yellow",
			restocked: "blue",
		}[frm.doc.fulfillment_status] || "grey";

		frm.page.set_indicator(
			`${frm.doc.financial_status ? frm.doc.financial_status.toUpperCase() : "PENDING"} / ${
				frm.doc.fulfillment_status ? frm.doc.fulfillment_status.toUpperCase() : "UNFULFILLED"
			}`,
			fin_color
		);

		// Button: Open in Shopify Admin
		if (frm.doc.shopify_order_url) {
			frm.add_custom_button(__("Open in Shopify Admin"), () => {
				window.open(frm.doc.shopify_order_url, "_blank");
			}).addClass("btn-primary");
		}

		// Button: Shopify Settings
		frm.add_custom_button(__("Shopify Settings"), () => {
			frappe.set_route("Form", "Shopify Settings");
		}, __("Actions"));
	},
});
