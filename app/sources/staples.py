"""Curated staples: canonical, plain-form foods for common one-word queries.

USDA's own search frequently buries the "obvious" answer for broad queries
(e.g. "rice" surfaces glutinous/pudding/fried variants before plain cooked
white rice). This module seeds a small, hand-picked list of the plainest
generic USDA entry for the most common broad food terms, so search ranking
can surface the expected staple first.

Each entry's macros and `source_id` (fdcId) were fetched live from the USDA
FoodData Central API (SR Legacy / Foundation, per-100g values already) at
seeding time. See the comment on each entry for the fdcId and the exact
food it was picked from. No fallbacks were needed — every staple below
resolved to a real USDA record.
"""

from app.schemas import NormalizedFood

_STAPLES: list[tuple[list[str], NormalizedFood]] = [
    (
        ["rice", "white rice"],
        # fdcId=168878, "Rice, white, long-grain, regular, enriched, cooked"
        NormalizedFood(
            source="usda",
            source_id="168878",
            name="Rice, white, long-grain, regular, enriched, cooked",
            brand=None,
            calories_100g=130.0,
            protein_100g=2.69,
            carbs_100g=28.2,
            fat_100g=0.28,
            serving_desc="1 cup cooked",
            serving_grams=158.0,
            generic_score=1.0,
        ),
    ),
    (
        ["brown rice"],
        # fdcId=169704, "Rice, brown, long-grain, cooked"
        NormalizedFood(
            source="usda",
            source_id="169704",
            name="Rice, brown, long-grain, cooked",
            brand=None,
            calories_100g=123.0,
            protein_100g=2.74,
            carbs_100g=25.6,
            fat_100g=0.97,
            serving_desc="1 cup cooked",
            serving_grams=195.0,
            generic_score=1.0,
        ),
    ),
    (
        ["chicken", "chicken breast"],
        # fdcId=171477, "Chicken, broilers or fryers, breast, meat only, cooked, roasted"
        NormalizedFood(
            source="usda",
            source_id="171477",
            name="Chicken, broilers or fryers, breast, meat only, cooked, roasted",
            brand=None,
            calories_100g=165.0,
            protein_100g=31.0,
            carbs_100g=0.0,
            fat_100g=3.57,
            serving_desc="3 oz cooked",
            serving_grams=85.0,
            generic_score=1.0,
        ),
    ),
    (
        ["egg", "eggs"],
        # fdcId=171287, "Egg, whole, raw, fresh"
        NormalizedFood(
            source="usda",
            source_id="171287",
            name="Egg, whole, raw, fresh",
            brand=None,
            calories_100g=143.0,
            protein_100g=12.6,
            carbs_100g=0.72,
            fat_100g=9.51,
            serving_desc="1 large egg",
            serving_grams=50.0,
            generic_score=1.0,
        ),
    ),
    (
        ["banana", "bananas"],
        # fdcId=173944, "Bananas, raw"
        NormalizedFood(
            source="usda",
            source_id="173944",
            name="Bananas, raw",
            brand=None,
            calories_100g=89.0,
            protein_100g=1.09,
            carbs_100g=22.8,
            fat_100g=0.33,
            serving_desc="1 medium banana",
            serving_grams=118.0,
            generic_score=1.0,
        ),
    ),
    (
        ["apple", "apples"],
        # fdcId=171688, "Apples, raw, with skin"
        NormalizedFood(
            source="usda",
            source_id="171688",
            name="Apples, raw, with skin",
            brand=None,
            calories_100g=52.0,
            protein_100g=0.26,
            carbs_100g=13.8,
            fat_100g=0.17,
            serving_desc="1 medium apple",
            serving_grams=182.0,
            generic_score=1.0,
        ),
    ),
    (
        ["milk"],
        # fdcId=171265, "Milk, whole, 3.25% milkfat, with added vitamin D"
        NormalizedFood(
            source="usda",
            source_id="171265",
            name="Milk, whole, 3.25% milkfat, with added vitamin D",
            brand=None,
            calories_100g=61.0,
            protein_100g=3.15,
            carbs_100g=4.8,
            fat_100g=3.25,
            serving_desc="1 cup",
            serving_grams=244.0,
            generic_score=1.0,
        ),
    ),
    (
        ["oatmeal", "oats"],
        # fdcId=173905, "Cereals, oats, regular and quick, unenriched, cooked
        # with water (includes boiling and microwaving), without salt"
        NormalizedFood(
            source="usda",
            source_id="173905",
            name="Cereals, oats, regular and quick, unenriched, cooked with water, without salt",
            brand=None,
            calories_100g=71.0,
            protein_100g=2.54,
            carbs_100g=12.0,
            fat_100g=1.52,
            serving_desc="1 cup cooked",
            serving_grams=234.0,
            generic_score=1.0,
        ),
    ),
    (
        ["bread"],
        # fdcId=174924, "Bread, white, commercially prepared (includes soft
        # bread crumbs)"
        NormalizedFood(
            source="usda",
            source_id="174924",
            name="Bread, white, commercially prepared",
            brand=None,
            calories_100g=266.0,
            protein_100g=8.85,
            carbs_100g=49.4,
            fat_100g=3.33,
            serving_desc="1 slice",
            serving_grams=25.0,
            generic_score=1.0,
        ),
    ),
    (
        ["pasta"],
        # fdcId=169737, "Pasta, cooked, enriched, without added salt"
        NormalizedFood(
            source="usda",
            source_id="169737",
            name="Pasta, cooked, enriched, without added salt",
            brand=None,
            calories_100g=158.0,
            protein_100g=5.8,
            carbs_100g=30.9,
            fat_100g=0.93,
            serving_desc="1 cup cooked",
            serving_grams=140.0,
            generic_score=1.0,
        ),
    ),
    (
        ["potato", "potatoes"],
        # fdcId=170033, "Potatoes, baked, flesh, without salt"
        NormalizedFood(
            source="usda",
            source_id="170033",
            name="Potatoes, baked, flesh, without salt",
            brand=None,
            calories_100g=93.0,
            protein_100g=1.96,
            carbs_100g=21.6,
            fat_100g=0.1,
            serving_desc="1 medium baked potato",
            serving_grams=173.0,
            generic_score=1.0,
        ),
    ),
    (
        ["sweet potato"],
        # fdcId=168483, "Sweet potato, cooked, baked in skin, flesh, without salt"
        NormalizedFood(
            source="usda",
            source_id="168483",
            name="Sweet potato, cooked, baked in skin, flesh, without salt",
            brand=None,
            calories_100g=90.0,
            protein_100g=2.01,
            carbs_100g=20.7,
            fat_100g=0.15,
            serving_desc="1 medium baked sweet potato",
            serving_grams=114.0,
            generic_score=1.0,
        ),
    ),
    (
        ["broccoli"],
        # fdcId=169967, "Broccoli, cooked, boiled, drained, without salt"
        NormalizedFood(
            source="usda",
            source_id="169967",
            name="Broccoli, cooked, boiled, drained, without salt",
            brand=None,
            calories_100g=35.0,
            protein_100g=2.38,
            carbs_100g=7.18,
            fat_100g=0.41,
            serving_desc="1 cup chopped, cooked",
            serving_grams=156.0,
            generic_score=1.0,
        ),
    ),
    (
        ["salmon"],
        # fdcId=175168, "Fish, salmon, Atlantic, farmed, cooked, dry heat"
        NormalizedFood(
            source="usda",
            source_id="175168",
            name="Fish, salmon, Atlantic, farmed, cooked, dry heat",
            brand=None,
            calories_100g=206.0,
            protein_100g=22.1,
            carbs_100g=0.0,
            fat_100g=12.4,
            serving_desc="3 oz cooked",
            serving_grams=85.0,
            generic_score=1.0,
        ),
    ),
    (
        ["ground beef", "beef"],
        # fdcId=174032, "Beef, ground, 85% lean meat / 15% fat, patty, cooked, broiled"
        NormalizedFood(
            source="usda",
            source_id="174032",
            name="Beef, ground, 85% lean meat / 15% fat, patty, cooked, broiled",
            brand=None,
            calories_100g=250.0,
            protein_100g=25.9,
            carbs_100g=0.0,
            fat_100g=15.4,
            serving_desc="3 oz cooked",
            serving_grams=85.0,
            generic_score=1.0,
        ),
    ),
    (
        ["black beans", "beans"],
        # fdcId=173735, "Beans, black, mature seeds, cooked, boiled, without salt"
        NormalizedFood(
            source="usda",
            source_id="173735",
            name="Beans, black, mature seeds, cooked, boiled, without salt",
            brand=None,
            calories_100g=132.0,
            protein_100g=8.86,
            carbs_100g=23.7,
            fat_100g=0.54,
            serving_desc="1 cup cooked",
            serving_grams=172.0,
            generic_score=1.0,
        ),
    ),
    (
        ["almonds"],
        # fdcId=170567, "Nuts, almonds"
        NormalizedFood(
            source="usda",
            source_id="170567",
            name="Nuts, almonds",
            brand=None,
            calories_100g=579.0,
            protein_100g=21.2,
            carbs_100g=21.6,
            fat_100g=49.9,
            serving_desc="1 oz (about 23 almonds)",
            serving_grams=28.0,
            generic_score=1.0,
        ),
    ),
    (
        ["peanut butter"],
        # fdcId=172470, "Peanut butter, smooth style, without salt"
        NormalizedFood(
            source="usda",
            source_id="172470",
            name="Peanut butter, smooth style, without salt",
            brand=None,
            calories_100g=598.0,
            protein_100g=22.2,
            carbs_100g=22.3,
            fat_100g=51.4,
            serving_desc="2 tbsp",
            serving_grams=32.0,
            generic_score=1.0,
        ),
    ),
    (
        ["greek yogurt", "yogurt"],
        # fdcId=330137, "Yogurt, Greek, plain, nonfat"
        NormalizedFood(
            source="usda",
            source_id="330137",
            name="Yogurt, Greek, plain, nonfat",
            brand=None,
            calories_100g=61.0,
            protein_100g=10.3,
            carbs_100g=3.64,
            fat_100g=0.37,
            serving_desc="1 container (170g)",
            serving_grams=170.0,
            generic_score=1.0,
        ),
    ),
    (
        ["avocado", "avocados"],
        # fdcId=171705, "Avocados, raw, all commercial varieties"
        NormalizedFood(
            source="usda",
            source_id="171705",
            name="Avocados, raw, all commercial varieties",
            brand=None,
            calories_100g=160.0,
            protein_100g=2.0,
            carbs_100g=8.53,
            fat_100g=14.7,
            serving_desc="1/2 medium avocado",
            serving_grams=100.0,
            generic_score=1.0,
        ),
    ),
    (
        ["olive oil"],
        # fdcId=171413, "Oil, olive, salad or cooking"
        NormalizedFood(
            source="usda",
            source_id="171413",
            name="Oil, olive, salad or cooking",
            brand=None,
            calories_100g=884.0,
            protein_100g=0.0,
            carbs_100g=0.0,
            fat_100g=100.0,
            serving_desc="1 tbsp",
            serving_grams=14.0,
            generic_score=1.0,
        ),
    ),
    (
        ["cheddar", "cheddar cheese"],
        # fdcId=328637, "Cheese, cheddar"
        NormalizedFood(
            source="usda",
            source_id="328637",
            name="Cheese, cheddar",
            brand=None,
            calories_100g=408.0,
            protein_100g=23.3,
            carbs_100g=2.44,
            fat_100g=34.0,
            serving_desc="1 oz",
            serving_grams=28.0,
            generic_score=1.0,
        ),
    ),
    (
        ["tofu"],
        # fdcId=172448, "Tofu, firm, prepared with calcium sulfate and
        # magnesium chloride (nigari)"
        NormalizedFood(
            source="usda",
            source_id="172448",
            name="Tofu, firm, prepared with calcium sulfate and magnesium chloride (nigari)",
            brand=None,
            calories_100g=78.0,
            protein_100g=9.04,
            carbs_100g=2.85,
            fat_100g=4.17,
            serving_desc="1/2 cup",
            serving_grams=124.0,
            generic_score=1.0,
        ),
    ),
    (
        ["quinoa"],
        # fdcId=168917, "Quinoa, cooked"
        NormalizedFood(
            source="usda",
            source_id="168917",
            name="Quinoa, cooked",
            brand=None,
            calories_100g=120.0,
            protein_100g=4.4,
            carbs_100g=21.3,
            fat_100g=1.92,
            serving_desc="1 cup cooked",
            serving_grams=185.0,
            generic_score=1.0,
        ),
    ),
    (
        ["spinach"],
        # fdcId=168462, "Spinach, raw"
        NormalizedFood(
            source="usda",
            source_id="168462",
            name="Spinach, raw",
            brand=None,
            calories_100g=23.0,
            protein_100g=2.86,
            carbs_100g=3.63,
            fat_100g=0.39,
            serving_desc="1 cup raw",
            serving_grams=30.0,
            generic_score=1.0,
        ),
    ),
    (
        ["carrot", "carrots"],
        # fdcId=170393, "Carrots, raw"
        NormalizedFood(
            source="usda",
            source_id="170393",
            name="Carrots, raw",
            brand=None,
            calories_100g=41.0,
            protein_100g=0.93,
            carbs_100g=9.58,
            fat_100g=0.24,
            serving_desc="1 medium carrot",
            serving_grams=61.0,
            generic_score=1.0,
        ),
    ),
    (
        ["orange", "oranges"],
        # fdcId=169097, "Oranges, raw, all commercial varieties"
        NormalizedFood(
            source="usda",
            source_id="169097",
            name="Oranges, raw, all commercial varieties",
            brand=None,
            calories_100g=47.0,
            protein_100g=0.94,
            carbs_100g=11.8,
            fat_100g=0.12,
            serving_desc="1 medium orange",
            serving_grams=131.0,
            generic_score=1.0,
        ),
    ),
]


def staple_for(query: str) -> NormalizedFood | None:
    q = (query or "").strip().lower()
    if not q:
        return None
    for triggers, food in _STAPLES:
        if q in triggers:
            return food
    return None
