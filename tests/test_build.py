"""Checks for the rules build.py uses to read grocery ads. Run: python -m unittest discover -s tests"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import build  # noqa: E402


class Category(unittest.TestCase):
    def test_food_types(self):
        cases = {
            "Kroger Large Peeled and Deveined Shrimp": "Shrimp",
            "Fresh Whole Atlantic Salmon Fillets, Extra Jumbo Raw Shrimp 16-20 ct.": "Fish",
            "Snow Crab Clusters": "Crab & crawfish",
            "Simple Truth Organic Milk": "Milk",
            "Brookshire's Large Eggs": "Eggs",
            "Hill's Premium Meats Thick Sliced Bacon": "Bacon & sausage",
            "Kirkwood Fresh 93% Lean Turkey": "Turkey",
            "Chicken Leg Quarters": "Chicken",
            "Boston Butt Pork Roast": "Pork",
            "Boneless Chuck Roast": "Beef",
            "Fresh Guacamole": None,
        }
        for name, want in cases.items():
            self.assertEqual(build.category(name), want, name)

    def test_skips_prepared_and_pet_food(self):
        for name in ["Cheap Chicken", "8-Piece Mixed Fried Chicken", "Pedigree Dog Food Adult High Protein Red Meat",
                     "Brookshire's Chicken Breast Nuggets Or Patties"]:
            self.assertTrue(build.SKIP.search(name), name)


class AdSize(unittest.TestCase):
    def test_weights(self):
        self.assertEqual(build.ad_size("Bacon & sausage", "Smithfield Bacon", "12 oz. pkg."), ("12 oz", 0.75))
        self.assertEqual(build.ad_size("Fish", "Kroger Wild Pink Salmon Fillets", "2 lb. bag, frozen"), ("2 lb", 2.0))
        self.assertEqual(build.ad_size("Pork", "Marinated Pork Loin Filet", "23 oz."), ("23 oz", 1.4375))
        # "Also sold in a 1 lb bag" and "16 oz" agree, so the size is clear.
        self.assertEqual(build.ad_size("Shrimp", "Shrimp", "16 oz. Also sold in a 1 lb. bag")[1], 1.0)

    def test_no_size_when_unclear(self):
        self.assertEqual(build.ad_size("Beef", "Ground Beef", "12-16 oz. pkg."), (None, None))   # a range
        self.assertEqual(build.ad_size("Pork", "Pork Chops", "1 lb. or 2 lb. pkg."), (None, None))  # two sizes
        self.assertEqual(build.ad_size("Chicken", "Chicken", "Only $5.99 lb"), (None, None))  # a price, not a size
        self.assertEqual(build.ad_size("Beef", "Brisket", None), (None, None))

    def test_eggs_and_milk(self):
        self.assertEqual(build.ad_size("Eggs", "Large Eggs", "18 ct."), ("18 ct", None))
        self.assertEqual(build.ad_size("Eggs", "Large Eggs", "1 dozen"), ("1 dozen", None))
        self.assertEqual(build.ad_size("Milk", "Organic Milk", "half gallon"), ("half gallon", None))
        self.assertEqual(build.ad_size("Milk", "Whole Milk", "1 gal."), ("1 gallon", None))


class Conditions(unittest.TestCase):
    def cond(self, detail=None, **item):
        base = {"post_price_text": None, "pre_price_text": None, "sale_story": None}
        base.update(item)
        return build.ad_conditions(base, detail)

    def test_coupons_cards_and_limits(self):
        self.assertEqual(self.cond({"display_type": 25, "disclaimer_text": "Limit 5 lbs. Each"}), ["Coupon", "Limit 5 lbs"])
        self.assertEqual(self.cond(post_price_text="/lb With Card"), ["Store card"])
        self.assertEqual(self.cond(post_price_text="/EA With Digital Coupon"), ["Digital coupon"])
        self.assertEqual(self.cond({"disclaimer_text": "Limit 2 Pkgs At Sale Price"}), ["Limit 2 pkgs"])

    def test_multi_buy(self):
        self.assertEqual(self.cond(sale_story="BUY ONE, GET ONE 50% OFF regular retail"), ["Buy one, get one"])
        self.assertEqual(self.cond(pre_price_text="2 FOR"), ["Price for 2"])
        self.assertEqual(self.cond({"disclaimer_text": "When you buy 3 or more"}), ["Must buy 3"])
        self.assertEqual(self.cond(), [])


class ItemKey(unittest.TestCase):
    def test_sizes_do_not_change_identity(self):
        a = ["Bacon & sausage", "Super 1 Foods", "Smithfield Bacon, 12 oz"]
        b = ["Bacon & sausage", "Super 1 Foods", "Smithfield Bacon 16 oz."]
        self.assertEqual(build.item_key(a), build.item_key(b))


if __name__ == "__main__":
    unittest.main()
