"""Deck files, Main/Extra classification and EDOPro's deck checks, on a small synthetic card database."""

import sqlite3

import pytest

from ygo_agent.arena import deck as D
from ygo_agent.core.cards import CardDatabase
from ygo_agent.core.constants import (TYPE_EFFECT, TYPE_FUSION, TYPE_LINK, TYPE_MONSTER, TYPE_SPELL, TYPE_TOKEN,
                                      TYPE_XYZ)

MONSTER, SPELL, FUSION, LINK, XYZ, TOKEN = 1000, 2000, 3000, 4000, 5000, 6000


@pytest.fixture
def cards(tmp_path):
    path = tmp_path / "cards.cdb"
    con = sqlite3.connect(path)
    con.execute("create table datas (id integer primary key, ot integer, alias integer, setcode integer, "
                "type integer, atk integer, def integer, level integer, race integer, attribute integer, "
                "category integer)")
    con.execute("create table texts (id integer primary key, name text, desc text, " +
                ", ".join(f"str{i} text" for i in range(1, 17)) + ")")
    rows = [(MONSTER, TYPE_MONSTER | TYPE_EFFECT, 1, "Monster"), (SPELL, TYPE_SPELL, 3, "Spell"),
            (FUSION, TYPE_MONSTER | TYPE_FUSION, 1, "Fusion"), (LINK, TYPE_MONSTER | TYPE_LINK, 1, "Link"),
            (XYZ, TYPE_MONSTER | TYPE_XYZ, 0x100, "Anime Xyz"), (TOKEN, TYPE_MONSTER | TYPE_TOKEN, 1, "Token"),
            (MONSTER + 1, TYPE_MONSTER, 1, "Monster (alt art)")]
    for code, ctype, ot, name in rows:
        alias = MONSTER if code == MONSTER + 1 else 0
        con.execute("insert into datas values (?,?,?,?,?,?,?,?,?,?,?)",
                    (code, ot, alias, 0x12, ctype, 1000, 2 if ctype & TYPE_LINK else 1000, 4, 1, 1, 0))
        con.execute("insert into texts (id, name, desc) values (?,?,?)", (code, name, ""))
    con.commit()
    con.close()
    return CardDatabase([str(path)])


def test_card_data_conversion(cards):
    link = cards.get(LINK)
    assert link.link_marker == 2 and link.defense == 0 and link.is_extra_deck
    assert cards.get(MONSTER).setcodes == (0x12,) and cards.get(MONSTER + 1).base_code == MONSTER
    assert cards.resolve("spell") == SPELL and cards.resolve(str(FUSION)) == FUSION


def test_parse_ydk_and_classify(cards):
    text = f"#created by x\n#main\n{MONSTER}\n{FUSION}\n{TOKEN}\n#extra\n{LINK}\n!side\n{SPELL}\n12345\n"
    main, extra, side = D.parse_ydk(text)
    assert (main, extra, side) == ([MONSTER, FUSION, TOKEN], [LINK], [SPELL, 12345])
    r = D.classify(main + extra, side, cards)
    assert r.deck.main == [MONSTER] and r.deck.extra == [FUSION, LINK] and r.deck.side == [SPELL]
    assert r.unknown == [12345] and r.skipped_tokens == [TOKEN]


def deck(main=(), extra=(), side=()):
    return D.Deck(list(main), list(extra), list(side))


def test_size_checks(cards):
    rules = D.DeckRules()
    err = D.check_deck(deck([SPELL] * 39), cards, rules)
    assert err.type == D.DeckErrorType.MAINCOUNT and (err.current, err.minimum, err.maximum) == (39, 40, 60)
    err = D.check_deck(deck([SPELL] * 40, [FUSION] * 16), cards, D.DeckRules(check_content=False))
    assert err.type == D.DeckErrorType.EXTRACOUNT
    assert D.check_deck(deck([SPELL] * 10), cards, D.DeckRules(sizes=D.DeckSizes.unlimited(),
                                                               check_content=False)) is None


def test_content_checks(cards):
    rules = D.DeckRules(sizes=D.DeckSizes.unlimited())
    assert D.check_deck(deck([MONSTER] * 3 + [SPELL] * 3), cards, rules) is None
    err = D.check_deck(deck([MONSTER] * 2 + [MONSTER + 1] * 2), cards, rules)   # alt arts count together
    assert err.type == D.DeckErrorType.CARDCOUNT
    err = D.check_deck(deck([MONSTER], [LINK]), cards, D.DeckRules(sizes=D.DeckSizes.unlimited(),
                                                                   forbidden_types=TYPE_LINK))
    assert err.type == D.DeckErrorType.FORBTYPE and err.code == LINK
    err = D.check_deck(deck([MONSTER]), cards, rules, unknown=[999])
    assert err.type == D.DeckErrorType.UNKNOWNCARD and err.code == 999
    err = D.check_deck(deck([MONSTER], [XYZ]), cards, D.DeckRules(sizes=D.DeckSizes.unlimited(),
                                                                  allowed=D.AllowedCards.OCG_TCG))
    assert err.type == D.DeckErrorType.UNOFFICIALCARD and err.code == XYZ
    err = D.check_deck(deck([SPELL]), cards, D.DeckRules(sizes=D.DeckSizes.unlimited(),
                                                         allowed=D.AllowedCards.OCG_ONLY))
    assert err is None  # ot 3 = OCG and TCG


def test_banlist_parsing_and_limits(cards, tmp_path):
    conf = tmp_path / "test.lflist.conf"
    conf.write_text(f"#comment\n!2026.1 Test\n{MONSTER} 1 --limited\n{SPELL} 0\n!Whitelist\n$whitelist\n"
                    f"{SPELL} 3\n")
    lists = D.load_banlists([str(conf)])
    assert [b.name for b in lists] == ["2026.1 Test", "Whitelist"]
    assert lists[0].content == {MONSTER: 1, SPELL: 0} and lists[1].whitelist
    assert lists[0].hash != 0x7DFCEE6A and lists[0].hash == D.load_banlists([str(conf)])[0].hash
    rules = D.DeckRules(sizes=D.DeckSizes.unlimited(), banlist=lists[0])
    assert D.check_deck(deck([MONSTER, MONSTER + 1]), cards, rules).type == D.DeckErrorType.LFLIST
    assert D.check_deck(deck([SPELL]), cards, rules).type == D.DeckErrorType.LFLIST
    white = D.DeckRules(sizes=D.DeckSizes.unlimited(), banlist=lists[1])
    assert D.check_deck(deck([SPELL] * 3), cards, white) is None
    assert D.check_deck(deck([MONSTER]), cards, white).type == D.DeckErrorType.LFLIST
    assert D.find_banlist(lists, "test").name == "2026.1 Test"


def test_deck_problems_lists_everything(cards):
    probs = D.deck_problems(deck([MONSTER] * 4), cards, D.DeckRules(forbidden_types=TYPE_MONSTER), [42])
    assert any("main deck has 4" in p for p in probs)
    assert any("4 copies" in p for p in probs) and any("unknown card 42" in p for p in probs)
    assert any("forbidden" in p for p in probs)
