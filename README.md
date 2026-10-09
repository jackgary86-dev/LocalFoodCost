# LocalFoodCost

This week's grocery deals in Longview, TX (ZIP 75601), as a phone-friendly web page:
**https://jackgary86-dev.github.io/LocalFoodCost/**

- **Top 5 deals this week**: the biggest savings against the normal price.
- **Every price** for shrimp, fish, crab, milk, eggs, beef, chicken, pork, bacon, sausage and turkey at Longview stores, with each store's address.
- **Normal price** for each item: once an item has 4 earlier weeks of price history, its own Longview median price; until then, the BLS average price for the region where the government tracks it, otherwise the median everyday price at Longview's Walmart and Sam's Club.
- **Price history** badges: "Lowest in N weeks" and "Usually $X" for items seen in earlier weeks.
- **Store distance**: each deal shows how far the nearest location is, with its address. A "Stores within" setting (default 15 miles) hides chains with no location inside it, and "Show anyway" brings them back. Locations come from OpenStreetMap; Longview's are saved in the page by the weekly build, other ZIPs look them up live.
- **Package sizes and conditions** read from each ad's description: sizes give a price per pound, and badges show coupons, store cards, limits and must-buy deals. A filter hides deals that need a coupon, card or membership.
- **Any ZIP code**: type a ZIP and press "Update prices" to load that area's weekly ads.
- **Watch list**: save foods you always buy (shrimp, ribeye, eggs…) and see this week's best price on each at the top of the page.
- **"A or B" deals** are compared with the cheaper option's normal price, so a "Chicken Breasts or Thighs" sale isn't measured against the breast price alone.
- **Install as an app**: Add to Home Screen gives a proper icon and full-screen view, and the app opens with the last prices it loaded even without a connection (`manifest.webmanifest`, `sw.js`, `icons/`; redraw the icons with `python -I tools/make_icons.py`).
- **Shopping list**: tick deals to build a trip grouped by store, nearest first, with each item's conditions, an estimate of how much you save against normal prices, and a **Copy list** button (opens the share sheet on phones). Saved in your browser.

## Where the prices come from

| Source | Stores | Refreshed |
|---|---|---|
| Weekly ads listed on Flipp for ZIP 75601 | Brookshire's, Super 1 Foods, FRESH by Brookshire's, Kroger, ALDI, Albertsons, Sprouts, Dollar General, Family Dollar | Every Wednesday by GitHub Actions |
| Store websites (`everyday.json`) | Walmart (E Loop 281), Sam's Club (#6422), Dollar General, Natural Grocers | Weekly when the owner's computer runs the browser refresh |

Stores whose ads list ZIP 75601 but that have no Longview location (H-E-B, Spring Market, Costco) are left out.

## Files

- `index.html`: the whole site. The data lives in four constants written by `build.py`: `LONGVIEW`, `WEEK_OF`, `STORE_LOCS` and `HISTORY`.
- `build.py`: fetches this week's ads and each item's ad detail (sizes, coupons, limits), merges `everyday.json`, saves price history, refreshes Longview store locations, rewrites those constants and prints the Top 5. Run `python -I build.py`.
- `everyday.json`: everyday prices collected from store websites.
- `history/`: one file per ad week (`YYYY-MM-DD.json`) with each item's price, written by `build.py`. The page gets the last 26 weeks for the items it shows.
- `verified.json`: corrections from checking store websites by hand (package sizes, regular prices, mismatches). `build.py` applies them only for the ad week they were checked, so they drop off when the next ad starts.
- `tests/test_build.py`: checks the rules `build.py` uses to read ads (food types, package sizes, coupons and limits). Run `python -m unittest discover -s tests`.
- `.github/workflows/weekly-refresh.yml`: runs the tests and `build.py` every Wednesday and commits the result.

Prices are a snapshot. Check the store's own ad before you shop.
