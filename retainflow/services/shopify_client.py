import frappe
import requests
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.password import set_encrypted_password


def _get_access_token(settings):
	"""Return a valid token, requesting a new one if the stored one is
	missing or expires within 5 minutes."""
	if settings.token_expires_at and get_datetime(settings.token_expires_at) > add_to_date(
		now_datetime(), minutes=5
	):
		return settings.get_password("access_token")

	resp = requests.post(
		f"https://{settings.store_domain}/admin/oauth/access_token",
		json={
			"client_id": settings.client_id,
			"client_secret": settings.get_password("client_secret"),
			"grant_type": "client_credentials",
		},
		timeout=30,
	)
	resp.raise_for_status()
	data = resp.json()

	token = data["access_token"]
	# Password fields must be written with this helper so they get encrypted
	set_encrypted_password("Shopify Settings", "Shopify Settings", token, "access_token")
	frappe.db.set_single_value(
		"Shopify Settings",
		"token_expires_at",
		add_to_date(now_datetime(), seconds=data.get("expires_in", 86399)),
	)
	return token


def graphql(query, variables=None):
	"""Run a GraphQL query against the Shopify Admin API."""
	settings = frappe.get_single("Shopify Settings")
	token = _get_access_token(settings)
	resp = requests.post(
		f"https://{settings.store_domain}/admin/api/{settings.api_version}/graphql.json",
		json={"query": query, "variables": variables or {}},
		headers={"X-Shopify-Access-Token": token},
		timeout=30,
	)
	resp.raise_for_status()
	body = resp.json()
	if body.get("errors"):
		frappe.throw(f"Shopify returned errors: {body['errors']}")
	return body["data"]


def connect_shopify():
	"""Validate the connection (from section 15 of your document)."""
	data = graphql("{ shop { name myshopifyDomain currencyCode ianaTimezone } }")
	return data["shop"]
