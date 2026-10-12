frappe.listview_settings["Shopify Order"] = {
	get_indicator: function (doc) {
		const status_colors = {
			paid: "green",
			pending: "orange",
			authorized: "blue",
			partially_paid: "yellow",
			refunded: "red",
			voided: "darkgrey",
		};
		const status = doc.financial_status || "pending";
		return [__(status.toUpperCase()), status_colors[status] || "grey", "financial_status,=," + status];
	},
	onload: function (list_view) {
		list_view.page.add_inner_button(__("Sync from Shopify"), () => {
			frappe.show_alert({ message: __("Fetching orders from Shopify..."), indicator: "blue" });
			frappe.call({
				method: "retainflow.shopify_api.sync_orders",
				args: { limit: 50 },
				freeze: true,
				freeze_message: __("Syncing orders with Shopify..."),
				callback: function (r) {
					if (!r.exc && r.message) {
						frappe.msgprint({
							title: __("Sync Complete"),
							indicator: "green",
							message: __(
								"<b>{0}</b> orders synced.<br>Total orders stored: <b>{1}</b>",
								[r.message.synced_count, r.message.total_orders]
							),
						});
						list_view.refresh();
					}
				},
			});
		});

		list_view.page.add_inner_button(__("Shopify Settings"), () => {
			frappe.set_route("Form", "Shopify Settings");
		});
	},
};
