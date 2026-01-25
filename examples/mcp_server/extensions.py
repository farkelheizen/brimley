from brimley.extensions import register_sqlite_function

@register_sqlite_function("vip_score", 1)
def vip_score(purchase_count):
    """Calculates a VIP score based on purchase count."""
    if purchase_count is None:
        return 0
    return purchase_count * 10
