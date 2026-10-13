# Copyright (c) 2026, Retainflow and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from retainflow.shopify_api import create_sync_log


class IntegrationTestShopifySyncLog(IntegrationTestCase):
	def tearDown(self):
		frappe.db.delete("Shopify Sync Log", {"sync_type": "Products"})
		frappe.db.commit()

	def test_create_sync_log_success(self):
		name = create_sync_log(
			sync_type="Products",
			status="Success",
			start_time=frappe.utils.now_datetime(),
			synced_count=5,
			total_records=5,
			sync_limit=50,
			message="Successfully synced 5 products from Shopify.",
		)

		log = frappe.get_doc("Shopify Sync Log", name)
		self.assertEqual(log.status, "Success")
		self.assertEqual(log.synced_count, 5)
		self.assertIsNotNone(log.end_time)
		self.assertGreaterEqual(log.duration, 0)
