frappe.listview_settings["Shopify Sync Log"] = {
	get_indicator: function (doc) {
		const status_colors = {
			Success: "green",
			Failed: "red",
		};
		const status = doc.status || "Success";
		return [__(status), status_colors[status] || "grey", "status,=," + status];
	},
};
