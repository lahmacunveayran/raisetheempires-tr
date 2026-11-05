def test_the_easy_bots_are_beaten_more_often(monkeypatch, tmp_path):
    """A measurement of bot_empires' design, not of a number taken from it.

    What is measured: 81 random squads (3 to 5 recent units, players of level 10 to 90) fight the 15 bots that
    defense_fleet builds for them, 3 battles each, played by play() with the engine's random numbers
    (EngineRandom) from a fixed seed. play() is a copy of battle_engine's battle rules written in this test; it is
    not its own oracle: every 100th battle of this sample is played again by battle_engine.battle_complete_response
    itself and must end the same (test_the_battles_played_here_are_the_engines does the same for other squads).

    What is expected, from bot_empires' docstring, not from running it: the bots of the five steps
    (GlobalPVPPlayerDelta -2, -1, 0, +2, +4) are easier the lower the step, the bot of the player's level is
    "a nearly even match" (HANDICAP), so the easiest are beaten more than half the time and the hardest less.
    "Nearly even" is taken as within 8 points of half; with HANDICAP 0 (an exact mirror) the docstring has the
    player win about 38%, outside it. What the player wins depends mostly on the squads drawn, so the sample has
    many squads and few battles."""
    monkeypatch.setattr(battle_engine, "report_battle_log", lambda *a: None)
    rng = random.Random(7)
    wins, games = [0] * len(bot_empires.DELTAS), [0] * len(bot_empires.DELTAS)
    replayed = 0
    with app.test_request_context():
        session.sid = "0"
        for level in range(10, 100, 10):
            for _ in range(9):
                units = random_squad(rng, level)
                setup_session(monkeypatch, tmp_path, level=level, units=units)
                player = [(kind(u), strength(u)) for u in units]
                fleets = [[u.split(",")[0] for u in bot_empires.defense_fleet(bot)] for bot in bot_empires.bots()]
                for i, fleet in enumerate(fleets):
                    for _ in range(3):
                        w, z = rng.randrange(1, 2 ** 32), rng.randrange(1, 2 ** 32)
                        player_left, bot_left = play(player, [(kind(u), strength(u)) for u in fleet],
                                                     EngineRandom(w, z))
                        if sum(games) % 100 == 0:
                            with contextlib.redirect_stdout(io.StringIO()):  # the engine prints a lot
                                assert engine_play(units, fleet, w, z) == (player_left, bot_left)
                            replayed += 1
                        wins[i // 3] += sum(player_left) > sum(bot_left)
                        games[i // 3] += 1
    rates = [w / g for w, g in zip(wins, games)]
    print("player wins by step", [round(r, 2) for r in rates], "battles replayed by the engine", replayed)
    assert games == [81 * 9] * 5 and replayed == 37
    assert rates[0] > rates[1] > rates[2] > rates[3] > rates[4]
    assert abs(rates[2] - 0.5) <= 0.08
    assert rates[0] > 0.5 > rates[4]
