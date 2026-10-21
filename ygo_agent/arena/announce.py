"""MSG_ANNOUNCE_CARD filters: the core sends a small stack program; a declared card must satisfy it
(playerop.cpp is_declarable). Policies use this to find legal codes to declare."""

from __future__ import annotations

from ..core.cards import CardData, CardDatabase
from ..core.constants import (OPCODE_ADD, OPCODE_ALLOW_ALIASES, OPCODE_ALLOW_TOKENS, OPCODE_AND, OPCODE_BAND,
                              OPCODE_BNOT, OPCODE_BOR, OPCODE_BXOR, OPCODE_DIV, OPCODE_GETATTRIBUTE,
                              OPCODE_GETCODE, OPCODE_GETRACE, OPCODE_GETTYPE, OPCODE_ISATTRIBUTE, OPCODE_ISCODE,
                              OPCODE_ISRACE, OPCODE_ISSETCARD, OPCODE_ISTYPE, OPCODE_LSHIFT, OPCODE_MUL,
                              OPCODE_NEG, OPCODE_NOT, OPCODE_OR, OPCODE_RSHIFT, OPCODE_SUB, TYPE_MONSTER,
                              TYPE_TOKEN)

CARD_MARINE_DOLPHIN = 78734254
CARD_TWINKLE_MOSS = 13857930

_BINARY = {
    OPCODE_ADD: lambda a, b: a + b, OPCODE_SUB: lambda a, b: a - b, OPCODE_MUL: lambda a, b: a * b,
    OPCODE_DIV: lambda a, b: int(a / b) if b else 0, OPCODE_AND: lambda a, b: int(bool(a) and bool(b)),
    OPCODE_OR: lambda a, b: int(bool(a) or bool(b)), OPCODE_BAND: lambda a, b: a & b,
    OPCODE_BOR: lambda a, b: a | b, OPCODE_BXOR: lambda a, b: a ^ b, OPCODE_LSHIFT: lambda a, b: a << (b & 63),
    OPCODE_RSHIFT: lambda a, b: a >> (b & 63),
}
_UNARY = {OPCODE_NEG: lambda a: -a, OPCODE_NOT: lambda a: int(not a), OPCODE_BNOT: lambda a: ~a}


def _has_setcode(card: CardData, set_code: int) -> bool:
    settype, subtype = set_code & 0xFFF, set_code & 0xF000
    return any((sc & 0xFFF) == settype and (sc & 0xF000 & subtype) == subtype for sc in card.setcodes)


def is_declarable(card: CardData, opcodes: list[int]) -> bool:
    stack: list[int] = []
    alias = token = False
    for op in opcodes:
        if op in _BINARY:
            if len(stack) >= 2:
                rhs, lhs = stack.pop(), stack.pop()
                stack.append(_BINARY[op](lhs, rhs))
        elif op in _UNARY:
            if stack:
                stack.append(_UNARY[op](stack.pop()))
        elif op == OPCODE_ISCODE:
            if stack:
                stack.append(int(card.code == (stack.pop() & 0xFFFFFFFF)))
        elif op == OPCODE_ISTYPE:
            if stack:
                stack.append(card.type & stack.pop())
        elif op == OPCODE_ISRACE:
            if stack:
                stack.append(card.race & stack.pop())
        elif op == OPCODE_ISATTRIBUTE:
            if stack:
                stack.append(card.attribute & stack.pop())
        elif op == OPCODE_GETCODE:
            stack.append(card.code)
        elif op == OPCODE_GETTYPE:
            stack.append(card.type)
        elif op == OPCODE_GETRACE:
            stack.append(card.race)
        elif op == OPCODE_GETATTRIBUTE:
            stack.append(card.attribute)
        elif op == OPCODE_ISSETCARD:
            if stack:
                stack.append(int(_has_setcode(card, stack.pop() & 0xFFFFFFFF)))
        elif op == OPCODE_ALLOW_ALIASES:
            alias = True
        elif op == OPCODE_ALLOW_TOKENS:
            token = True
        else:
            stack.append(op)
    if len(stack) != 1 or stack[0] == 0:
        return False
    if card.code in (CARD_MARINE_DOLPHIN, CARD_TWINKLE_MOSS):
        return True
    is_token_monster = (card.type & (TYPE_MONSTER | TYPE_TOKEN)) == (TYPE_MONSTER | TYPE_TOKEN)
    return (alias or not card.alias) and (token or not is_token_monster)


def declarable_codes(cards: CardDatabase, opcodes: list[int], limit: int | None = None) -> list[int]:
    out = []
    for card in cards.cards.values():
        if is_declarable(card, opcodes):
            out.append(card.code)
            if limit and len(out) >= limit:
                break
    return out
