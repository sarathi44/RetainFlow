// Copyright (c) 2026, Retainflow and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shopify Settings", {
	refresh(frm) {
		// Set indicator
		if (frm.doc.connection_status === "Connected") {
			frm.dashboard.set_headline_alert(
				__("Shopify Store Connected: {0} ({1})", [
					frm.doc.shop_name || frm.doc.shopify_url,
					frm.doc.currency || "Default Currency",
				]),
				"green"
			);
		} else if (frm.doc.connection_status === "Error") {
			frm.dashboard.set_headline_alert(
				__("Connection Error: Please re-check credentials or store URL"),
				"red"
			);
		} else {
			frm.dashboard.set_headline_alert(
				__("Shopify is not connected. Enter your credentials and test the connection."),
				"orange"
			);
		}

		// Action Buttons
		frm.add_custom_button(__("Test Connection"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Please save your changes before testing the connection."));
				return;
			}
			frappe.show_alert({ message: __("Testing connection..."), indicator: "blue" });
			frm.call({
				method: "test_connection",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Connecting to Shopify Admin API..."),
				callback(r) {
					if (!r.exc && r.message) {
						frappe.msgprint({
							title: __("Connection Successful"),
							indicator: "green",
							message: __(
								"Successfully connected to <b>{0}</b> ({1})!<br>Timezone: {2}<br>Currency: {3}",
								[
									r.message.shop.shop_name,
									r.message.shop.myshopify_domain,
									r.message.shop.timezone,
									r.message.shop.currency,
								]
							),
						});
						frm.reload_doc();
					}
				},
			});
		}).addClass("btn-primary");

		frm.add_custom_button(__("Sync Orders Now"), () => {
			if (frm.doc.connection_status !== "Connected") {
				frappe.confirm(
					__("The connection has not been verified yet. Do you want to proceed with syncing orders?"),
					() => {
						trigger_sync(frm);
					}
				);
			} else {
				trigger_sync(frm);
			}
		});

		frm.add_custom_button(__("View Shopify Orders"), () => {
			frappe.set_route("List", "Shopify Order");
		}, __("Navigation"));
	},
});

function trigger_sync(frm) {
	frappe.show_alert({ message: __("Syncing orders from Shopify..."), indicator: "blue" });
	frm.call({
		method: "sync_orders_now",
		doc: frm.doc,
		freeze: true,
		freeze_message: __("Fetching orders from Shopify API..."),
		callback(r) {
			if (!r.exc && r.message) {
				frappe.msgprint({
					title: __("Sync Complete"),
					indicator: "green",
					message: __(
						"<b>{0}</b> orders processed.<br>Total orders stored: <b>{1}</b>",
						[r.message.synced_count, r.message.total_orders]
					),
				});
				frm.reload_doc();
			}
		},
	});
}
