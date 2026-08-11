import { useEffect } from "react";

// Kept in sync with the <title> in index.html, which is what a crawler and a
// cold page load see before React mounts.
const SITE_NAME = "SHPE UH";
const DEFAULT_TITLE = "SHPE University of Houston — Leading Hispanics in STEM";

/**
 * Sets the browser tab title for a page.
 *
 * index.html carries one static title for every route, so without this the tab,
 * the browser history, and every bookmark read the same thing on /shop as on
 * /calendar. Call it once near the top of a page component:
 *
 *   useDocumentTitle("Calendar")   ->  "Calendar | SHPE UH"
 *   useDocumentTitle()             ->  the full site title (home page)
 *
 * Pages whose title depends on fetched data should pass a fallback rather than
 * a falsy value, so the tab never flashes the site default mid-load:
 *
 *   useDocumentTitle(product ? product.name : "Shop")
 *
 * Deliberately does not restore the previous title on unmount — every route
 * sets its own, so the next page's effect overwrites this one anyway.
 */
export default function useDocumentTitle(title) {
	useEffect(() => {
		document.title = title ? `${title} | ${SITE_NAME}` : DEFAULT_TITLE;
	}, [title]);
}
