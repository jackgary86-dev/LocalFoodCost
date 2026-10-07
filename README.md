# LocalFoodCost

This week's grocery deals in Longview, TX (ZIP 75601), as a phone-friendly web page:
**https://jackgary86-dev.github.io/LocalFoodCost/**

- **Top 5 deals this week**: the biggest savings against the normal price.
- **Every price** for shrimp, fish, crab, milk, eggs, beef, chicken, pork, bacon, sausage and turkey at Longview stores, with each store's address.
- **Normal price** for each item: the BLS average price for the South region where the government tracks it, otherwise the median everyday price at Longview's Walmart and Sam's Club.
- A shopping list that totals your trip by store (saved in your browser).

## Where the prices come from

| Source | Stores | Refreshed |
|---|---|---|
| Weekly ads listed on Flipp for ZIP 75601 | Brookshire's, Super 1 Foods, FRESH by Brookshire's, Kroger, ALDI, Albertsons, Sprouts, Dollar General, Family Dollar | Every Wednesday by GitHub Actions |
| Store websites (`everyday.json`) | Walmart (E Loop 281), Sam's Club (#6422), Dollar General, Natural Grocers | Weekly when the owner's computer runs the browser refresh |

Stores whose ads list ZIP 75601 but that have no Longview location (H-E-B, Spring Market, Costco) are left out.

## Files

- `index.html`: the whole site. The data lives in two constants, `LONGVIEW` and `WEEK_OF`.
- `build.py`: fetches this week's ads, merges `everyday.json`, rewrites those constants and prints the Top 5. Run `python -I build.py`.
- `everyday.json`: everyday prices collected from store websites.
- `verified.json`: corrections from checking store websites by hand (package sizes, regular prices, mismatches). `build.py` applies them only for the ad week they were checked, so they drop off when the next ad starts.
- `.github/workflows/weekly-refresh.yml`: runs `build.py` every Wednesday and commits the result.

Prices are a snapshot. Check the store's own ad before you shop.
