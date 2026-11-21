"""CLDR cardinal plural categories per language.

Embedded from the Unicode CLDR plural rules (cardinal), since xcstool has no
external dependencies. Languages not in the table only require ``other``.
"""

from typing import Dict, FrozenSet

_GROUPS = {
    ("other",): (
        "bm bo dz hnj id ig ii in ja jbo jv jw kde kea km ko lkt lo ms my nqo osa root sah "
        "ses sg su th to tpi vi wo yo yue zh"
    ),
    ("one", "other"): (
        "af ak am an as asa ast az bal bem bez bg bho bn brx ce ceb cgg chr ckb csw da de doi dv "
        "ee el en eo et eu fa ff fi fil fo fur fy gl gsw gu guw ha haw hi hu hy ia io is ji jgo "
        "jmc ka kab kaj kcg kk kkj kl kn ks ksb ku ky lb lg lij ln mas mg mgo mk ml mn mr nah nb "
        "nd ne nl nn nnh no nr nso ny nyn om or os pa pap pcm ps rm rof rwk saq sc sd sdh seh si "
        "sn so sq ss ssy st sv sw syr ta te teo ti tig tk tl tn tr ts tzm ug ur uz ve vo vun wa "
        "wae xh xog yi zu"
    ),
    ("zero", "one", "other"): "ksh lag lv prg",
    ("one", "two", "other"): "he iu iw naq sat se sma smi smj smn sms",
    ("one", "few", "other"): "bs hr mo ro sh shi sr",
    ("one", "many", "other"): "ca es fr it lld pt pt-PT scn vec",
    ("one", "two", "few", "other"): "dsb gd hsb sl",
    ("one", "few", "many", "other"): "be cs lt pl ru sk uk",
    ("one", "two", "few", "many", "other"): "br ga gv mt",
    ("zero", "one", "two", "few", "many", "other"): "ar ars cy kw",
}

PLURAL_CATEGORIES: Dict[str, FrozenSet[str]] = {
    language: frozenset(categories)
    for categories, languages in _GROUPS.items()
    for language in languages.split()
}

_DEFAULT = frozenset({"other"})


def required_categories(language: str) -> FrozenSet[str]:
    """The plural categories a language requires, e.g. ``ru`` → one, few, many, other.

    Region and script subtags fall back to the base language
    (``pt-BR`` → ``pt``, ``zh-Hant`` → ``zh``).
    """
    code = language.replace("_", "-")
    lowered = {key.lower(): value for key, value in PLURAL_CATEGORIES.items()}
    if code.lower() in lowered:
        return lowered[code.lower()]
    base = code.split("-", 1)[0].lower()
    return lowered.get(base, _DEFAULT)
