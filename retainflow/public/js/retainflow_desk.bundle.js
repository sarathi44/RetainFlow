/**
 * RetainFlow · desk routing overrides
 * Opens records that have a custom RetainFlow screen in that screen
 * instead of Frappe's built-in form view.
 */
(function () {
	// doctype → custom record page prefix (record name is appended)
	const CUSTOM_RECORD_ROUTES = {
		"Shopify Customer": "/customers/",
	};

	function custom_path_for(route) {
		if (!route || (route[0] || "").toLowerCase() !== "form") return null;
		const prefix = CUSTOM_RECORD_ROUTES[route[1]];
		const name = route[2];
		// new records keep the desk form
		if (!prefix || !name || name.startsWith("new-")) return null;
		return prefix + encodeURIComponent(name);
	}

	// patch at load time so a direct hit on /desk/shopify-customer/<name> is caught too
	const render_page = frappe.router.render_page;
	frappe.router.render_page = function () {
		const path = custom_path_for(this.current_route);
		if (path) {
			window.location.replace(path);
			return;
		}
		return render_page.apply(this, arguments);
	};
})();
