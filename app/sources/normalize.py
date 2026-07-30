from app.schemas import NormalizedFood

# USDA FoodData Central nutrient IDs (values are per 100g)
_USDA_ENERGY = 1008
_USDA_PROTEIN = 1003
_USDA_CARBS = 1005
_USDA_FAT = 1004

_USDA_REFERENCE_TYPES = {"Foundation", "SR Legacy"}
_OFF_NOVA_SCORE = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.1}


def _usda_generic_score(item: dict) -> float:
    dt = item.get("dataType")
    if dt in _USDA_REFERENCE_TYPES:
        base = 1.0
    elif dt == "Survey (FNDDS)":
        base = 0.6
    elif dt == "Branded":
        base = 0.2
    else:
        base = 0.5
    if not (item.get("brandOwner") or item.get("brandName")):
        base = min(1.0, base + 0.05)
    return base


def _off_generic_score(product: dict) -> float:
    nova = product.get("nova_group")
    base = 0.5
    if nova is not None:
        try:
            base = _OFF_NOVA_SCORE.get(int(nova), 0.5)
        except (TypeError, ValueError):
            base = 0.5
    if not (product.get("brands") or "").strip():
        base = min(1.0, base + 0.05)
    return base


def _usda_nutrients(item: dict) -> dict[int, float]:
    out: dict[int, float] = {}
    for n in item.get("foodNutrients", []):
        nid = n.get("nutrientId")
        val = n.get("value")
        if nid is not None and val is not None:
            out[int(nid)] = float(val)
    return out


def normalize_usda(item: dict) -> NormalizedFood | None:
    nut = _usda_nutrients(item)
    if _USDA_ENERGY not in nut:
        return None
    brand = item.get("brandOwner") or item.get("brandName")
    return NormalizedFood(
        source="usda",
        source_id=str(item["fdcId"]),
        name=item.get("description", "").strip(),
        brand=brand or None,
        calories_100g=nut[_USDA_ENERGY],
        protein_100g=nut.get(_USDA_PROTEIN, 0.0),
        carbs_100g=nut.get(_USDA_CARBS, 0.0),
        fat_100g=nut.get(_USDA_FAT, 0.0),
        serving_desc="100g",
        serving_grams=100.0,
        generic_score=_usda_generic_score(item),
    )


def normalize_off(product: dict) -> NormalizedFood | None:
    nut = product.get("nutriments", {})
    energy = nut.get("energy-kcal_100g")
    if energy is None:
        return None
    brand = (product.get("brands") or "").split(",")[0].strip() or None
    serving_grams = product.get("serving_quantity")
    return NormalizedFood(
        source="off",
        source_id=str(product.get("code", "")),
        name=(product.get("product_name") or "").strip(),
        brand=brand,
        calories_100g=float(energy),
        protein_100g=float(nut.get("proteins_100g", 0.0)),
        carbs_100g=float(nut.get("carbohydrates_100g", 0.0)),
        fat_100g=float(nut.get("fat_100g", 0.0)),
        serving_desc=(product.get("serving_size") or None),
        serving_grams=float(serving_grams) if serving_grams is not None else None,
        generic_score=_off_generic_score(product),
    )
