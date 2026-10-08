"""Weekly refresh for the LocalFoodCost page (index.html).

Fetches this week's grocery-ad items that Flipp lists for ZIP 75601, merges them with the
everyday prices in everyday.json (Walmart, Sam's Club, Natural Grocers), and writes the result
into index.html as the LONGVIEW and WEEK_OF constants. Prints the new Top 5.

Usage: python -I build.py
"""
import collections
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import statistics
import subprocess
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ZIP = "75601"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
QUERIES = ["shrimp", "salmon", "tilapia", "catfish", "cod", "fish", "mahi", "crab", "crawfish", "lobster",
           "milk", "gallon milk", "eggs", "ground beef", "steak", "ribeye", "sirloin", "brisket", "roast", "chuck",
           "chicken", "chicken breast", "thighs", "drumsticks", "wings", "leg quarters", "pork", "pork chops",
           "pork tenderloin", "ribs", "bacon", "sausage", "ham", "turkey", "swai"]
# Flipp lists these ads for 75601, but the stores aren't in Longview (no H-E-B or Spring Market in town;
# the nearest Costco is in the Dallas area), so their deals are left out.
EXCLUDE = {"H-E-B", "Spring Market", "Costco"}
STORE_NAMES = {"Super 1 Foods & Discount Pharmacy": "Super 1 Foods", "Sprouts Farmers Market": "Sprouts"}
SKIP = re.compile(
    r"dog|cat\b|chip|cracker|candy|chocolate|soup|broth|noodle|ramen|seasoning|sauce|cereal|treat|almond|\boat|"
    r"coconut|soy|toy|shirt|lotion|shampoo|cheetos|dip|creamer|pizza|muscle milk|evaporated|condensed|ice cream|"
    r"cone|nestl|jerky|stew|beans|rinds|franks|vienna|meal|kit|deveiner|tinned|chunk|pasta|ravioli|fried rice|"
    r"lo mein|tso|cake|coffee|protein|shake|chowder|lunchmeat|bites|toppers|nuggets|patties|strips|tenders|"
    r"any.tizers|popcorn|fully cooked|deli|pulled|fried chicken|burgers|steam|breaded|battered|tempura|"
    r"marinated fish|cheap chicken|cream of|macaroni|steak-umm|filet mignon|primo taglio|crumbled|smart way|yogurt|"
    r"cheese|butter|sushi|salad|cajun fettucine|impossible|beyond meat", re.I)


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def category(name):
    n = name.lower()
    if "shrimp" in n and "salmon" not in n:
        return "Shrimp"
    if re.search(r"salmon|catfish|swai|pangasius|tilapia|\bcod\b|mahi|flounder|snapper|fish fillet", n):
        return "Fish"
    if re.search(r"crab|crawfish|lobster", n):
        return "Crab & crawfish"
    if re.search(r"\bmilk\b", n):
        return "Milk"
    if re.search(r"\beggs\b", n):
        return "Eggs"
    if re.search(r"bacon|sausage|bratwurst|boudin|hot link|chorizo|\bham\b|kielbasa", n):
        return "Bacon & sausage"
    if "turkey" in n:
        return "Turkey"
    if re.search(r"chicken|wing|thigh|drumstick|leg quarter", n):
        return "Chicken"
    if re.search(r"pork|ribs", n) and "beef" not in n:
        return "Pork"
    if re.search(r"beef|steak|brisket|ribeye|sirloin|chuck|roast", n):
        return "Beef"
    return None


def flipp_rows():
    flyers = get_json(f"https://flyers-ng.flippback.com/api/flipp/data?locale=en-us&postal_code={ZIP}&sid=1234567890")["flyers"]
    local = {f["id"]: f for f in flyers if "Groceries" in (f.get("categories") or [])}
    items = {}
    for q in QUERIES:
        url = ("https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code="
               f"{ZIP}&q={urllib.parse.quote(q)}")
        try:
            for it in get_json(url).get("items", []):
                if it.get("flyer_id") in local:
                    items[it["id"]] = it
        except Exception as e:  # one failed query shouldn't sink the week
            print(f"warning: query {q!r} failed: {e}")
    rows, seen = [], set()
    for it in items.values():
        name = (it.get("name") or "").replace("�", "").strip()
        price, story = it.get("current_price"), it.get("sale_story")
        if not name or SKIP.search(name):
            continue
        cat = category(name)
        # An item without a price is only useful when the ad says what the deal is (BOGO, % off).
        if not cat or (price is None and not re.search(r"buy one|% off|bogo", story or "", re.I)):
            continue
        post = (it.get("post_price_text") or "").lower()
        unit = "/lb" if re.search(r"\blb", post) else ("each" if re.search(r"\bea", post) else "")
        notes = []
        if story:
            notes.append(story.strip().capitalize() if price is None else story.strip().lower())
        if it.get("original_price"):
            notes.append(f"reg. ${it['original_price']:.2f}")
        store = STORE_NAMES.get(it["merchant_name"].strip(), it["merchant_name"].strip())
        if store in EXCLUDE:
            continue
        key = (store, name, price)
        if key in seen:
            continue
        seen.add(key)
        rows.append([cat, store, name, price, unit, "; ".join(notes), it["valid_from"][:10], it["valid_to"][:10],
                     price if unit == "/lb" else None,
                     f"https://flipp.com/en-us/longview-tx/item/{it['id']}?postal_code={ZIP}",
                     None, None, ad_conditions(it, None)])
    enrich_from_details(rows, {r[9]: iid for r, iid in zip(rows, (int(re.search(r"/item/(\d+)", r[9]).group(1)) for r in rows))})
    starts = collections.Counter(r[6] for r in rows)
    return rows, starts


# ---------- Deal conditions and package sizes from the ad ----------
LIMIT = re.compile(r"limit\s+(\d+(?:\.\d+)?)\s*(lbs?|pkgs?|packages?|items?|per|each|with)?", re.I)
MUST_BUY = re.compile(r"(?:must buy|when you buy|buy)\s+(\d+)", re.I)
PURCHASE = re.compile(r"with (?:a |an )?(?:additional )?\$(\d+)(?:\.\d\d)? (?:or more )?purchase", re.I)


def ad_conditions(it, detail):
    """Short labels for what a deal requires: coupons, store cards, limits, multi-buys."""
    post = (it.get("post_price_text") or "").lower()
    pre = (it.get("pre_price_text") or "").lower()
    story = (it.get("sale_story") or "").lower()
    disc = ((detail or {}).get("disclaimer_text") or "")
    out = []
    if (detail or {}).get("display_type") == 25:
        out.append("Coupon")
    if "digital coupon" in post or "digital coupon" in story:
        out.append("Digital coupon")
    elif "coupon" in post or "coupon" in story:
        out.append("Coupon")
    if "card" in post:
        out.append("Store card")
    if "buy one, get one" in story or "bogo" in story or "buy 1, get 1" in story:
        out.append("Buy one, get one")
    m = re.match(r"(\d+)\s*(?:for|/)", pre)
    if m and int(m.group(1)) > 1:
        out.append(f"Price for {m.group(1)}")
    for src in (disc, story):
        m = MUST_BUY.search(src)
        if m and int(m.group(1)) > 1:
            out.append(f"Must buy {m.group(1)}")
        m = PURCHASE.search(src)
        if m:
            out.append(f"With ${m.group(1)} purchase")
    m = LIMIT.search(disc)
    if m:
        what = (m.group(2) or "").lower()
        what = {"lb": "lbs", "pkg": "pkgs", "package": "pkgs", "packages": "pkgs", "item": "items"}.get(what, what)
        out.append(f"Limit {m.group(1)} {what}".strip() if what in ("lbs", "pkgs", "items") else f"Limit {m.group(1)}")
    seen, uniq = set(), []
    for c in out:
        if c not in seen and not (c == "Coupon" and "Digital coupon" in seen):
            seen.add(c)
            uniq.append(c)
    return uniq


SIZE_RANGE = re.compile(r"\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:oz|lb|lbs|pound)", re.I)
OZ = re.compile(r"(?<![\d./$-])(\d+(?:\.\d+)?)\s*(?:-\s*)?(?:oz|ounce)s?\b(?!\s*(?:serving|per))", re.I)
LB = re.compile(r"(?<![\d./$-])(\d+(?:\.\d+)?)\s*(?:-\s*)?(?:lb|lbs|pound)s?\.?\b", re.I)
CT = re.compile(r"(?<![\d./-])(\d+)\s*(?:ct|count)\b", re.I)
DOZ = re.compile(r"(?<![\d./-])(\d+(?:\.\d+)?)\s*dozen|\bdozen\b", re.I)


def ad_size(cat, name, desc):
    """The package size an ad states, as (label, pounds); pounds is None when it isn't a weight."""
    text = f"{name} {desc or ''}"
    if SIZE_RANGE.search(text):
        return None, None  # "12-16 oz" style ranges can't give one price per pound
    if cat == "Eggs":
        m = CT.search(text)
        if m:
            return f"{m.group(1)} ct", None
        m = DOZ.search(text)
        if m:
            return f"{m.group(1) or 1} dozen", None
        return None, None
    if cat == "Milk":
        if re.search(r"half[- ]gallon|1/2 gal", text, re.I):
            return "half gallon", None
        if re.search(r"\bgal(?:lon)?\b", text, re.I):
            return "1 gallon", None
        return None, None
    weights = {round(float(v) / 16, 4) for v in OZ.findall(text) if "fl" not in text.lower()} | \
              {round(float(v), 4) for v in LB.findall(text)}
    weights = {w for w in weights if 0.1 <= w <= 40}
    if len(weights) != 1:
        return None, None  # no size, or several different sizes on one ad
    lbs = weights.pop()
    oz = lbs * 16
    label = f"{lbs:g} lb" if lbs >= 1 and (lbs * 4).is_integer() else f"{round(oz, 1):g} oz"
    return label, lbs


def enrich_from_details(rows, ids):
    """Fetch each ad item's detail (description, disclaimer, coupon flag) and add sizes and conditions."""
    def fetch(iid):
        try:
            return iid, get_json(f"https://backflipp.wishabi.com/flipp/items/{iid}").get("item") or {}
        except Exception:
            return iid, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        details = dict(pool.map(fetch, set(ids.values())))
    sized = conds = 0
    for r in rows:
        d = details.get(ids.get(r[9]), {})
        if not d:
            continue
        extra = ad_conditions({"post_price_text": None, "pre_price_text": None, "sale_story": None}, d)
        for c in extra:
            if c not in r[12]:
                r[12].append(c)
                conds += 1
        if r[3] is not None and r[4] != "/lb":
            label, lbs = ad_size(r[0], r[2], d.get("description"))
            if label:
                r[11] = label
                if lbs:
                    r[8] = round(r[3] / lbs, 2)
                sized += 1
    print(f"Ad details: {len(details)} fetched, {sized} package sizes found, {conds} conditions added.")


SIZE_WORDS = re.compile(r"\b\d+(?:\.\d+)?\s*(?:oz|lb|lbs|ct|count|pk|pack|gal|gallon|dozen)\b", re.I)
HISTORY_DIR = HERE / "history"
HISTORY_WEEKS = 26


def item_key(r):
    """A stable identity for the same product week to week: store, food type and the name without sizes."""
    name = SIZE_WORDS.sub(" ", r[2].lower())
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return f"{r[1]}|{r[0]}|{name}"


def history_value(r):
    """The number tracked over time: price per pound when known, otherwise the item price."""
    if r[8] is not None:
        return r[8], "lb"
    if r[3] is not None:
        return r[3], "each"
    return None, None


def save_history(rows, week_start):
    """Write this ad week's prices to history/<week>.json (rewritten if the week is rebuilt)."""
    HISTORY_DIR.mkdir(exist_ok=True)
    items = {}
    for r in rows:
        value, unit = history_value(r)
        if value is not None:
            items.setdefault(r[10], [value, unit])
    (HISTORY_DIR / f"{week_start}.json").write_text(
        json.dumps({"week": week_start, "items": items}, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")


def history_for(rows):
    """Past prices for the items on this week's page, from the most recent HISTORY_WEEKS weekly files."""
    files = sorted(HISTORY_DIR.glob("*.json"))[-HISTORY_WEEKS:]
    weeks, items = [], {}
    wanted = {r[10] for r in rows}
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        weeks.append(data["week"])
        for key, (value, unit) in data["items"].items():
            if key in wanted:
                items.setdefault(key, []).append([data["week"], value, unit])
    return {"weeks": weeks, "items": items}


OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ZIP_LAT, ZIP_LON = 32.5178, -94.7303  # ZIP 75601 (Longview, TX)
SHOP_TYPES = "supermarket|wholesale|variety_store|department_store|health_food|grocery|discount|butcher|seafood"


def store_locations():
    """Grocery-type stores within ~31 miles of Longview from OpenStreetMap, trying each Overpass server
    in turn. Returns None if all fail, so the page keeps last week's locations."""
    q = (f'[out:json][timeout:60];nwr["shop"~"^({SHOP_TYPES})$"]["name"]'
         f'(around:50000,{ZIP_LAT},{ZIP_LON});out center tags;')
    body = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(2):
        for server in OVERPASS:
            try:
                req = urllib.request.Request(server, data=body, headers={**UA, "User-Agent": "LocalFoodCost/1.0 (github.com/jackgary86-dev/LocalFoodCost)"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    els = json.load(r).get("elements", [])
                places = []
                for e in els:
                    g, t = e.get("center") or e, e.get("tags") or {}
                    if g.get("lat") is None:
                        continue
                    places.append({"lat": round(g["lat"], 5), "lon": round(g["lon"], 5),
                                   "tags": {k: t[k] for k in ("brand", "name", "brand:en") if t.get(k)},
                                   "addr": " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x)})
                if places:
                    return {"zip": ZIP, "at": dt.date.today().isoformat(), "places": places}
            except Exception as e:
                print(f"warning: {server} failed: {e}")
        time.sleep(20)
    return None


def apply_verified(rows, week_start):
    """Apply hand-checked corrections from verified.json when they're for this ad week.
    Runs after the ad sizes, so a hand check wins over a size read from the description."""
    path = HERE / "verified.json"
    if not path.exists():
        return 0
    v = json.loads(path.read_text(encoding="utf-8"))
    if v.get("week") != week_start:
        return 0
    applied = 0
    for fix in v.get("items", []):
        for r in rows:
            if r[1] == fix["store"] and fix["match"].lower() in r[2].lower():
                if fix.get("name"):
                    r[2] = fix["name"]
                if fix.get("per_lb"):
                    r[8] = fix["per_lb"]
                if fix.get("note") and fix["note"] not in r[5]:
                    r[5] = "; ".join(x for x in (r[5], fix["note"]) if x)
                applied += 1
                break
    return applied


def main():
    today = dt.date.today().isoformat()
    flipp, starts = flipp_rows()
    if len(flipp) < 30:
        raise SystemExit(f"Only {len(flipp)} ad items found; not overwriting the page.")
    every = json.loads((HERE / "everyday.json").read_text(encoding="utf-8"))
    # Everyday rows with an end date (Natural Grocers specials) drop out once they end.
    keep = [r for r in every["rows"] if not r[7] or r[7] > today]
    rows = flipp + keep
    start = starts.most_common(1)[0][0]
    applied = apply_verified(rows, start)
    for r in rows:  # rows: [.. url, key, size, conditions]; everyday rows have no ad link
        r.extend([None] * (13 - len(r)))
        r[10] = item_key(r)
        if r[12] is None:
            r[12] = ["Membership"] if r[1] == "Sam's Club" else []
    save_history(rows, start)
    history = history_for(rows)
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=6)).isoformat()
    week = {"start": start, "end": end, "collected": today, "everyday_collected": every.get("collected")}

    page = HERE / "index.html"
    html = page.read_text(encoding="utf-8")
    html, n1 = re.subn(r"const LONGVIEW = \[.*?\];", lambda m: "const LONGVIEW = " + json.dumps(rows, ensure_ascii=False) + ";",
                       html, count=1, flags=re.S)
    html, n2 = re.subn(r"const WEEK_OF = \{.*?\};", lambda m: "const WEEK_OF = " + json.dumps(week) + ";", html, count=1)
    locs = store_locations()
    if locs:
        locs_js = "const STORE_LOCS = " + json.dumps(locs, ensure_ascii=False) + ";"
        html, n4 = re.subn(r"const STORE_LOCS = \{.*?\};", lambda m: locs_js, html, count=1, flags=re.S)
        if n4 == 0:
            html = html.replace("const WEEK_OF = " + json.dumps(week) + ";", "const WEEK_OF = " + json.dumps(week) + ";\n" + locs_js, 1)
        print(f"Store locations: {len(locs['places'])} places from OpenStreetMap.")
    else:
        print("Store locations: every map server failed; keeping last week's locations.")
    hist_js = "const HISTORY = " + json.dumps(history, ensure_ascii=False) + ";"
    html, n3 = re.subn(r"const HISTORY = \{.*?\};", lambda m: hist_js, html, count=1, flags=re.S)
    if n3 == 0:
        html = html.replace("const WEEK_OF = " + json.dumps(week) + ";", "const WEEK_OF = " + json.dumps(week) + ";\n" + hist_js, 1)
        n3 = 1
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise SystemExit("Couldn't find the data constants in index.html.")
    page.write_text(html, encoding="utf-8")
    print(f"Week {start} to {end}: {len(flipp)} ad items + {len(keep)} everyday items from {len(set(r[1] for r in rows))} stores.")
    print(f"Applied {applied} website-checked corrections from verified.json.")
    print(f"Price history: {len(history['weeks'])} week(s) on file ({', '.join(history['weeks'])}).")

    # Preview the Top 5 with the page's own scoring code.
    script = ("const HISTORY=" + json.dumps(history) + ";const DATA={mode:'snapshot',week:" + json.dumps(week) + "};"
              "const state={st:'TX'};const money=n=>'$'+n.toFixed(2);"
              + html[html.index("const BLS"):html.index("function cmpHtml")])
    js = (script + "\nconst L=" + json.dumps(rows) + ";const t='" + today + "';"
          "const sc=L.filter(r=>(!r[7]||r[7]>t)&&!/organic/i.test(r[2])).map(r=>({r,c:normalFor({name:r[2],price:r[3],perLb:r[8],key:r[10],size:r[11]})}))"
          ".filter(x=>x.c&&x.c.pct<=-10).sort((a,b)=>a.c.pct-b.c.pct);const per={},pick=[];"
          "for(const x of sc){if((per[x.r[0]]=(per[x.r[0]]||0)+1)>2)continue;pick.push(x);if(pick.length==5)break}"
          "pick.forEach((x,i)=>console.log(`${i+1}. ${-x.c.pct}% below normal: ${x.r[2]} at ${x.r[1]}, $${x.r[3]}`))")
    out = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, encoding="utf-8")
    print(out.stdout or out.stderr)


if __name__ == "__main__":
    main()
