"""Weekly refresh for the LocalFoodCost page (index.html).

Fetches this week's grocery-ad items that Flipp lists for ZIP 75601, merges them with the
everyday prices in everyday.json (Walmart, Sam's Club, Natural Grocers), and writes the result
into index.html as the LONGVIEW and WEEK_OF constants. Prints the new Top 5.

Usage: python -I build.py
"""
import collections
import datetime as dt
import json
import pathlib
import re
import statistics
import subprocess
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
    r"marinated fish|cream of|macaroni|steak-umm|filet mignon|primo taglio|crumbled|smart way|yogurt|"
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
        if "card" in post:
            notes.append("with store card")
        if "digital coupon" in post:
            notes.append("with digital coupon")
        elif "coupon" in post:
            notes.append("with coupon")
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
                     f"https://flipp.com/en-us/longview-tx/item/{it['id']}?postal_code={ZIP}"])
    starts = collections.Counter(r[6] for r in rows)
    return rows, starts


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
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=6)).isoformat()
    week = {"start": start, "end": end, "collected": today, "everyday_collected": every.get("collected")}

    page = HERE / "index.html"
    html = page.read_text(encoding="utf-8")
    html, n1 = re.subn(r"const LONGVIEW = \[.*?\];", lambda m: "const LONGVIEW = " + json.dumps(rows, ensure_ascii=False) + ";",
                       html, count=1, flags=re.S)
    html, n2 = re.subn(r"const WEEK_OF = \{.*?\};", lambda m: "const WEEK_OF = " + json.dumps(week) + ";", html, count=1)
    if n1 != 1 or n2 != 1:
        raise SystemExit("Couldn't find the data constants in index.html.")
    page.write_text(html, encoding="utf-8")
    print(f"Week {start} to {end}: {len(flipp)} ad items + {len(keep)} everyday items from {len(set(r[1] for r in rows))} stores.")

    # Preview the Top 5 with the page's own scoring code.
    script = ('const DATA={mode:"snapshot"};const state={st:"TX"};'
              + html[html.index("const BLS"):html.index("function cmpHtml")])
    js = (script + "\nconst L=" + json.dumps(rows) + ";const t='" + today + "';"
          "const sc=L.filter(r=>!r[7]||r[7]>t).map(r=>({r,c:normalFor({name:r[2],price:r[3],perLb:r[8]})}))"
          ".filter(x=>x.c&&x.c.pct<=-10).sort((a,b)=>a.c.pct-b.c.pct);const per={},pick=[];"
          "for(const x of sc){if((per[x.r[0]]=(per[x.r[0]]||0)+1)>2)continue;pick.push(x);if(pick.length==5)break}"
          "pick.forEach((x,i)=>console.log(`${i+1}. ${-x.c.pct}% below normal: ${x.r[2]} at ${x.r[1]}, $${x.r[3]}`))")
    out = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, encoding="utf-8")
    print(out.stdout or out.stderr)


if __name__ == "__main__":
    main()
