"""Decks: .ydk files, EDOPro's main/extra classification, deck checks and banlists (gframe/deck_manager.cpp)."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum

from ..core.cards import CardData, CardDatabase
from ..core.constants import (SCOPE_OCG, SCOPE_PRERELEASE, SCOPE_TCG, TYPE_MONSTER, TYPE_SKILL, TYPE_SPELL,
                              TYPE_TRAP)


class DeckErrorType(IntEnum):
    """network.h DeckError::DERR_TYPE."""
    NONE = 0
    LFLIST = 1
    OCGONLY = 2
    TCGONLY = 3
    UNKNOWNCARD = 4
    CARDCOUNT = 5
    MAINCOUNT = 6
    EXTRACOUNT = 7
    SIDECOUNT = 8
    FORBTYPE = 9
    UNOFFICIALCARD = 10
    INVALIDSIZE = 11
    TOOMANYLEGENDS = 12
    TOOMANYSKILLS = 13


class AllowedCards(IntEnum):
    """HostInfo.rule (EDOPro DuelAllowedCards)."""
    OCG_ONLY = 0
    TCG_ONLY = 1
    OCG_TCG = 2
    WITH_PRERELEASE = 3
    ANY = 4


@dataclass
class DeckError:
    type: DeckErrorType
    code: int = 0
    current: int = 0
    minimum: int = 0
    maximum: int = 0

    def __str__(self) -> str:
        if self.type in (DeckErrorType.MAINCOUNT, DeckErrorType.EXTRACOUNT, DeckErrorType.SIDECOUNT):
            what = self.type.name[:-5].lower()
            return f"{what} deck has {self.current} cards (allowed {self.minimum}-{self.maximum})"
        return f"{self.type.name.lower()}" + (f" (card {self.code})" if self.code else "")


@dataclass(frozen=True)
class DeckSizes:
    main: tuple[int, int] = (40, 60)
    extra: tuple[int, int] = (0, 15)
    side: tuple[int, int] = (0, 15)

    @classmethod
    def unlimited(cls) -> "DeckSizes":
        return cls((0, 999), (0, 999), (0, 999))


@dataclass
class Deck:
    main: list[int] = field(default_factory=list)
    extra: list[int] = field(default_factory=list)
    side: list[int] = field(default_factory=list)
    name: str = ""

    def __len__(self) -> int:
        return len(self.main)

    def copy(self) -> "Deck":
        return Deck(list(self.main), list(self.extra), list(self.side), self.name)

    def network_payload(self) -> tuple[list[int], list[int]]:
        """(main + extra, side): what CTOS_UPDATE_DECK carries."""
        return self.main + self.extra, list(self.side)


@dataclass
class LoadResult:
    deck: Deck
    unknown: list[int]   # codes not in the card database (EDOPro remembers the last one as the deck error)
    skipped_tokens: list[int] = field(default_factory=list)


def classify(main_and_extra: list[int], side: list[int], cards: CardDatabase, *, rituals_in_extra: bool = False,
             name: str = "") -> LoadResult:
    """DeckManager::LoadDeck without an explicit extra list: Extra Deck cards are told apart by type."""
    deck, unknown, tokens = Deck(name=name), [], []
    for code in main_and_extra:
        card = cards.get(code)
        if card is None:
            unknown.append(code)
            continue
        if card.is_token:
            tokens.append(code)
            continue
        is_extra = card.is_extra_deck or (rituals_in_extra and card.is_ritual_monster)
        (deck.extra if is_extra else deck.main).append(code)
    for code in side:
        card = cards.get(code)
        if card is None:
            unknown.append(code)
        elif card.is_token:
            tokens.append(code)
        else:
            deck.side.append(code)
    return LoadResult(deck, unknown, tokens)


def parse_ydk(text: str) -> tuple[list[int], list[int], list[int]]:
    """(main, extra, side) as listed in a .ydk (#main, #extra, !side sections; '#' lines are comments)."""
    main, extra, side = [], [], []
    current = main
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line == "#extra":
                current = extra
            elif line == "#main":
                current = main
            continue
        if line.startswith("!"):
            current = side
            continue
        digits = line.split()[0]
        if digits.isdigit():
            current.append(int(digits))
    return main, extra, side


def load_ydk(path: str, cards: CardDatabase, *, rituals_in_extra: bool = False) -> LoadResult:
    with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as f:
        main, extra, side = parse_ydk(f.read())
    name = os.path.splitext(os.path.basename(path))[0]
    return classify(main + extra, side, cards, rituals_in_extra=rituals_in_extra, name=name)


def find_deck(name_or_path: str, deck_dirs: list[str]) -> str:
    """A .ydk path from a path, or a deck name looked up in `deck_dirs` (EDOPro's deck/ folder first)."""
    p = os.path.expanduser(name_or_path)
    for candidate in (p, os.path.join(p, "deck.ydk")):
        if os.path.isfile(candidate):
            return candidate
    for d in deck_dirs:
        for candidate in (os.path.join(d, name_or_path), os.path.join(d, name_or_path + ".ydk"),
                          os.path.join(d, name_or_path, "deck.ydk")):
            if os.path.isfile(candidate):
                return candidate
    raise FileNotFoundError(f"deck {name_or_path!r} not found (looked in {', '.join(deck_dirs)})")


# --- banlists ----------------------------------------------------------------------------------------------

@dataclass
class Banlist:
    name: str
    content: dict[int, int] = field(default_factory=dict)
    whitelist: bool = False
    hash: int = 0x7DFCEE6A

    def limit(self, card: CardData) -> int | None:
        """LFList::GetLimitationIterator: the card's own entry, else its original's (for alt artworks)."""
        if card.code in self.content:
            return self.content[card.code]
        if card.alias and (not self.whitelist or abs(card.alias - card.code) < 10):
            return self.content.get(card.alias)
        return None


NO_BANLIST = Banlist("N/A", hash=0)  # EDOPro's "no limit" list (hash 0)


def _lflist_hash(h: int, code: int, count: int) -> int:
    m = 0xFFFFFFFF
    a = ((code << 18) & m) | (code >> 14)
    b = ((code << (27 + count)) & m if 0 <= 27 + count < 32 else 0) | \
        ((code >> (5 - count)) if 0 <= 5 - count < 32 else 0)
    return (h ^ a ^ b) & m


def load_banlists(paths: list[str]) -> list[Banlist]:
    """DeckManager::LoadLFListSingle for each file, in order."""
    lists: list[Banlist] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        cur: Banlist | None = None
        for line in lines:
            line = line.rstrip("\r")
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                cur = Banlist(line[1:].strip())
                lists.append(cur)
                continue
            if line.startswith("$whitelist") and cur:
                cur.whitelist = True
                continue
            if cur is None:
                continue
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            try:
                code, count = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if code:
                cur.content[code] = count
                cur.hash = _lflist_hash(cur.hash, code, count)
    return lists


def find_banlist(lists: list[Banlist], name: str) -> Banlist:
    key = name.strip().lower()
    for bl in lists:
        if bl.name.lower() == key:
            return bl
    matches = [bl for bl in lists if key in bl.name.lower()]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(f"banlist {name!r} not found (have: {', '.join(bl.name for bl in lists)})")


# --- checks ----------------------------------------------------------------------------------------------

@dataclass
class DeckRules:
    sizes: DeckSizes = field(default_factory=DeckSizes)
    check_size: bool = True
    check_content: bool = True
    forbidden_types: int = 0
    banlist: Banlist | None = None
    allowed: AllowedCards = AllowedCards.ANY
    rituals_in_extra: bool = False


def check_size(deck: Deck, cards: CardDatabase, sizes: DeckSizes) -> DeckError | None:
    """DeckManager::CheckDeckSize (skills don't count towards the Main Deck)."""
    skills = sum(1 for c in deck.main if (cards.get(c) or _NONE).type & TYPE_SKILL)
    for kind, count, (lo, hi) in ((DeckErrorType.MAINCOUNT, len(deck.main) - skills, sizes.main),
                                  (DeckErrorType.EXTRACOUNT, len(deck.extra), sizes.extra),
                                  (DeckErrorType.SIDECOUNT, len(deck.side), sizes.side)):
        if not lo <= count <= hi:
            return DeckError(kind, current=count, minimum=lo, maximum=hi)
    return None


_NONE = CardData(0, 0, (), 0, 0, 0, 0, 0, 0, 0, 0, 0)


def _scope_error(card: CardData, allowed: AllowedCards) -> DeckErrorType | None:
    ot = card.ot
    if allowed in (AllowedCards.OCG_ONLY, AllowedCards.TCG_ONLY, AllowedCards.OCG_TCG) and ot > 0x3:
        return DeckErrorType.UNOFFICIALCARD
    if allowed == AllowedCards.OCG_ONLY and not ot & SCOPE_OCG:
        return DeckErrorType.TCGONLY
    if allowed == AllowedCards.TCG_ONLY and not ot & SCOPE_TCG:
        return DeckErrorType.OCGONLY
    if allowed == AllowedCards.WITH_PRERELEASE and not ot & (SCOPE_OCG | SCOPE_TCG | SCOPE_PRERELEASE):
        return DeckErrorType.UNOFFICIALCARD
    return None


def check_content(deck: Deck, cards: CardDatabase, rules: DeckRules) -> DeckError | None:
    """DeckManager::CheckDeckContent. With no banlist the "N/A" list applies: still at most 3 copies, the
    card-pool rule and Main/Extra placement are checked."""
    def info(code):
        return cards.get(code) or _NONE
    all_cards = [info(c) for c in deck.main + deck.extra + deck.side]
    if rules.forbidden_types and any(c.type & rules.forbidden_types for c in all_cards):
        bad = next(c for c in all_cards if c.type & rules.forbidden_types)
        return DeckError(DeckErrorType.FORBTYPE, bad.code)
    main = [info(c) for c in deck.main]
    extra = [info(c) for c in deck.extra]
    if sum(1 for c in main + extra if c.is_legend and c.type & TYPE_MONSTER) > 1 or \
            sum(1 for c in main if c.is_legend and c.type & TYPE_SPELL) > 1 or \
            sum(1 for c in main if c.is_legend and c.type & TYPE_TRAP) > 1:
        return DeckError(DeckErrorType.TOOMANYLEGENDS)
    if sum(1 for c in main if c.type & TYPE_SKILL) > 1:
        return DeckError(DeckErrorType.TOOMANYSKILLS)
    banlist = rules.banlist or NO_BANLIST
    counts: Counter[int] = Counter()
    for section, cards_ in (("main", main), ("extra", extra), ("side", [info(c) for c in deck.side])):
        for card in cards_:
            scope = _scope_error(card, rules.allowed)
            if scope:
                return DeckError(scope, card.code)
            in_extra = card.is_extra_deck or (rules.rituals_in_extra and card.is_ritual_monster)
            if (section == "main" and in_extra) or (section == "extra" and not in_extra):
                return DeckError(DeckErrorType.EXTRACOUNT, card.code)
            counts[card.base_code] += 1
            if counts[card.base_code] > 3:
                return DeckError(DeckErrorType.CARDCOUNT, card.code)
            limit = banlist.limit(card)
            if (limit is not None and counts[card.base_code] > limit) or (banlist.whitelist and limit is None):
                return DeckError(DeckErrorType.LFLIST, card.code)
    return None


def check_deck(deck: Deck, cards: CardDatabase, rules: DeckRules, unknown: list[int] = ()) -> DeckError | None:
    """The first problem in EDOPro's order (GenericDuel::PlayerReady): size, unknown card, content."""
    if rules.check_size:
        err = check_size(deck, cards, rules.sizes)
        if err:
            return err
    if rules.check_content:
        if unknown:
            return DeckError(DeckErrorType.UNKNOWNCARD, unknown[-1])
        return check_content(deck, cards, rules)
    return None


def deck_problems(deck: Deck, cards: CardDatabase, rules: DeckRules, unknown: list[int] = ()) -> list[str]:
    """Every problem worth telling the user about (not just the first), for CLI reports."""
    out = []
    err = check_size(deck, cards, rules.sizes)
    if err:
        out.append(str(err))
    for code in unknown:
        out.append(f"unknown card {code}")
    counts = Counter((cards.get(c) or _NONE).base_code or c for c in deck.main + deck.extra + deck.side)
    for code, n in sorted(counts.items()):
        if n > 3:
            out.append(f"{n} copies of {cards.name(code)} (max 3)")
    if rules.forbidden_types:
        for c in deck.main + deck.extra + deck.side:
            if (cards.get(c) or _NONE).type & rules.forbidden_types:
                out.append(f"{cards.name(c)} is a forbidden card type under these rules")
    err = check_content(deck, cards, rules)
    if err and err.type == DeckErrorType.LFLIST:
        out.append(f"{cards.name(err.code)} exceeds the {(rules.banlist or NO_BANLIST).name} limit")
    elif err and err.type not in (DeckErrorType.CARDCOUNT, DeckErrorType.FORBTYPE):
        out.append(str(err) if not err.code else f"{err.type.name.lower()}: {cards.name(err.code)}")
    return out
