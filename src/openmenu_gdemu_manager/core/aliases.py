from .matching import normalize


TITLE_ALIASES: dict[str, list[str]] = {
    "Jet Set Radio": ["Jet Grind Radio", "De La Jet Set Radio"],
    "Jet Grind Radio": ["Jet Set Radio", "De La Jet Set Radio"],
    "Garou: Mark of the Wolves": ["Fatal Fury - Mark of the Wolves", "Garou Mark Of The Wolves"],
    "Garou Mark Of The Wolves": ["Fatal Fury - Mark of the Wolves", "Garou: Mark of the Wolves"],
    "Fatal Fury - Mark of the Wolves": ["Garou: Mark of the Wolves", "Garou Mark Of The Wolves"],
    "Daytona USA 2001": ["Daytona USA"],
    "Daytona USA": ["Daytona USA 2001"],
    "The House of the Dead 2": ["House of the Dead 2, The"],
    "House of the Dead 2, The": ["The House of the Dead 2"],
    "Capcom vs. SNK 2": ["Capcom vs. SNK 2 - Millionaire Fighting 2001"],
    "Capcom vs. SNK 2 - Millionaire Fighting 2001": ["Capcom vs. SNK 2"],
    "The King of Fighters '99 Evolution": ["King of Fighters, The - Evolution", "KOF 99 Evolution"],
    "The King of Fighters Dream Match 1999": ["King of Fighters, The - Dream Match 1999", "KOF Dream Match 1999"],
}


def query_variants(title: str, product_id: str = "") -> list[str]:
    variants = [title]
    normalized_title = normalize(title)
    for alias_key, alias_values in TITLE_ALIASES.items():
        all_titles = [alias_key, *alias_values]
        if normalized_title in {normalize(item) for item in all_titles}:
            variants.extend(all_titles)
    variants.extend(
        [
            f"{title} Dreamcast cover",
            f"{title} Sega Dreamcast box art",
        ]
    )
    if product_id:
        variants.append(product_id)

    result: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        key = normalize(variant)
        if variant and key and key not in seen:
            seen.add(key)
            result.append(variant)
    return result


def is_alias_match(query: str, title: str) -> bool:
    nq = normalize(query)
    nt = normalize(title)
    if not nq or not nt:
        return False
    for alias_key, alias_values in TITLE_ALIASES.items():
        group = {normalize(alias_key), *(normalize(value) for value in alias_values)}
        if nq in group and nt in group:
            return True
    return False
