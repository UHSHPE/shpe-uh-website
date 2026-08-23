// Page controls for a list sliced by hooks/usePagination.
//
// Spread the hook's return straight in:  <Pagination {...pager} label="orders" />
//
// Exports only the component — a file that exports a component must not also
// export helpers, or react-refresh/only-export-components fails the build.

// A sliding band of numbers around the current page, with the first and last
// always reachable, so 40 pages doesn't render 40 buttons. The band widens near
// either end so the strip keeps a steady width instead of collapsing to
// "1 2 … 9" on the first page.
function pageWindow(page, pageCount) {
	if (pageCount <= 7) {
		return Array.from({ length: pageCount }, (_, i) => i + 1);
	}
	let from = Math.max(2, page - 1);
	let to = Math.min(pageCount - 1, page + 1);
	if (page <= 3) to = 4;
	if (page >= pageCount - 2) from = pageCount - 3;

	const out = [1];
	if (from > 2) out.push("gap");
	for (let p = from; p <= to; p++) out.push(p);
	if (to < pageCount - 1) out.push("gap");
	out.push(pageCount);
	return out;
}

// The secondary-button shape repeated across MyOrders / ShopManager / my-events.
const btn = {
	minWidth: "36px",
	borderRadius: "999px",
	padding: "7px 12px",
	fontSize: "13px",
	fontFamily: "inherit",
	fontWeight: 700,
	border: "1px solid var(--border-strong)",
	background: "#fff",
	color: "var(--shpe-blue)",
	cursor: "pointer",
};

// The active filter-pill fill, matching the pills above these same lists.
const btnActive = {
	...btn,
	border: "1px solid var(--shpe-blue)",
	background: "var(--shpe-blue)",
	color: "#fff",
	cursor: "default",
};

const btnDisabled = {
	...btn,
	color: "var(--muted-soft)",
	cursor: "not-allowed",
	opacity: 0.6,
};

export default function Pagination({
	page,
	pageCount,
	setPage,
	total,
	rangeStart,
	rangeEnd,
	label = "items",
}) {
	// A single page needs no controls, so short lists look exactly as they did
	// before — no call site has to guard this itself.
	if (pageCount <= 1) return null;

	const atStart = page <= 1;
	const atEnd = page >= pageCount;

	return (
		<nav
			aria-label="Pagination"
			style={{
				display: "flex",
				alignItems: "center",
				justifyContent: "space-between",
				gap: "12px",
				flexWrap: "wrap",
				marginTop: "14px",
			}}
		>
			<p style={{ margin: 0, fontSize: "12px", color: "var(--muted-soft)" }}>
				Showing {rangeStart}–{rangeEnd} of {total} {label}
			</p>

			<div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
				<button
					type="button"
					onClick={() => setPage(page - 1)}
					disabled={atStart}
					aria-label="Previous page"
					style={atStart ? btnDisabled : btn}
				>
					‹ Prev
				</button>

				{pageWindow(page, pageCount).map((p, i) =>
					p === "gap" ? (
						<span
							key={`gap-${i}`}
							aria-hidden="true"
							style={{ padding: "0 2px", fontSize: "13px", color: "var(--muted-soft)" }}
						>
							…
						</span>
					) : (
						<button
							key={p}
							type="button"
							onClick={() => setPage(p)}
							aria-label={`Page ${p}`}
							aria-current={p === page ? "page" : undefined}
							style={p === page ? btnActive : btn}
						>
							{p}
						</button>
					)
				)}

				<button
					type="button"
					onClick={() => setPage(page + 1)}
					disabled={atEnd}
					aria-label="Next page"
					style={atEnd ? btnDisabled : btn}
				>
					Next ›
				</button>
			</div>
		</nav>
	);
}
