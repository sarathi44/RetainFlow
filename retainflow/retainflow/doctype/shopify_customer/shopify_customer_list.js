frappe.listview_settings["Shopify Customer"] = {
	onload: function (list_view) {
		list_view.page.add_inner_button(__("Sync from Shopify"), () => {
			frappe.call({
				method: "retainflow.shopify_api.sync_customers",
				args: { limit: 50 },
				freeze: true,
				freeze_message: __("Syncing customers with Shopify..."),
				callback: function (r) {
					if (!r.exc && r.message) {
						frappe.msgprint({
							title: __("Sync Complete"),
							indicator: "green",
							message: __(
								"<b>{0}</b> customers synced.<br>Total customers stored: <b>{1}</b>",
								[r.message.synced_count, r.message.total_customers]
							),
						});
						list_view.refresh();
					}
				},
			});
		});
	},
};
