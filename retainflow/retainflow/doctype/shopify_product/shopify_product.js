// Copyright (c) 2026, Retainflow and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shopify Product", {
	refresh(frm) {
		// Set status indicator
		const status_color =
			{
				active: "green",
				draft: "orange",
				archived: "grey",
			}[frm.doc.status] || "grey";

		frm.page.set_indicator(
			frm.doc.status ? frm.doc.status.toUpperCase() : "UNKNOWN",
			status_color
		);

		// Button: Open in Shopify Admin
		if (frm.doc.shopify_product_url) {
			frm.add_custom_button(__("Open in Shopify Admin"), () => {
				window.open(frm.doc.shopify_product_url, "_blank");
			}).addClass("btn-primary");
		}

		// Button: View on Storefront
		if (frm.doc.handle && frm.doc.__onload && frm.doc.__onload.shop_url) {
			frm.add_custom_button(__("View on Storefront"), () => {
				window.open(
					`https://${frm.doc.__onload.shop_url}/products/${frm.doc.handle}`,
					"_blank"
				);
			});
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
