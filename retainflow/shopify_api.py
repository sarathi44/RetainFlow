import json
import re

import frappe
import requests
from frappe.utils import flt, get_datetime, now_datetime

DEFAULT_API_VERSION = "2024-10"


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


def get_access_token(shop_url: str, client_id: str, client_secret: str) -> str:
	"""
	Exchanges the app's Client ID / Client Secret for a short-lived Admin API
	access token using Shopify's client credentials grant.
	"""
	clean_url = clean_shopify_url(shop_url)
	if not clean_url:
		frappe.throw("Shopify Store URL cannot be empty.")
	if not client_id or not client_secret:
		frappe.throw("Client ID and Client API Secret cannot be empty.")

	cache_key = f"retainflow:shopify_token:{clean_url}"
	token = frappe.cache().get_value(cache_key)
	if token:
		return token

	endpoint = f"https://{clean_url}/admin/oauth/access_token"
	payload = {
		"grant_type": "client_credentials",
		"client_id": client_id.strip(),
		"client_secret": client_secret.strip(),
	}

	try:
		response = requests.post(endpoint, json=payload, timeout=15)
	except requests.RequestException as e:
		frappe.throw(f"Network error while authenticating with Shopify: {e!s}")

	if response.status_code != 200:
		frappe.throw(
			f"Shopify authentication failed ({response.status_code}). "
			f"Please check the Client ID and Client API Secret. Response: {response.text}"
		)

	token = response.json().get("access_token")
	if not token:
		frappe.throw("Shopify did not return an access token for the given client credentials.")

	# Cache briefly so a sync run does not re-authenticate on every request
	frappe.cache().set_value(cache_key, token, expires_in_sec=300)
	return token


def get_shopify_headers(access_token: str) -> dict:
	return {
		"Content-Type": "application/json",
		"X-Shopify-Access-Token": access_token.strip() if access_token else "",
	}


def test_shopify_connection(
	shop_url: str, client_id: str, client_secret: str, api_version: str = DEFAULT_API_VERSION
) -> dict:
	"""
	Tests connectivity to Shopify using the shop.json endpoint with client credentials.
	"""
	access_token = get_access_token(shop_url, client_id, client_secret)
	clean_url = clean_shopify_url(shop_url)
	endpoint = f"https://{clean_url}/admin/api/{api_version}/shop.json"
	headers = get_shopify_headers(access_token)

	try:
		response = requests.get(endpoint, headers=headers, timeout=15)
	except requests.RequestException as e:
		frappe.throw(f"Network error while connecting to Shopify: {e!s}")

	if response.status_code == 401:
		frappe.throw(
			"Shopify Authentication Failed (401 Unauthorized). Please check your Client ID and Client API Secret."
		)
	elif response.status_code == 403:
		frappe.throw(
			"Shopify Access Forbidden (403). Make sure your app has the required read/write permissions (scopes)."
		)
	elif response.status_code == 404:
		frappe.throw(f"Shopify Store not found at {clean_url} (404 Not Found). Please verify the store URL.")
	elif response.status_code != 200:
		frappe.throw(
			f"Failed to connect to Shopify. Status Code: {response.status_code}. Response: {response.text}"
		)

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
	client_id: str,
	client_secret: str,
	api_version: str = DEFAULT_API_VERSION,
	limit: int = 50,
	status: str = "any",
) -> list[dict]:
	"""
	Fetches orders from Shopify using client credentials.
	"""
	access_token = get_access_token(shop_url, client_id, client_secret)
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
		frappe.throw(f"Error fetching orders from Shopify: {e!s}")

	if response.status_code != 200:
		frappe.throw(f"Shopify Orders API returned error {response.status_code}: {response.text}")

	data = response.json()
	return data.get("orders", [])


def fetch_shopify_products(
	shop_url: str,
	client_id: str,
	client_secret: str,
	api_version: str = DEFAULT_API_VERSION,
	limit: int = 50,
) -> list[dict]:
	"""
	Fetches products (with variants and images inline) from Shopify
	using client credentials.
	"""
	access_token = get_access_token(shop_url, client_id, client_secret)
	clean_url = clean_shopify_url(shop_url)
	endpoint = f"https://{clean_url}/admin/api/{api_version}/products.json"
	headers = get_shopify_headers(access_token)
	params = {"limit": min(limit, 250)}

	try:
		response = requests.get(endpoint, headers=headers, params=params, timeout=25)
	except requests.RequestException as e:
		frappe.throw(f"Error fetching products from Shopify: {e!s}")

	if response.status_code != 200:
		frappe.throw(f"Shopify Products API returned error {response.status_code}: {response.text}")

	data = response.json()
	return data.get("products", [])


def fetch_shopify_customers(
	shop_url: str,
	client_id: str,
	client_secret: str,
	api_version: str = DEFAULT_API_VERSION,
	limit: int = 50,
) -> list[dict]:
	"""
	Fetches customers (with addresses inline) from Shopify
	using client credentials.
	"""
	access_token = get_access_token(shop_url, client_id, client_secret)
	clean_url = clean_shopify_url(shop_url)
	endpoint = f"https://{clean_url}/admin/api/{api_version}/customers.json"
	headers = get_shopify_headers(access_token)
	params = {"limit": min(limit, 250)}

	try:
		response = requests.get(endpoint, headers=headers, params=params, timeout=25)
	except requests.RequestException as e:
		frappe.throw(f"Error fetching customers from Shopify: {e!s}")

	if response.status_code != 200:
		frappe.throw(f"Shopify Customers API returned error {response.status_code}: {response.text}")

	data = response.json()
	return data.get("customers", [])


def format_variant_option_values(variant: dict) -> str:
	"""
	Combines Shopify option fields into a readable string, e.g. 'Blue / M'.
	"""
	options = [variant.get(f"option{i}") for i in range(1, 4)]
	options = [o for o in options if o and o != "Default Title"]
	return " / ".join(options)


def sync_single_product(product_data: dict, shop_url: str) -> str:
	"""
	Upserts a single Shopify product dictionary (with variants) into the
	Frappe 'Shopify Product' doctype. Returns the Shopify Product ID.
	"""
	product_id = str(product_data.get("id") or "")
	if not product_id:
		return ""

	clean_url = clean_shopify_url(shop_url)
	# storefront_url = f"https://{clean_url}/products/{product_data.get('handle')}"
	admin_url = f"https://{clean_url}/admin/products/{product_id}"

	featured_image = (product_data.get("image") or {}).get("src")

	# Total stock quantity across all variants
	inventory_stock_qty = sum(
		int(variant.get("inventory_quantity") or 0) for variant in product_data.get("variants", [])
	)

	# Check if document already exists
	if frappe.db.exists("Shopify Product", product_id):
		product_doc = frappe.get_doc("Shopify Product", product_id)
	else:
		product_doc = frappe.new_doc("Shopify Product")
		product_doc.shopify_product_id = product_id

	product_doc.product_title = product_data.get("title") or f"Product {product_id}"
	product_doc.handle = product_data.get("handle") or ""
	product_doc.status = product_data.get("status") or "active"
	product_doc.vendor = product_data.get("vendor") or ""
	product_doc.product_type = product_data.get("product_type") or ""
	product_doc.tags = product_data.get("tags") or ""
	product_doc.inventory_stock_qty = inventory_stock_qty
	product_doc.featured_image = featured_image or ""
	product_doc.created_at_shopify = parse_shopify_datetime(product_data.get("created_at"))
	product_doc.published_at = parse_shopify_datetime(product_data.get("published_at"))
	product_doc.updated_at_shopify = parse_shopify_datetime(product_data.get("updated_at"))
	product_doc.shopify_product_url = admin_url
	product_doc.raw_json = json.dumps(product_data, indent=2)

	product_doc.variants = []
	for variant in product_data.get("variants", []):
		product_doc.append(
			"variants",
			{
				"variant_title": variant.get("title") or "Default Title",
				"shopify_variant_id": str(variant.get("id") or ""),
				"sku": variant.get("sku") or "",
				"price": flt(variant.get("price")),
				"compare_at_price": flt(variant.get("compare_at_price")),
				"inventory_quantity": variant.get("inventory_quantity") or 0,
				"option_values": format_variant_option_values(variant),
				"barcode": variant.get("barcode") or "",
			},
		)

	if product_doc.is_new():
		product_doc.insert(ignore_permissions=True)
	else:
		product_doc.save(ignore_permissions=True)

	return product_id


@frappe.whitelist()
def sync_products(limit: int = 50) -> dict:
	"""
	Product sync runner called from Settings or Scheduler.
	"""
	shop_url, client_id, client_secret = get_configured_credentials()
	settings = frappe.get_single("Shopify Settings")
	sync_limit = limit or 50
	start_time = now_datetime()

	try:
		products = fetch_shopify_products(
			shop_url=shop_url,
			client_id=client_id,
			client_secret=client_secret,
			api_version=DEFAULT_API_VERSION,
			limit=sync_limit,
		)
		synced_count = 0
		for product_data in products:
			sync_single_product(product_data, shop_url)
			synced_count += 1

		frappe.db.commit()

		total_products = frappe.db.count("Shopify Product")
		settings.db_set("last_product_sync_time", now_datetime())
		settings.db_set("total_products_synced", total_products)

		message = f"Successfully synced {synced_count} products from Shopify."
		create_sync_log(
			sync_type="Products",
			status="Success",
			start_time=start_time,
			synced_count=synced_count,
			total_records=total_products,
			sync_limit=sync_limit,
			message=message,
		)
		frappe.db.commit()

		return {
			"status": "success",
			"synced_count": synced_count,
			"total_products": total_products,
			"message": message,
		}
	except Exception as e:
		frappe.log_error(title="Shopify Product Sync Failed", message=frappe.get_traceback())
		create_sync_log(
			sync_type="Products",
			status="Failed",
			start_time=start_time,
			sync_limit=sync_limit,
			message=str(e),
			error=frappe.get_traceback(),
		)
		frappe.db.commit()
		raise


def sync_single_customer(customer_data: dict, shop_url: str) -> str:
	"""
	Upserts a single Shopify customer dictionary (with addresses) into the
	Frappe 'Shopify Customer' doctype. Returns the Shopify Customer ID.
	"""
	customer_id = str(customer_data.get("id") or "")
	if not customer_id:
		return ""

	clean_url = clean_shopify_url(shop_url)
	admin_url = f"https://{clean_url}/admin/customers/{customer_id}"

	customer_name = f"{customer_data.get('first_name') or ''} {customer_data.get('last_name') or ''}".strip()
	if not customer_name:
		customer_name = customer_data.get("email") or f"Customer {customer_id}"

	default_address_id = (customer_data.get("default_address") or {}).get("id")

	# Check if document already exists
	if frappe.db.exists("Shopify Customer", customer_id):
		customer_doc = frappe.get_doc("Shopify Customer", customer_id)
	else:
		customer_doc = frappe.new_doc("Shopify Customer")
		customer_doc.shopify_customer_id = customer_id

	customer_doc.customer_name = customer_name
	customer_doc.email = customer_data.get("email") or ""
	customer_doc.phone = customer_data.get("phone") or ""
	customer_doc.state = customer_data.get("state") or "enabled"
	customer_doc.verified_email = 1 if customer_data.get("verified_email") else 0
	customer_doc.accepts_marketing = 1 if customer_data.get("accepts_marketing") else 0
	customer_doc.tags = customer_data.get("tags") or ""
	customer_doc.orders_count = customer_data.get("orders_count") or 0
	customer_doc.total_spent = flt(customer_data.get("total_spent"))
	customer_doc.currency = customer_data.get("currency") or ""
	customer_doc.note = customer_data.get("note") or ""
	customer_doc.created_at_shopify = parse_shopify_datetime(customer_data.get("created_at"))
	customer_doc.updated_at_shopify = parse_shopify_datetime(customer_data.get("updated_at"))
	customer_doc.shopify_customer_url = admin_url
	customer_doc.raw_json = json.dumps(customer_data, indent=2)

	customer_doc.addresses = []
	for address in customer_data.get("addresses", []):
		customer_doc.append(
			"addresses",
			{
				"customer_address_name": address.get("name") or "",
				"address1": address.get("address1") or "",
				"address2": address.get("address2") or "",
				"city": address.get("city") or "",
				"province": address.get("province") or "",
				"zip": address.get("zip") or "",
				"country": address.get("country") or "",
				"phone": address.get("phone") or "",
				"is_default": 1 if address.get("id") == default_address_id else 0,
			},
		)

	if customer_doc.is_new():
		customer_doc.insert(ignore_permissions=True)
	else:
		customer_doc.save(ignore_permissions=True)

	return customer_id


@frappe.whitelist()
def sync_customers(limit: int = 50) -> dict:
	"""
	Customer sync runner called from Settings or Scheduler.
	"""
	shop_url, client_id, client_secret = get_configured_credentials()
	settings = frappe.get_single("Shopify Settings")
	sync_limit = limit or 50
	start_time = now_datetime()

	try:
		customers = fetch_shopify_customers(
			shop_url=shop_url,
			client_id=client_id,
			client_secret=client_secret,
			api_version=DEFAULT_API_VERSION,
			limit=sync_limit,
		)
		synced_count = 0
		for customer_data in customers:
			sync_single_customer(customer_data, shop_url)
			synced_count += 1

		frappe.db.commit()

		total_customers = frappe.db.count("Shopify Customer")
		settings.db_set("last_customer_sync_time", now_datetime())
		settings.db_set("total_customers_synced", total_customers)

		message = f"Successfully synced {synced_count} customers from Shopify."
		create_sync_log(
			sync_type="Customers",
			status="Success",
			start_time=start_time,
			synced_count=synced_count,
			total_records=total_customers,
			sync_limit=sync_limit,
			message=message,
		)
		frappe.db.commit()

		return {
			"status": "success",
			"synced_count": synced_count,
			"total_customers": total_customers,
			"message": message,
		}
	except Exception as e:
		frappe.log_error(title="Shopify Customer Sync Failed", message=frappe.get_traceback())
		create_sync_log(
			sync_type="Customers",
			status="Failed",
			start_time=start_time,
			sync_limit=sync_limit,
			message=str(e),
			error=frappe.get_traceback(),
		)
		frappe.db.commit()
		raise


def get_configured_credentials() -> tuple[str, str, str]:
	"""
	Reads and validates Shopify credentials from Shopify Settings.
	Returns (shop_url, client_id, client_secret).
	"""
	settings = frappe.get_single("Shopify Settings")
	shop_url = settings.shopify_url
	client_id = settings.client_id
	client_secret = None
	try:
		client_secret = settings.get_password("client_secret")
	except Exception:
		pass
	if not client_secret:
		client_secret = settings.client_secret

	if not shop_url or not client_id or not client_secret:
		frappe.throw("Please configure Shopify Store URL, Client ID and Client API Secret first.")

	return shop_url, client_id, client_secret


def create_sync_log(
	sync_type: str,
	status: str,
	start_time,
	synced_count: int = 0,
	total_records: int = 0,
	sync_limit: int | None = None,
	message: str = "",
	error: str | None = None,
	trigger: str = "Manual",
) -> str:
	"""
	Creates a Shopify Sync Log entry for a sync run and returns its name.
	"""
	end_time = now_datetime()
	log = frappe.get_doc(
		{
			"doctype": "Shopify Sync Log",
			"sync_type": sync_type,
			"status": status,
			"start_time": start_time,
			"end_time": end_time,
			"duration": max(0, (end_time - start_time).total_seconds()),
			"synced_count": synced_count or 0,
			"total_records": total_records or 0,
			"sync_limit": sync_limit,
			"trigger": trigger,
			"message": message or "",
			"error_detail": error or "",
		}
	)
	log.insert(ignore_permissions=True)
	return log.name


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
	customer_name = f"{customer_data.get('first_name') or ''} {customer_data.get('last_name') or ''}".strip()
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
	order_doc.subtotal_price = flt(
		order_data.get("current_subtotal_price") or order_data.get("subtotal_price")
	)
	order_doc.total_tax = flt(order_data.get("total_tax"))
	order_doc.total_discounts = flt(order_data.get("total_discounts"))
	order_doc.total_shipping = flt(
		order_data.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount") or 0.0
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


@frappe.whitelist()
def sync_orders(limit: int = 50) -> dict:
	"""
	Main sync runner called from Settings or Scheduler.
	"""
	shop_url, client_id, client_secret = get_configured_credentials()
	settings = frappe.get_single("Shopify Settings")
	sync_limit = limit or settings.order_sync_limit or 50
	start_time = now_datetime()

	try:
		orders = fetch_shopify_orders(
			shop_url=shop_url,
			client_id=client_id,
			client_secret=client_secret,
			api_version=DEFAULT_API_VERSION,
			limit=sync_limit,
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

		message = f"Successfully synced {synced_count} orders from Shopify."
		create_sync_log(
			sync_type="Orders",
			status="Success",
			start_time=start_time,
			synced_count=synced_count,
			total_records=total_orders,
			sync_limit=sync_limit,
			message=message,
		)
		frappe.db.commit()

		return {
			"status": "success",
			"synced_count": synced_count,
			"total_orders": total_orders,
			"message": message,
		}
	except Exception as e:
		frappe.log_error(title="Shopify Order Sync Failed", message=frappe.get_traceback())
		settings.db_set("last_sync_time", now_datetime())
		settings.db_set("last_sync_status", "Failed")
		settings.db_set("last_error_message", str(e))
		create_sync_log(
			sync_type="Orders",
			status="Failed",
			start_time=start_time,
			sync_limit=sync_limit,
			message=str(e),
			error=frappe.get_traceback(),
		)
		frappe.db.commit()
		raise
