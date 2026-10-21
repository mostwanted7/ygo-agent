// End-to-end test of the C# bridge against a running brain (ygo-agent play --join --brain-only),
// using a hand-built Saffira opening instead of a real EDOPro room. Usage: BridgeTest.exe cards.cdb [brain port]
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using WindBot.Game;
using YGOSharp.OCGWrapper;
using YGOSharp.OCGWrapper.Enums;

static class BridgeTest
{
    const int SDQ = 51296484, TourGuide = 10802915, Benten = 77235086, Veiler = 97268402, PrePrep = 13048472;
    const int Hymn = 80566312, Prayers = 52472775, Saffira = 56350972, GhostOgre = 59438930, Stratos = 40044918;

    static ClientCard Card(int id, CardLocation loc, int seq, int controller, int position = 1, int atk = -1, int def = -1)
    {
        ClientCard c = new ClientCard(id, loc, seq, controller);
        c.Sequence = seq;
        c.Position = position;
        if (atk >= 0) typeof(ClientCard).GetProperty("Attack").SetValue(c, atk);
        if (def >= 0) typeof(ClientCard).GetProperty("Defense").SetValue(c, def);
        if (atk >= 0) typeof(ClientCard).GetProperty("Level").SetValue(c, 4);
        return c;
    }

    static void Check(string what, bool ok)
    {
        Console.WriteLine((ok ? "PASS " : "FAIL ") + what);
        if (!ok) Environment.ExitCode = 1;
    }

    static int Main(string[] args)
    {
        NamedCardsManager.LoadDatabase(args[0]);
        int port = args.Length > 1 ? int.Parse(args[1]) : 7922;
        Chat2Parsing();
        Duel preDuel = new Duel();  // fields not initialized yet, like when choosing who goes first
        BrainBridge early = new BrainBridge("127.0.0.1", port, preDuel, (m, f) => { }, Console.WriteLine);
        bool? goFirst = early.SelectFirst();
        Check("go_first answered before the duel starts", goFirst == true);

        Duel duel = new Duel();
        duel.IsFirst = true;
        duel.Fields[0].Init(35, 12);
        duel.Fields[1].Init(35, 15);
        duel.Fields[0].LifePoints = 8000;
        duel.Fields[1].LifePoints = 8000;
        duel.Turn = 1;
        duel.Player = 0;
        duel.Phase = DuelPhase.Main1;
        duel.Fields[0].Hand.Clear();
        int[] hand = { SDQ, TourGuide, Benten, Veiler, PrePrep };
        for (int i = 0; i < hand.Length; ++i)
            duel.Fields[0].Hand.Add(Card(hand[i], CardLocation.Hand, i, 0));

        List<string> chat = new List<string>();
        BrainBridge bridge = new BrainBridge("127.0.0.1", port, duel, (msg, forced) => { chat.Add(msg); Console.WriteLine("  chat> " + msg); }, Console.WriteLine);
        Check("connected", bridge.Connected);
        bridge.Event("room", new Dictionary<string, object> { { "duel_flags", 858112L }, { "best_of", 3 }, { "teams", new[] { 1, 1 } } });
        bridge.Event("start", new Dictionary<string, object> { { "first", true }, { "lp", new[] { 8000, 8000 } }, { "names", new[] { "Claude", "Tester" } } });
        bridge.Event("new_turn", new Dictionary<string, object> { { "turn", 1 }, { "player", 0 } });
        bridge.Event("new_phase", new Dictionary<string, object> { { "phase", 4 }, { "player", 0 } });

        // Main Phase 1 options.
        MainPhase main = new MainPhase();
        ClientCard sdq = duel.Fields[0].Hand[0], tour = duel.Fields[0].Hand[1], preprep = duel.Fields[0].Hand[4];
        long sdqDesc = ((long)SDQ << 20) | 0;
        sdq.ActionActivateIndex[sdqDesc] = 0;
        main.ActivableCards.Add(sdq); main.ActivableDescs.Add(sdqDesc);
        preprep.ActionActivateIndex[0] = 1;
        main.ActivableCards.Add(preprep); main.ActivableDescs.Add(0);
        tour.ActionIndex[0] = 0; main.SummonableCards.Add(tour);
        tour.ActionIndex[3] = 0; main.MonsterSetableCards.Add(tour);
        preprep.ActionIndex[4] = 0; main.SpellSetableCards.Add(preprep);
        main.CanEndPhase = true;
        MainPhaseAction idle = bridge.SelectIdle(main);
        Check("idle returns an action", idle != null);
        if (idle != null) Console.WriteLine("  idle action: " + idle.Action + " index " + idle.Index);

        // SDQ's effect: pick a Ritual Spell to send from the Deck.
        List<ClientCard> deckSpells = new List<ClientCard> { Card(Hymn, CardLocation.Deck, 3, 0), Card(Hymn, CardLocation.Deck, 9, 0), Card(Prayers, CardLocation.Deck, 17, 0) };
        IList<ClientCard> sent = bridge.SelectCards("select_card", deckSpells, 1, 1, 504, false);
        Check("select_card picks one", sent != null && sent.Count == 1);

        // Ritual tribute: Levels must reach 6.
        List<ClientCard> tributes = new List<ClientCard> { duel.Fields[0].Hand[1], duel.Fields[0].Hand[2], duel.Fields[0].Hand[3] };
        tributes[0].OpParam1 = 3; tributes[1].OpParam1 = 6; tributes[2].OpParam1 = 1;
        IList<ClientCard> sum = bridge.SelectSum(tributes, 6, 1, 3, 500, false);
        Check("select_sum returns a valid tribute set", sum != null && sum.Sum(c => c.OpParam1) >= 6);

        CardPosition pos = bridge.SelectPosition(Saffira, new List<CardPosition> { CardPosition.FaceUpAttack, CardPosition.FaceUpDefence });
        Check("position answered", pos == CardPosition.FaceUpAttack || pos == CardPosition.FaceUpDefence);

        // Opponent's turn: they Normal Summon Stratos and activate its search; we hold Ghost Ogre.
        duel.Turn = 2; duel.Player = 1;
        bridge.Event("new_turn", new Dictionary<string, object> { { "turn", 2 }, { "player", 1 } });
        duel.Fields[0].MonsterZone[2] = Card(Saffira, CardLocation.MonsterZone, 2, 0, 1, 2500, 2400);
        duel.Fields[0].Hand.Clear();
        duel.Fields[0].Hand.Add(Card(GhostOgre, CardLocation.Hand, 0, 0));
        duel.Fields[0].Hand.Add(Card(Veiler, CardLocation.Hand, 1, 0));
        ClientCard stratos = Card(Stratos, CardLocation.MonsterZone, 1, 1, 1, 1800, 300);
        duel.Fields[1].MonsterZone[1] = stratos;
        bridge.Event("summoning", new Dictionary<string, object> { { "id", Stratos }, { "to", new Dictionary<string, object> { { "c", 1 }, { "l", 4 }, { "s", 1 }, { "p", 1 } } }, { "special", false } });
        long stratosDesc = ((long)Stratos << 20) | 1;
        duel.CurrentChain.Add(stratos);
        duel.CurrentChainInfo.Add(new ChainInfo(stratos, 1, stratosDesc));
        bridge.Event("chaining", new Dictionary<string, object> { { "id", Stratos }, { "card", BrainBridge.Card(stratos) }, { "player", 1 }, { "desc", stratosDesc }, { "link", 1 } });
        int chainChoice = bridge.SelectChain(new List<ClientCard> { duel.Fields[0].Hand[0], duel.Fields[0].Hand[1] }, new List<long> { 0, 0 }, false);
        Check("chain answered (index or pass)", chainChoice == BrainBridge.Pass || chainChoice == 0 || chainChoice == 1);
        duel.CurrentChain.Clear();
        duel.CurrentChainInfo.Clear();

        // A two-card select-unselect: the second pick should come from the plan without asking Claude again.
        List<ClientCard> mats = new List<ClientCard> { Card(TourGuide, CardLocation.MonsterZone, 0, 0, 1, 1000, 600), Card(8903700, CardLocation.MonsterZone, 1, 0, 1, 1200, 2000), duel.Fields[0].MonsterZone[2] };
        int first = bridge.SelectUnselect(mats, new List<ClientCard>(), 2, 2, false, false, 513);
        Check("select_unselect first pick", first >= 0 && first < 3);
        if (first >= 0)
        {
            List<ClientCard> rest = mats.Where((c, i) => i != first).ToList();
            DateTime t = DateTime.Now;
            int second = bridge.SelectUnselect(rest, new List<ClientCard> { mats[first] }, 2, 2, false, false, 513);
            Check("select_unselect second pick from plan", second >= 0 && second < 2 && (DateTime.Now - t).TotalSeconds < 2);
        }

        // A "!note" from the opponent is acknowledged in chat with the next reply; the explanations aren't sent.
        bridge.Event("chat", new Dictionary<string, object> { { "player", 1 }, { "position", 0 }, { "message", "!bridge test note" }, { "source", "duelist" } });
        int before = chat.Count;
        bool? yes = bridge.SelectEffectYn(duel.Fields[0].MonsterZone[2], ((long)Saffira << 20) | 0);
        Check("effect_yn answered", yes.HasValue);
        Check("feedback note acknowledged", chat.Skip(before).Any(m => m.StartsWith("Noted feedback")));
        Check("no explanation chat", chat.All(m => !m.StartsWith("[")));

        // End of game 1: the game_over round trip carries the result line, then game 2 starts on the same connection.
        bridge.Event("win", new Dictionary<string, object> { { "result", 0 }, { "reason", 1 } });
        before = chat.Count;
        bridge.GameOver(0, 1);
        Check("game over line sent", chat.Count == before + 1);
        Check("at most 4 banter lines in game 1", chat.Count(m => !m.StartsWith("Noted feedback")) <= 4);
        bool? game2First = bridge.SelectFirst();
        Check("game 2: go_first answered", game2First == true);
        duel.Turn = 1; duel.Player = 0;
        bridge.Event("start", new Dictionary<string, object> { { "first", true }, { "lp", new[] { 8000, 8000 } }, { "names", new[] { "Claude", "Tester" } } });
        CardPosition pos2 = bridge.SelectPosition(Saffira, new List<CardPosition> { CardPosition.FaceUpAttack });
        Check("game 2: position answered", pos2 == CardPosition.FaceUpAttack);
        return Environment.ExitCode;
    }

    static byte[] Utf16(string s, int chars)
    {
        byte[] b = new byte[chars * 2];
        byte[] text = Encoding.Unicode.GetBytes(s);
        Array.Copy(text, b, Math.Min(text.Length, b.Length - 2));
        return b;
    }

    // STOC_CHAT_2 as EDOPro's host sends it (generic_duel.cpp Chat): type, is_team, name[20], message.
    static void Chat2Parsing()
    {
        Func<int, bool, string, Dictionary<string, object>> parse = (type, team, text) =>
        {
            MemoryStream ms = new MemoryStream();
            BinaryWriter w = new BinaryWriter(ms);
            w.Write((byte)type); w.Write((byte)(team ? 1 : 0)); w.Write(Utf16("Lazar", 20));
            byte[] msg = Encoding.Unicode.GetBytes(text + "\0");
            w.Write(msg);
            ms.Position = 0;
            return BrainBridge.Chat2Event(new BinaryReader(ms), 0);
        };
        Dictionary<string, object> opp = parse(0, false, "!don't Veiler my Stratos");
        Check("chat2: opponent message", (string)opp["message"] == "!don't Veiler my Stratos" && (int)opp["player"] == 1
            && (string)opp["name"] == "Lazar" && (string)opp["source"] == "duelist");
        Dictionary<string, object> own = parse(0, true, "hi");
        Check("chat2: own team message", (int)own["player"] == 0);
        Dictionary<string, object> spectator = parse(1, false, "!note");
        Check("chat2: spectator message", (string)spectator["source"] == "spectator" && (int)spectator["player"] == 7);
    }
}
