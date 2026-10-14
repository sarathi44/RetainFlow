import os

import frappe

no_cache = 1


def _asset_version(*parts):
	path = os.path.join(frappe.get_app_path("retainflow", "public"), *parts)
	try:
		return str(int(os.path.getmtime(path)))
	except OSError:
		return "0"


def get_context(context):
	# served at /customers/<name> via website_route_rules in hooks.py
	name = frappe.form_dict.get("name")

	if frappe.session.user == "Guest":
		frappe.redirect(f"/login?redirect-to=/customers/{name or ''}")

	if not name or not frappe.db.exists("Shopify Customer", name):
		raise frappe.PageDoesNotExistError

	context.title = f"{frappe.db.get_value('Shopify Customer', name, 'customer_name') or name} · RetainFlow"
	context.base_template = "templates/blank.html"
	context.customer_name = name
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.css_v = _asset_version("css", "retainflow.css")
	context.js_v = _asset_version("js", "customer_page.js")
	return context
