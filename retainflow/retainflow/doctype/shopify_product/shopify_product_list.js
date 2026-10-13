frappe.listview_settings["Shopify Product"] = {
	get_indicator: function (doc) {
		const status_colors = {
			active: "green",
			draft: "orange",
			archived: "grey",
		};
		const status = doc.status || "active";
		return [__(status.toUpperCase()), status_colors[status] || "grey", "status,=," + status];
	},
	onload: function (list_view) {
		list_view.page.add_inner_button(__("Sync from Shopify"), () => {
			frappe.show_alert({
				message: __("Fetching products from Shopify..."),
				indicator: "blue",
			});
			frappe.call({
				method: "retainflow.shopify_api.sync_products",
				args: { limit: 50 },
				freeze: true,
				freeze_message: __("Syncing products with Shopify..."),
				callback: function (r) {
					if (!r.exc && r.message) {
						frappe.msgprint({
							title: __("Sync Complete"),
							indicator: "green",
							message: __(
								"<b>{0}</b> products synced.<br>Total products stored: <b>{1}</b>",
								[r.message.synced_count, r.message.total_products]
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
