import json
import re
import requests
import frappe
from frappe.utils import flt, get_datetime, now_datetime


def clean_shopify_url(url: str) -> str:
	"""
	Sanitizes Shopify URL input:
	e.g. 'https://my-store.myshopify.com/' -> 'my-store.myshopify.com'
	"""
	if not url:
		return ""
	url = url.strip()
	url = re.sub(r"^https?://", "", url)
	url = url.rstrip("/")
	return url


def get_shopify_headers(access_token: str) -> dict:
	return {
		"Content-Type": "application/json",
		"X-Shopify-Access-Token": access_token.strip() if access_token else "",
	}


def test_shopify_connection(shop_url: str, access_token: str, api_version: str = "2024-10") -> dict:
	"""
	Tests connectivity to Shopify Admin API using the shop.json endpoint.
	"""
	clean_url = clean_shopify_url(shop_url)
	if not clean_url:
		frappe.throw("Shopify Store URL cannot be empty.")
	if not access_token:
		frappe.throw("Admin API Access Token cannot be empty.")

	endpoint = f"https://{clean_url}/admin/api/{api_version}/shop.json"
	headers = get_shopify_headers(access_token)

	try:
		response = requests.get(endpoint, headers=headers, timeout=15)
	except requests.RequestException as e:
		frappe.throw(f"Network error while connecting to Shopify: {str(e)}")

	if response.status_code == 401:
		frappe.throw("Shopify Authentication Failed (401 Unauthorized). Please check your Admin API Access Token.")
	elif response.status_code == 403:
		frappe.throw("Shopify Access Forbidden (403). Make sure your app has the required read/write permissions (scopes).")
	elif response.status_code == 404:
		frappe.throw(f"Shopify Store not found at {clean_url} (404 Not Found). Please verify the store URL.")
	elif response.status_code != 200:
		frappe.throw(f"Failed to connect to Shopify. Status Code: {response.status_code}. Response: {response.text}")

	data = response.json()
	shop = data.get("shop", {})
	return {
		"shop_name": shop.get("name"),
		"shop_email": shop.get("email"),
		"currency": shop.get("currency"),
		"timezone": shop.get("iana_timezone") or shop.get("timezone"),
		"myshopify_domain": shop.get("myshopify_domain"),
	}


def fetch_shopify_orders(
	shop_url: str,
	access_token: str,
	api_version: str = "2024-10",
	limit: int = 50,
	status: str = "any",
) -> list[dict]:
	"""
	Fetches orders from Shopify Admin API.
	"""
	clean_url = clean_shopify_url(shop_url)
	endpoint = f"https://{clean_url}/admin/api/{api_version}/orders.json"
	headers = get_shopify_headers(access_token)
	params = {
		"status": status,
		"limit": min(limit, 250),
	}

	try:
		response = requests.get(endpoint, headers=headers, params=params, timeout=25)
	except requests.RequestException as e:
		frappe.throw(f"Error fetching orders from Shopify: {str(e)}")

	if response.status_code != 200:
		frappe.throw(
			f"Shopify Orders API returned error {response.status_code}: {response.text}"
		)

	data = response.json()
	return data.get("orders", [])


def format_address(addr: dict | None) -> str:
	if not addr:
		return ""
	parts = [
		addr.get("name"),
		addr.get("company"),
		addr.get("address1"),
		addr.get("address2"),
		", ".join(filter(None, [addr.get("city"), addr.get("province"), addr.get("zip")])),
		addr.get("country"),
		f"Phone: {addr.get('phone')}" if addr.get("phone") else None,
	]
	return "\n".join(part for part in parts if part)


def parse_shopify_datetime(dt_str: str | None):
	if not dt_str:
		return None
	try:
		dt = get_datetime(dt_str)
		if hasattr(dt, "tzinfo") and dt.tzinfo:
			dt = dt.replace(tzinfo=None)
		return dt
	except Exception:
		return None


def sync_single_order(order_data: dict, shop_url: str) -> str:
	"""
	Upserts a single Shopify order dictionary into the Frappe 'Shopify Order' doctype.
	Returns the Shopify Order ID.
	"""
	order_id = str(order_data.get("id"))
	if not order_id:
		return ""

	customer_data = order_data.get("customer") or {}
	customer_name = (
		f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip()
	)
	if not customer_name:
		customer_name = order_data.get("email") or "Guest Customer"

	financial_status = order_data.get("financial_status") or "pending"
	raw_fulfillment = order_data.get("fulfillment_status")
	fulfillment_status = raw_fulfillment if raw_fulfillment else "unfulfilled"

	order_status = "open"
	if order_data.get("cancelled_at"):
		order_status = "cancelled"
	elif order_data.get("closed_at"):
		order_status = "closed"

	order_date = parse_shopify_datetime(order_data.get("created_at")) or now_datetime()
	cancelled_at = parse_shopify_datetime(order_data.get("cancelled_at"))

	shipping_address = format_address(order_data.get("shipping_address"))
	billing_address = format_address(order_data.get("billing_address"))

	# Format gateways
	gateways = order_data.get("payment_gateway_names") or []
	payment_gateways = ", ".join(gateways) if isinstance(gateways, list) else str(gateways)

	clean_url = clean_shopify_url(shop_url)
	admin_order_url = f"https://{clean_url}/admin/orders/{order_id}"

	# Check if document already exists
	if frappe.db.exists("Shopify Order", order_id):
		order_doc = frappe.get_doc("Shopify Order", order_id)
	else:
		order_doc = frappe.new_doc("Shopify Order")
		order_doc.shopify_order_id = order_id

	order_doc.shopify_order_name = order_data.get("name") or f"#{order_id}"
	order_doc.order_date = order_date
	order_doc.financial_status = financial_status
	order_doc.fulfillment_status = fulfillment_status
	order_doc.order_status = order_status
	order_doc.cancelled_at = cancelled_at
	order_doc.cancel_reason = order_data.get("cancel_reason") or ""
	order_doc.customer_name = customer_name
	order_doc.customer_email = order_data.get("email") or customer_data.get("email") or ""
	order_doc.customer_phone = order_data.get("phone") or customer_data.get("phone") or ""
	order_doc.shipping_address = shipping_address
	order_doc.billing_address = billing_address
	order_doc.currency = order_data.get("currency") or "USD"
	order_doc.subtotal_price = flt(order_data.get("current_subtotal_price") or order_data.get("subtotal_price"))
	order_doc.total_tax = flt(order_data.get("total_tax"))
	order_doc.total_discounts = flt(order_data.get("total_discounts"))
	order_doc.total_shipping = flt(
		order_data.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount")
		or 0.0
	)
	order_doc.total_price = flt(order_data.get("current_total_price") or order_data.get("total_price"))
	order_doc.payment_gateway_names = payment_gateways
	order_doc.tags = order_data.get("tags") or ""
	order_doc.shopify_order_url = admin_order_url
	order_doc.raw_json = json.dumps(order_data, indent=2)

	# Process line items
	order_doc.items = []
	for item in order_data.get("line_items", []):
		qty = item.get("quantity", 1)
		price = flt(item.get("price"))
		discount = flt(item.get("total_discount") or 0.0)
		amount = (price * qty) - discount
		order_doc.append(
			"items",
			{
				"title": item.get("title") or item.get("name"),
				"variant_title": item.get("variant_title") or "",
				"sku": item.get("sku") or "",
				"quantity": qty,
				"price": price,
				"total_discount": discount,
				"amount": amount,
				"shopify_product_id": str(item.get("product_id") or ""),
				"shopify_variant_id": str(item.get("variant_id") or ""),
				"shopify_line_item_id": str(item.get("id") or ""),
			},
		)

	if order_doc.is_new():
		order_doc.insert(ignore_permissions=True)
	else:
		order_doc.save(ignore_permissions=True)

	return order_id


def sync_orders(limit: int = 50) -> dict:
	"""
	Main sync runner called from Settings or Scheduler.
	"""
	settings = frappe.get_single("Shopify Settings")
	shop_url = settings.shopify_url
	token = None
	try:
		token = settings.get_password("access_token")
	except Exception:
		pass
	if not token:
		token = settings.access_token

	api_version = settings.api_version or "2024-10"

	if not shop_url or not token:
		frappe.throw("Please configure Shopify Store URL and Admin API Access Token first.")

	try:
		orders = fetch_shopify_orders(
			shop_url=shop_url,
			access_token=token,
			api_version=api_version,
			limit=limit or settings.order_sync_limit or 50,
		)
		synced_count = 0
		for order_data in orders:
			sync_single_order(order_data, shop_url)
			synced_count += 1

		frappe.db.commit()

		total_orders = frappe.db.count("Shopify Order")
		settings.db_set("last_sync_time", now_datetime())
		settings.db_set("last_sync_status", "Success")
		settings.db_set("total_orders_synced", total_orders)
		settings.db_set("last_error_message", "")

		return {
			"status": "success",
			"synced_count": synced_count,
			"total_orders": total_orders,
			"message": f"Successfully synced {synced_count} orders from Shopify.",
		}
	except Exception as e:
		frappe.log_error(title="Shopify Order Sync Failed", message=frappe.get_traceback())
		settings.db_set("last_sync_time", now_datetime())
		settings.db_set("last_sync_status", "Failed")
		settings.db_set("last_error_message", str(e))
		raise
