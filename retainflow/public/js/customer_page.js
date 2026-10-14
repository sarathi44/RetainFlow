/**
 * RetainFlow · Customer (Vue 3)
 * Single Shopify Customer record with loyalty metrics, addresses and
 * recent orders, served by retainflow.api.get_customer.
 */
(function () {
	const el = document.getElementById("rf-customer");
	if (!el) return;
	if (typeof Vue === "undefined") {
		el.innerHTML =
			'<div style="padding:40px;text-align:center">Vue failed to load. Run <code>bench build</code> and retry.</div>';
		return;
	}

	const { createApp, reactive, onMounted } = Vue;

	const SEGMENT_TONES = {
		New: "blue",
		Repeat: "green",
		VIP: "purple",
		"At Risk": "amber",
		Inactive: "red",
		"No eligible orders": "gray",
	};
	const TIER_TONES = { Bronze: "bronze", Silver: "gray", Gold: "gold" };

	// RetainFlow side nav
	const NAV = [
		{ label: "Dashboard", href: "/desk/retainflow", key: "dash" },
		{ label: "Customers", href: "/desk/shopify-customer", key: "cust" },
	];
	const STATUS_TONES = {
		paid: "green",
		fulfilled: "green",
		enabled: "green",
		pending: "amber",
		partially_paid: "amber",
		partial: "amber",
		invited: "amber",
		refunded: "red",
		voided: "red",
		cancelled: "red",
		disabled: "gray",
	};

	const currencyFormatters = {};
	function fmtCurrency(value, currency) {
		currency = currency || "INR";
		if (!currencyFormatters[currency]) {
			currencyFormatters[currency] = new Intl.NumberFormat("en-IN", {
				style: "currency",
				currency: currency,
				maximumFractionDigits: 0,
			});
		}
		return currencyFormatters[currency].format(value || 0);
	}

	function fmtPoints(value) {
		return (value || 0).toLocaleString("en-IN");
	}

	function fmtDate(value) {
		if (!value) return "—";
		const d = new Date(value.replace(" ", "T"));
		if (isNaN(d)) return value;
		return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
	}

	function fmtLastOrder(days) {
		if (days === null || days === undefined) return "No eligible orders";
		if (days === 0) return "Today";
		if (days === 1) return "Yesterday";
		return `${days} days ago`;
	}

	function fmtStatus(value) {
		if (!value) return "—";
		return value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
	}

	function statusTone(value) {
		return STATUS_TONES[(value || "").toLowerCase()] || "gray";
	}

	async function apiCall(method, params) {
		const csrf = el.dataset.csrfToken || "";
		const res = await fetch(`/api/method/${method}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": csrf,
				Accept: "application/json",
			},
			body: JSON.stringify(params || {}),
		});
		const data = await res.json();
		if (!res.ok || data.exc) {
			const message =
				(data &&
					data._server_messages &&
					JSON.parse(data._server_messages)[0] &&
					JSON.parse(JSON.parse(data._server_messages)[0]).message) ||
				`Request failed (${res.status})`;
			throw new Error(message || `Request failed (${res.status})`);
		}
		return data.message;
	}

	createApp({
		setup() {
			const state = reactive({
				loading: true,
				error: "",
				store: { shop_name: "RetainFlow Dev Store", currency: "INR" },
				customer: null,
				orders: [],
				ledger: [],
			});

			async function load() {
				state.loading = true;
				state.error = "";
				try {
					const data = await apiCall("retainflow.api.get_customer", {
						name: el.dataset.customer,
					});
					state.store = data.store || state.store;
					state.customer = data.customer;
					state.orders = data.orders || [];
					state.ledger = data.ledger || [];
					document.title = `${data.customer.name} · RetainFlow`;
				} catch (e) {
					state.error = e.message || "Could not load customer";
				} finally {
					state.loading = false;
				}
			}

			onMounted(load);

			return {
				state,
				SEGMENT_TONES,
				TIER_TONES,
				NAV,
				fmtCurrency,
				fmtPoints,
				fmtDate,
				fmtLastOrder,
				fmtStatus,
				statusTone,
				load,
			};
		},
		template: `
		<div style="min-height: 100vh; display: flex; flex-direction: column">
			<header style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; padding: 10px 16px; background: #1a1a1a; color: #e3e3e3">
				<div style="display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 600; color: #fff">
					<span style="display: inline-flex; width: 26px; height: 26px; border-radius: 6px; background: #3a3a3a; align-items: center; justify-content: center; font-size: 11px">S</span>
					<span>Shopify admin</span>
					<span class="rf-badge" style="background: #333; color: #d4d4d4">Host frame</span>
				</div>
				<div style="margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 13px">
					<span style="display: inline-flex; width: 28px; height: 28px; border-radius: 8px; background: #36a47a; color: #fff; align-items: center; justify-content: center; font-weight: 700; font-size: 11px">RF</span>
					<span>{{ state.store.shop_name }}</span>
				</div>
			</header>
			<div style="display: flex; flex-wrap: wrap; flex: 1; align-items: stretch">
				<nav aria-label="RetainFlow" style="flex: 1 1 200px; max-width: 240px; background: #ebebeb; padding: 12px 10px; display: flex; flex-direction: column; gap: 2px">
					<a v-for="n in NAV" :key="n.key" class="rf-nav" :class="{ on: n.key === 'cust' }" :href="n.href">{{ n.label }}</a>
				</nav>
				<main style="flex: 999 1 560px; min-width: 0; padding: 8px; display: flex; flex-direction: column">
				<div style="flex: 1; background: #fff; border-radius: 12px; border: 1px solid #e3e3e3; display: flex; flex-direction: column; min-width: 0">
					<div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 12px 20px; border-bottom: 1px solid #ededed">
						<div style="display: flex; align-items: center; gap: 8px; flex: 1 1 260px; font-size: 14px; min-width: 0">
							<span style="display: inline-flex; width: 24px; height: 24px; border-radius: 6px; background: #171717; color: #fff; align-items: center; justify-content: center; font-size: 10px; font-weight: 700">RF</span>
							<span class="rf-muted">RetainFlow</span><span class="rf-muted">/</span>
							<a href="/desk/shopify-customer" class="rf-muted" style="text-decoration: none">Customers</a><span class="rf-muted">/</span>
							<strong style="font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ state.customer ? state.customer.name : '…' }}</strong>
						</div>
						<div style="display: flex; gap: 8px; flex-wrap: wrap">
							<a class="rf-btn" href="/desk/shopify-customer">Back to customers</a>
							<a v-if="state.customer && state.customer.shopify_customer_url" class="rf-btn pri" :href="state.customer.shopify_customer_url" target="_blank" rel="noopener">Open in Shopify</a>
						</div>
					</div>

					<div v-if="state.error" class="rf-badge red" style="margin: 12px 24px 0; white-space: normal; height: auto; padding: 8px 12px">
						{{ state.error }}
					</div>

					<div v-if="state.loading" class="rf-muted" style="padding: 60px 20px; text-align: center">Loading customer…</div>

					<div v-else-if="state.customer" style="width: 100%; max-width: 1200px; margin: 0 auto; padding: 24px 24px 48px; display: flex; flex-direction: column; gap: 16px">
						<div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
							<h1 style="margin: 0; font-size: 20px; font-weight: 650">{{ state.customer.name }}</h1>
							<span class="rf-badge" :class="TIER_TONES[state.customer.tier]">{{ state.customer.tier }}</span>
							<span v-for="s in state.customer.segments" :key="s" class="rf-badge" :class="SEGMENT_TONES[s]">{{ s }}</span>
						</div>
						<div v-if="state.customer.tier_benefit" class="rf-muted" style="font-size: 13px; margin-top: -8px">
							{{ state.customer.tier }} benefit: {{ state.customer.tier_benefit }}
						</div>
						<div v-if="state.customer.downgrade_to" class="rf-badge amber" style="white-space: normal; height: auto; padding: 8px 12px; align-self: flex-start">
							Below the {{ state.customer.tier }} threshold · moves down to {{ state.customer.downgrade_to }} on {{ fmtDate(state.customer.downgrade_due) }} unless they requalify
						</div>
						<div v-if="state.customer.nudge" class="rf-badge blue" style="white-space: normal; height: auto; padding: 8px 12px; align-self: flex-start">
							Almost there: {{ state.customer.nudge.basis === 'points' ? fmtPoints(state.customer.nudge.gap) + ' points' : fmtCurrency(state.customer.nudge.gap, state.customer.currency) }} to {{ state.customer.nudge.next_tier }}
						</div>

						<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px">
							<div class="rf-card" style="padding: 14px 16px">
								<div class="rf-lbl">Eligible orders</div>
								<div class="num" style="font-size: 22px; font-weight: 650; margin-top: 4px">{{ state.customer.orders }}</div>
							</div>
							<div class="rf-card" style="padding: 14px 16px">
								<div class="rf-lbl">Eligible spend</div>
								<div class="num" style="font-size: 22px; font-weight: 650; margin-top: 4px">{{ fmtCurrency(state.customer.spend, state.customer.currency) }}</div>
							</div>
							<div class="rf-card" style="padding: 14px 16px">
								<div class="rf-lbl">Points</div>
								<div class="num" style="font-size: 22px; font-weight: 650; margin-top: 4px">{{ fmtPoints(state.customer.points) }}</div>
							</div>
							<div class="rf-card" style="padding: 14px 16px">
								<div class="rf-lbl">Last order</div>
								<div style="font-size: 22px; font-weight: 650; margin-top: 4px">{{ fmtLastOrder(state.customer.days_since_last) }}</div>
							</div>
						</div>

						<div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start">
							<div style="flex: 999 1 480px; min-width: 0; display: flex; flex-direction: column; gap: 16px">
								<div class="rf-card" style="overflow: hidden">
									<div style="padding: 14px 16px; font-weight: 600; font-size: 14px; border-bottom: 1px solid #ededed">Recent orders</div>
									<div style="overflow-x: auto">
										<table v-if="state.orders.length" style="width: 100%; border-collapse: collapse">
											<thead>
												<tr>
													<th class="rf-th">Order</th>
													<th class="rf-th">Date</th>
													<th class="rf-th">Payment</th>
													<th class="rf-th">Fulfillment</th>
													<th class="rf-th" style="text-align: right">Total</th>
												</tr>
											</thead>
											<tbody>
												<tr v-for="o in state.orders" :key="o.name" class="rf-row">
													<td class="rf-td">
														<a v-if="o.url" class="rf-name" :href="o.url" target="_blank" rel="noopener">{{ o.name }}</a>
														<span v-else>{{ o.name }}</span>
														<span v-if="o.order_status === 'cancelled'" class="rf-badge red" style="margin-left: 6px">Cancelled</span>
													</td>
													<td class="rf-td rf-muted">{{ fmtDate(o.date) }}</td>
													<td class="rf-td"><span class="rf-badge" :class="statusTone(o.financial_status)">{{ fmtStatus(o.financial_status) }}</span></td>
													<td class="rf-td"><span class="rf-badge" :class="statusTone(o.fulfillment_status)">{{ fmtStatus(o.fulfillment_status) }}</span></td>
													<td class="rf-td num" style="text-align: right">{{ fmtCurrency(o.total, o.currency) }}</td>
												</tr>
											</tbody>
										</table>
										<div v-else class="rf-muted" style="padding: 28px 16px; text-align: center; font-size: 13px">No synced orders for this customer yet.</div>
									</div>
								</div>

								<div class="rf-card" style="overflow: hidden">
									<div style="padding: 14px 16px; font-weight: 600; font-size: 14px; border-bottom: 1px solid #ededed">Points ledger</div>
									<div style="overflow-x: auto">
										<table v-if="state.ledger.length" style="width: 100%; border-collapse: collapse">
											<thead>
												<tr>
													<th class="rf-th">Date</th>
													<th class="rf-th">Order</th>
													<th class="rf-th" style="text-align: right">Eligible amount</th>
													<th class="rf-th" style="text-align: right">Rate</th>
													<th class="rf-th" style="text-align: right">Points</th>
												</tr>
											</thead>
											<tbody>
												<tr v-for="e in state.ledger" :key="e.order" class="rf-row">
													<td class="rf-td rf-muted">{{ fmtDate(e.date) }}</td>
													<td class="rf-td">{{ e.order }}</td>
													<td class="rf-td num" style="text-align: right">{{ fmtCurrency(e.eligible_amount, e.currency) }}</td>
													<td class="rf-td num rf-muted" style="text-align: right">{{ e.rate }} / unit<span v-if="e.multiplier !== 1"> × {{ e.multiplier }}</span></td>
													<td class="rf-td num" style="text-align: right; font-weight: 600">+{{ fmtPoints(e.points) }}</td>
												</tr>
											</tbody>
										</table>
										<div v-else class="rf-muted" style="padding: 28px 16px; text-align: center; font-size: 13px">No points posted yet. Paid, non-cancelled orders earn points.</div>
									</div>
								</div>

								<div v-if="state.customer.note" class="rf-card" style="padding: 14px 16px">
									<div style="font-weight: 600; font-size: 14px; margin-bottom: 6px">Note</div>
									<div style="font-size: 13px; white-space: pre-wrap">{{ state.customer.note }}</div>
								</div>
							</div>

							<div style="flex: 1 1 280px; min-width: 0; display: flex; flex-direction: column; gap: 16px">
								<div class="rf-card" style="padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; font-size: 13px">
									<div style="font-weight: 600; font-size: 14px">Contact</div>
									<div>
										<div class="rf-lbl">Email</div>
										<div style="overflow-wrap: anywhere">
											{{ state.customer.email || 'Email not shared' }}
											<span v-if="state.customer.email && state.customer.verified_email" class="rf-badge green" style="margin-left: 4px">Verified</span>
										</div>
									</div>
									<div>
										<div class="rf-lbl">Phone</div>
										<div>{{ state.customer.phone || '—' }}</div>
									</div>
									<div>
										<div class="rf-lbl">Account</div>
										<div><span class="rf-badge" :class="statusTone(state.customer.state)">{{ fmtStatus(state.customer.state) }}</span></div>
									</div>
									<div>
										<div class="rf-lbl">Marketing</div>
										<div>{{ state.customer.accepts_marketing ? 'Subscribed' : 'Not subscribed' }}</div>
									</div>
									<div>
										<div class="rf-lbl">Shopify customer ID</div>
										<div class="num">{{ state.customer.shopify_id }}</div>
									</div>
									<div>
										<div class="rf-lbl">Customer since</div>
										<div>{{ fmtDate(state.customer.created_at_shopify) }}</div>
									</div>
								</div>

								<div class="rf-card" style="padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; font-size: 13px">
									<div style="font-weight: 600; font-size: 14px">Addresses</div>
									<div v-if="!state.customer.addresses.length" class="rf-muted">No addresses on file.</div>
									<div v-for="(a, i) in state.customer.addresses" :key="i">
										<div style="display: flex; align-items: center; gap: 6px">
											<strong style="font-weight: 600">{{ a.name || 'Address ' + (i + 1) }}</strong>
											<span v-if="a.is_default" class="rf-badge gray">Default</span>
										</div>
										<div v-for="line in a.lines" :key="line" class="rf-muted">{{ line }}</div>
										<div v-if="a.phone" class="rf-muted">{{ a.phone }}</div>
									</div>
								</div>

								<div v-if="state.customer.perks.length" class="rf-card" style="padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; font-size: 13px">
									<div style="font-weight: 600; font-size: 14px">{{ state.customer.tier }} perks</div>
									<div v-for="p in state.customer.perks" :key="p.label" style="display: flex; justify-content: space-between; gap: 12px">
										<span class="rf-muted">{{ p.label }}</span>
										<span style="text-align: right">{{ p.value }}</span>
									</div>
								</div>

								<div v-if="state.customer.tags.length" class="rf-card" style="padding: 14px 16px; display: flex; flex-direction: column; gap: 8px">
									<div style="font-weight: 600; font-size: 14px">Tags</div>
									<div style="display: flex; gap: 4px; flex-wrap: wrap">
										<span v-for="t in state.customer.tags" :key="t" class="rf-badge gray">{{ t }}</span>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
				</main>
			</div>
		</div>
		`,
	}).mount(el);
})();
