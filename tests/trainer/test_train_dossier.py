"""The dossier: counts, texts, archetypes, Levels/Ranks, scripts copied and their hints (no EDOPro needed)."""

import json
import os

import pytest

from ygo_agent.trainer import dossier

GALE, BORA, SHAMAL, ARMOR_MASTER, ICARUS = 2009101, 49003716, 8571567, 69031175, 53567095

GALE_LUA = """--Blackwing - Gale the Whirlwind
local s,id=GetID()
function s.initial_effect(c)
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetCode(EFFECT_SPSUMMON_PROC)
	e1:SetRange(LOCATION_HAND)
	e1:SetCondition(s.spcon)
	c:RegisterEffect(e1)
	local e2=Effect.CreateEffect(c)
	e2:SetType(EFFECT_TYPE_IGNITION)
	e2:SetProperty(EFFECT_FLAG_CARD_TARGET)
	e2:SetRange(LOCATION_MZONE)
	e2:SetCountLimit(1)
	e2:SetTarget(s.target)
	c:RegisterEffect(e2)
end
"""
ARMOR_LUA = """local s,id=GetID()
function s.initial_effect(c)
	Synchro.AddProcedure(c,aux.FilterBoolFunctionEx(Card.IsSetCard,SET_BLACKWING),1,1,Synchro.NonTuner(nil),1,99)
	c:EnableReviveLimit()
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e1:SetCode(EVENT_BATTLE_DAMAGE)
	e1:SetCountLimit(1,id)
	e1:SetCost(s.cost)
	c:RegisterEffect(e1)
	local e2=e1:Clone()
	e2:SetProperty(EFFECT_FLAG_DELAY)
	c:RegisterEffect(e2)
end
"""


@pytest.fixture
def setup(tmp_path, db):
    scripts = tmp_path / "script"
    scripts.mkdir()
    (scripts / f"c{GALE}.lua").write_text(GALE_LUA)
    (scripts / f"c{ARMOR_MASTER}.lua").write_text(ARMOR_LUA)
    (scripts / "proc_synchro.lua").write_text("-- synchro procedure\n")
    (scripts / "utility.lua").write_text("-- utility\n")
    ydk = tmp_path / "Mini.ydk"
    ydk.write_text("#main\n" + "\n".join(map(str, [GALE, GALE, BORA, BORA, BORA, SHAMAL, ICARUS])) +
                   f"\n#extra\n{ARMOR_MASTER}\n!side\n")
    db.setnames = {0x33: "Blackwing"}
    out = tmp_path / "train"
    out.mkdir()
    return ydk, scripts, out


def test_dossier_has_counts_texts_archetypes_levels_and_scripts(setup, db):
    ydk, scripts, out = setup
    d = dossier.build(str(ydk), db, [str(scripts)], str(out), "Mini")
    gale = d.card(GALE)
    assert gale.count == 2 and gale.section == "main" and gale.tuner and gale.level == 3
    assert gale.archetypes == ["Blackwing"] and gale.script == f"scripts/c{GALE}.lua"
    assert (out / "scripts" / f"c{GALE}.lua").read_text() == GALE_LUA
    assert any("soft once per turn" in h for h in gale.hints)
    assert any("SPSUMMON_PROC" in h and "range hand" in h for h in gale.hints)
    armor = d.card("Blackwing Armor Master")
    assert armor.extra_kind == "Synchro" and armor.level == 7
    assert armor.procedure and armor.procedure[0].startswith("Synchro.AddProcedure")
    assert "EnableReviveLimit" in armor.restrictions
    e1 = next(h for h in armor.hints if h.startswith("e1:"))
    e2 = next(h for h in armor.hints if h.startswith("e2:"))
    assert "hard 1x per turn" in e1 and "'when'" in e1 and "cost s.cost" in e1
    assert "'if'" in e2 and "hard 1x per turn" in e2  # a Clone keeps its count limit, adds DELAY
    assert d.card(BORA).script is None and any("Bora" in m for m in d.missing_scripts)
    text = (out / "dossier.md").read_text()
    for want in ("2x Blackwing - Gale the Whirlwind", "**Blackwing** (0x33)", "Lv3 (2)", "Lv4 (4)",
                 "Synchro Lv7: **Blackwing Armor Master**", "Tuners in the Main Deck"):
        assert want in text, want
    assert "scripts/lib/proc_synchro.lua" in d.libs and "scripts/lib/utility.lua" in d.libs
    cards = json.loads((out / "cards.json").read_text())
    assert {c["id"] for c in cards} == {GALE, BORA, SHAMAL, ICARUS, ARMOR_MASTER}
    again = dossier.load(str(out), "Mini", db)
    assert again.card(GALE).hints == gale.hints and again.main_codes().count(BORA) == 3


def test_scripts_text_strips_comments(setup, db):
    ydk, scripts, out = setup
    d = dossier.build(str(ydk), db, [str(scripts)], str(out), "Mini")
    text = dossier.scripts_text(d, {"Blackwing - Gale the Whirlwind"})
    assert "Gale" in text and "--Blackwing" not in text and "SetCountLimit(1)" in text
    assert "Armor Master" not in text


def test_count_limit_kinds():
    assert dossier.count_limit("1").startswith("soft")
    assert "hard" in dossier.count_limit("1,id")
    assert "activation" in dossier.count_limit("1,id,EFFECT_COUNT_CODE_OATH")
    assert "Duel" in dossier.count_limit("1,id,EFFECT_COUNT_CODE_DUEL")
    assert "key {id,1}" in dossier.count_limit("1,{id,1}")


def test_setcode_membership():
    assert dossier.setcodes(0x1072 | (0x33 << 16)) == [0x1072, 0x33]
    assert dossier.in_archetype([0x1072], 0x72)        # Geargiano is a Geargia
    assert not dossier.in_archetype([0x72], 0x1072)    # but not every Geargia is a Geargiano


@pytest.mark.integration
def test_real_deck_dossier(tmp_path, agent_db, engine):
    path = os.path.join(engine.install.deck_dir, "Blackwing.ydk")
    if not os.path.isfile(path):
        pytest.skip("no Blackwing.ydk")
    d = dossier.build(path, agent_db, engine.install.script_dirs, str(tmp_path), "Blackwing")
    assert not [m for m in d.missing_scripts if "not in the card database" in m]
    assert sum(c.count for c in d.cards if c.section == "main") >= 40
    assert all(c.script for c in d.cards if c.kind != "Monster" or c.text)
