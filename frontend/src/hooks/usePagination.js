import { useState } from "react";

// Every paginated list in the app shows this many rows unless it passes its own
// pageSize. One constant so "up to 10 per page" is a single edit.
export const PAGE_SIZE = 10;

/**
 * Client-side pagination for a list that is already fully in memory.
 *
 * The list surfaces here all fetch everything and filter in the browser, so the
 * search boxes, filter pills, and count badges above them need the whole array.
 * This slices only what gets rendered, leaving those untouched:
 *
 *   const pager = usePagination(visible, { resetKey: `${tab}|${search}` });
 *   {pager.pageItems.map(...)}
 *   <Pagination {...pager} label="accounts" />
 *
 * `resetKey` is what sends the reader back to page 1 — a tab, a search string, a
 * filter pill, joined into one value. A change to `items` alone deliberately does
 * NOT reset, so marking a notification read leaves you where you were.
 *
 * `initialPage` moves that landing page off 1. The chair Events page uses it to
 * open on the next upcoming event in a chronological list that starts in August
 * (page 1 is the oldest events, which is the least useful place to land), while
 * leaving the reader free to page backwards into the past. Since the list is
 * fetched, the landing page isn't knowable on the first render — fold whatever
 * the computation depends on into `resetKey` (e.g. the loaded length) so the
 * reset fires once the data arrives.
 */
export default function usePagination(items, { pageSize = PAGE_SIZE, resetKey = "", initialPage = 1 } = {}) {
	const [page, setPage] = useState(initialPage);
	const [prevKey, setPrevKey] = useState(resetKey);

	const list = items ?? [];
	const total = list.length;
	const pageCount = Math.max(1, Math.ceil(total / pageSize));

	// Render-phase adjustment, NOT an effect — the lint config's
	// react-hooks/set-state-in-effect rule fails the build on setState inside a
	// useEffect body. Same shape as Header.jsx's prevPath.
	if (prevKey !== resetKey) {
		setPrevKey(resetKey);
		setPage(initialPage);
	}

	// Derived clamp, so this render is in range even when the list shrank under
	// the reader (a row removed, a filter narrowed). Converges in one pass: after
	// the re-render page === current, so nothing sets again.
	const current = Math.min(page, pageCount);
	if (current !== page) setPage(current);

	const start = (current - 1) * pageSize;

	return {
		pageItems: list.slice(start, start + pageSize),
		page: current,
		setPage,
		pageCount,
		total,
		rangeStart: total === 0 ? 0 : start + 1,
		rangeEnd: Math.min(start + pageSize, total),
	};
}
