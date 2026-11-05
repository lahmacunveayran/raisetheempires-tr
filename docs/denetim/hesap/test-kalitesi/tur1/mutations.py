# (id, file, old, new, description, occurrence)  occurrence: None = must be unique, int = index of occurrence
ES = "empires-server.py"
BE = "battle_engine.py"
M = [
    # ---- empires-server.py: per-save lock
    ("E01", ES, "            lock.acquire()\n", "            pass  # lock.acquire()\n", "open_session: drop lock.acquire()", None),
    ("E01b", ES, [("            lock.acquire()\n", "            pass  # lock.acquire()\n", None),
                  ("    if lock is not None:\n        lock.release()", "    if lock is not None:\n        pass", None)],
     None, "no per-save locking at all (acquire and release both removed)", None),
    ("E02", ES, "lock = self.locks.setdefault(request.cookies.get(app.config[\"SESSION_COOKIE_NAME\"], \"\"),\n                                             threading.Lock())",
     "lock = threading.Lock()", "open_session: a fresh lock per request (no sharing per save)", None),
    ("E03", ES, "    if lock is not None:\n        lock.release()", "    if lock is not None:\n        pass", "teardown: never release the save lock", None),
    # ---- host checks
    ("E04", ES, "        return host.lower() == \"localhost\"", "        return True", "is_known_host: accept every host name", None),
    ("E05", ES, "    host = host.rsplit(\":\", 1)[0] if not host.endswith(\"]\") else host\n", "", "is_known_host: no port stripping", None),
    ("E06", ES, "        return host.lower() == \"localhost\"", "        return \"localhost\" in host.lower()", "is_known_host: substring match (evil-localhost.example passes)", None),
    ("E07", ES, "        if not is_known_host(host):\n            print(\"Blocked request for host\", host)",
     "        if False and not is_known_host(host):\n            print(\"Blocked request for host\", host)", "KnownHostsOnly: host check removed", None),
    ("E08", ES, "    if not is_known_host(request.host):", "    if False:", "before_request reject_unknown_hosts removed", None),
    ("E09", ES, "    host = host.strip(\"[]\")\n", "", "is_known_host: no [] strip for IPv6", None),
    # ---- script_json
    ("E10", ES, ".replace(\"<\", \"\\\\u003c\")", "", "script_json: no '<' escaping", None),
    ("E11", ES, "                           allies=script_json(get_allies_friend(saves)),",
     "                           allies=json.dumps(get_allies_friend(saves), default=lambda o: '<not serializable>'),",
     "home(): allies back to plain json.dumps (unescaped)", 0),
    # ---- wipe / save editor
    ("E12", ES, "        create_backup(\"Before deleting the save game\")", "        pass", "wipe_session: no backup", None),
    ("E13", ES, "    incomplete_quests = [e[\"name\"] for e in session.get('quests', []) if e[\"complete\"] == False]",
     "    incomplete_quests = [e[\"name\"] for e in session['quests'] if e[\"complete\"] == False]", "save_editor: session['quests'] without .get", None),
    ("E14", ES, "        try:\n            save_game = json.loads(request.form['savegame'])\n        except (KeyError, ValueError):\n            return \"Not saved: the save game is not valid JSON\", 400\n",
     "        save_game = json.loads(request.form['savegame'])\n", "save_savegame: no JSON error handling", None),
    ("E15", ES, "    if not isinstance(save_game, dict):\n        return", "    if False:\n        return", "save_savegame: no dict check", None),
    ("E16", ES, "    if not isinstance(save_game.get('quests'), list) or not validate_save(save_game):",
     "    if False:", "save_savegame: no validation before writing", None),
    ("E17", ES, "    if not isinstance(save_game.get('quests'), list) or not validate_save(save_game):",
     "    if not validate_save(save_game):", "save_savegame: quests list check removed", None),
    ("E18", ES, "    if not isinstance(save_game.get('quests'), list) or not validate_save(save_game):",
     "    if not isinstance(save_game.get('quests'), list):", "save_savegame: validate_save removed", None),
    ("E19", ES, "    session['battle'] = save_game.get('battle')", "    session['battle'] = save_game['battle']", "save_savegame: battle without .get", None),
    ("E20", ES, "datetime.fromtimestamp(backup.get('saved_on') or 0)", "datetime.fromtimestamp(backup.get('saved_on', 0))", "format_backup_message: None saved_on", None),
    # ---- served_text
    ("E21", ES, "    return response.decode(\"utf-8\") if isinstance(response, bytes) else response", "    return response", "served_text: bytes mods not decoded", None),
    ("E22", ES, "    if isinstance(response, Response):\n        response.direct_passthrough = False\n", "    if isinstance(response, Response):\n", "served_text: direct_passthrough left on", 1),
    # ---- guarded_call
    ("E23", ES, "            session.clear()\n            session.update(pickle.loads(snapshot))\n    return {\"errorType\": CALL_FAILED",
     "            pass\n    return {\"errorType\": CALL_FAILED", "guarded_call: no snapshot restore", None),
    ("E24", ES, "        with defer_save_writes():\n            response = call_response(reqq, batch_id)",
     "        with contextlib.nullcontext():\n            response = call_response(reqq, batch_id)", "guarded_call: defer_save_writes not used", None),
    ("E25", ES, "            if encode is not None:\n                encode(dict(session))", "            if False:\n                encode(dict(session))", "guarded_call: no encode check", None),
    ("E26", ES, "    return {\"errorType\": CALL_FAILED, \"errorData\": reqq.functionName,", "    return {\"errorType\": 0, \"errorData\": reqq.functionName,", "guarded_call: failure answered as success", None),
    ("E27", ES, "        app.logger.exception(\"Call %s failed, its changes are undone\", reqq.functionName)\n",
     "        app.logger.exception(\"Call %s failed, its changes are undone\", reqq.functionName)\n        raise\n", "guarded_call: re-raise (whole batch fails)", None),
    ("E28", ES, "        if response is not None:\n            return response\n", "        return response\n", "guarded_call: None answer passed through", None),
    ("E29", ES, [("snapshot = pickle.dumps(dict(session), pickle.HIGHEST_PROTOCOL)", "snapshot = dict(session)", 1),
                 ("session.update(pickle.loads(snapshot))", "session.update(snapshot)", 1)],
     None, "guarded_call: shallow dict snapshot instead of deep pickle copy", None),
    ("E30", ES, "            resps.append(no_data_response())", "            resps.append(dummy_response())", "resolveBattle stale: dummy_response instead of no_data_response", None),
    # ---- crew
    ("E31", ES, "        friends = [int(f) if isinstance(f, float) and f.is_integer() else f for f in friends]\n", "", "crew: no float id conversion", None),
    ("E32", ES, "allies.get(str(f), {\"neighbor\": True}).get(\"neighbor\")", "allies.get(str(f), {\"neighbor\": False}).get(\"neighbor\")", "crew: unknown local saves not neighbors", None),
    ("E33", ES, "allies.get(str(f), {\"neighbor\": True}).get(\"neighbor\")", "allies[str(f)][\"neighbor\"]", "crew: allies[...] KeyError", None),
    # ---- 500 handler
    ("E34", ES, "    if settings.crash_log and not (crash_log_editor and crash_log_editor.is_alive()):", "    if settings.crash_log:", "500 handler: no one-editor check", None),
    # ---- playerLevel
    ("E35", ES, "        \"playerLevel\": int(session['user_object'][\"userInfo\"][\"player\"][\"level\"]),", "        \"playerLevel\": 1,", "random_fleet_challenge: playerLevel 1", 0),
    ("E36", ES, "        \"playerLevel\": int(session['user_object'][\"userInfo\"][\"player\"][\"level\"]),", "        \"playerLevel\": 1,", "random_enemy_fleet_challenge: playerLevel 1", 1),
    # ---- AMF undefined / bytearray
    ("E37", ES, "    if obj is pyamf.Undefined:  # what the client sends can end up in the save game\n        return None\n", "", "enc_hook: Undefined not handled", None),
    ("E38", ES, "    if isinstance(obj, pyamf.amf3.ByteArray):\n        return obj.getvalue()\n", "", "enc_hook: ByteArray not handled", None),
    ("E39", ES, "    if value is pyamf.Undefined:\n        return None\n", "", "dense_arrays: Undefined not mapped", None),
    ("E40", ES, "is_0_08a_preview(session.get('save_version'))", "is_0_08a_preview(version)", "user_response: migration check on server version (old bug)", None),

    # ---- save_engine.py
    ("S01", "save_engine.py", "    if pending is not None:\n        pending.append(save)\n    else:\n        write_session(save)", "    write_session(save)", "store_session: never defer", None),
    ("S02", "save_engine.py", "        yield\n        for save in g.pending_saves:\n            write_session(save)\n", "        yield\n", "defer_save_writes: pending saves never written", None),
    ("S03", "save_engine.py", "    try:\n        yield\n        for save in g.pending_saves:\n            write_session(save)\n    finally:\n",
     "    try:\n        yield\n    finally:\n        for save in g.pending_saves:\n            write_session(save)\n", "defer_save_writes: written even when the call fails", None),
    ("S04", "save_engine.py", "    record.data = sess_int.serializer.encode(dict(save))", "    record.data = pickle.dumps(dict(save))", "write_session: back to pickle", None),
    ("S05", "save_engine.py", "    if converted:\n        sess_int.client.session.commit()", "    if converted:\n        pass", "convert_pickled_saves: no commit", None),
    ("S06", "save_engine.py", "        if not data.startswith(b\"\\x80\"):", "        if data.startswith(b\"\\x80\"):", "convert_pickled_saves: inverted pickle check", None),

    # ---- save_migration.py
    ("M01", "save_migration.py", "    try:\n        create_backup(message)\n    except Exception as error:\n        print(\"WARNING: no backup\", repr(message), error)",
     "    create_backup(message)", "backup(): failure propagates", None),
    ("M02", "save_migration.py", "        backup(\"Update to 0.03a\")  # quests and expansions are reset below\n", "", "no backup before 0.03a", None),
    ("M03", "save_migration.py", "        session['save_version'] = target_version\n", "        pass\n", "0.08a: version not updated", None),

    # ---- state_machine.py
    ("SM1", "state_machine.py", "        try:  # a backup that can't be written (backups.db locked, disk full) must not undo the level up\n            create_backup(\"Level \" + level[\"-num\"])\n        except Exception as error:\n            print(\"WARNING: no backup for level\", level[\"-num\"], error)",
     "        create_backup(\"Level \" + level[\"-num\"])", "level up: backup failure propagates", None),

    # ---- logger.py
    ("L01", "logger.py", "        try:\n            return report(*args, **kwargs)\n        except Exception:\n            print(\"Could not report to the log page:\")\n            traceback.print_exc()",
     "        return report(*args, **kwargs)", "never_fails: lets exceptions through", None),
    ("L02", "logger.py", "    res = (response[0] if response else {}) if isinstance(response, list) else response", "    res = response[0] if isinstance(response, list) else response", "report_world_log: IndexError on []", None),
    ("L03", "logger.py", "if isinstance(res, dict) else res", "if not isinstance(res, str) else res", "report_world_log: None response -> AttributeError", None),

    # ---- game_settings.py
    ("G01", "game_settings.py", "for e in simple_list(custom_values)}", "for e in custom_values}", "lookup_state_machine: single define dict", None),
    ("G02", "game_settings.py", "    state_machine = next((e for e in game_settings['settings']['stateMachines']['stateMachine']\n                          if e['-name'] == state_machine_name), None)",
     "    [state_machine] = [e for e in game_settings['settings']['stateMachines']['stateMachine'] if e['-name'] == state_machine_name] or [None]",
     "lookup_raw_state_machine: unpack, duplicates fail", None),
    ("G03", "game_settings.py", "        raise ValueError(\"No state machine \" + str(state_machine_name))", "        return None", "unknown state machine returns None", None),

    # ---- bot_empires.py
    ("B01", "bot_empires.py", "    with open(STATE_PATH + \".tmp\", \"w\", encoding=\"utf-8\") as f:\n        json.dump(state, f)\n    os.replace(STATE_PATH + \".tmp\", STATE_PATH)",
     "    with open(STATE_PATH, \"w\", encoding=\"utf-8\") as f:\n        json.dump(state, f)", "_write_state: direct write, no temp file", None),
    ("B02", "bot_empires.py", "    os.replace(STATE_PATH + \".tmp\", STATE_PATH)", "    pass", "_write_state: temp file never moved in place", None),

    # ---- titan_lab.py
    ("T01", "titan_lab.py", "    if player[\"cash\"] < int(part.get(\"-unlockCost\", 0)):", "    if False:", "unlock_part: no cash check", None),
    ("T02", "titan_lab.py", "    if player[\"cash\"] < int(part.get(\"-unlockCost\", 0)):", "    if player[\"cash\"] <= int(part.get(\"-unlockCost\", 0)):", "unlock_part: exact cash refused (off by one)", None),

    # ---- battle_engine.py
    ("BE01", BE, "    return math.floor(x + 0.5)", "    return round(x)", "as3_round -> Python round", None),
    ("BE02", BE, "        random_roll = as3_round(random * (len(best_units) - 1))", "        random_roll = round(random * (len(best_units) - 1))", "ai_best_unit: round", None),
    ("BE03", BE, "        best_pairing = best_pairings[as3_round(roll_random_between(", "        best_pairing = best_pairings[round(roll_random_between(", "ai_best_attack pairing: round", None),
    ("BE04", BE, "        selected_random_consumable = as3_round(selected_random_consumable_roll)", "        selected_random_consumable = round(selected_random_consumable_roll)", "ally consumable pick: round", None),
    ("BE05", BE, "                    targeted_baddie = live_baddies_index[as3_round(", "                    targeted_baddie = live_baddies_index[round(", "power target baddie: round", None),
    ("BE06", BE, "                        as3_round(roll_random_between(0, len(live_friendly_index) - 1))]", "                        round(roll_random_between(0, len(live_friendly_index) - 1))]", "power target friendly: round", None),
    ("BE07", BE, "        baddie_attack_strength = get_unit_attack_strength(baddies[enemy_unit_id], False, params)", "        baddie_attack_strength = get_unit_max_strength(baddies[enemy_unit_id], False, params)", "enemy attack strength -> max strength", None),
    ("BE08", BE, "        friendly_attack_strength = get_unit_attack_strength(friendlies[player_unit_id], True)", "        friendly_attack_strength = get_unit_max_strength(friendlies[player_unit_id], True)", "player attack strength -> max strength", None),
    ("BE09", BE, "        if killed:\n            handle_quest_progress(meta, progress_battle_damage_count(\"battleKill\"", "        if True:\n            handle_quest_progress(meta, progress_battle_damage_count(\"battleKill\"", "consumable: kill rewards on every hit", None),
    ("BE10", BE, "            if damage > 0:\n                doBattleRewards(", "            if True:\n                doBattleRewards(", "unit hit: rewards (and reward roll) for 0 damage", None),
    ("BE11", BE, "doBattleRewards(hit_type, baddie_attack_strength, damage, friendly_strength, glancing=not hit)", "doBattleRewards(hit_type, baddie_attack_strength, damage, friendly_strength, glancing=False)", "unit hit: glancing hits pay coins", None),
    ("BE12", BE, "                if damage > 0:\n                    doLossRewards(friendlies[player_unit_id], damage)\n", "", "unit kill of player: no loss rewards", None),
    ("BE13", BE, "doBattleRewards(hit_type, baddie_attack_strength, damage, friendly_strength, glancing=not hit)", "doBattleRewards(hit_type, baddie_attack_strength, damage, friendly_attack_strength, glancing=not hit)", "rare type from full strength instead of strength left", None),
    ("BE14", BE, "if grade == max_grade_2 and grade >= 0]", "if grade == max_grade_2]", "ai_best_attack method 2: no grade >= 0", None),
    ("BE15", BE, "        active_consumables.append(({\"consumable\": {}}, (\"AI tried\", None), -1))\n", "", "AI assign: no 'AI tried' marker", None),
    ("BE16", BE, "                   and (baddie_strengths[i] > 0 or \"controller\" in get_unit_types(b))\n", "", "AI casters include killed units", None),
    ("BE17", BE, "(baddie_strengths[i] > 0 or \"controller\" in get_unit_types(b))", "(baddie_strengths[i] > 0)", "AI casters: dead Titan controllers dropped", None),
    ("BE18", BE, "(\"AI tried\", None), -1))", "(\"AI tried\", None), 5))", "AI tried markers outlive the turn", None),
    ("BE19", BE, "        grade = 'good'\n    elif defender_type in chain.get('-great', '').split(','):", "        grade = 'poor'\n    elif defender_type in chain.get('-great', '').split(','):", "unknown kind grade poor", None),
    ("BE20", BE, "            strength = as3_round(strength)  # WorldUpgradeManager", "            strength = strength  # WorldUpgradeManager", "research: no rounding", None),
    ("BE21", BE, "            strength = as3_round(strength)  # WorldUpgradeManager", "            strength = round(strength)  # WorldUpgradeManager", "research: Python round", None),
    ("BE22", BE, "    invasion = save['user_object'][\"pvp\"][\"invaders\"].get(\"u\" + str(get_zid())) if save else None", "    invasion = save['user_object'][\"pvp\"][\"invaders\"][\"u\" + str(get_zid())]", "invasion_complete: no .get", None),
    ("BE23", BE, "        bot_empires.store_save(save)\n    bot_empires.battle_won(enemy_fleet_uid)", "        bot_empires.store_save(save)\n        bot_empires.battle_won(enemy_fleet_uid)", "invasion_complete: win not counted without invasion", None),
    ("BE24", BE, "            damage += 1  # the client adds the 1", "            pass  # the client adds the 1", "power direct hit: no +1 damage", None),
    ("BE25", BE, "                colateral_damage += 1\n", "", "power collateral: no +1 damage", None),
    ("BE26", BE, "            if collateral_unit_current_strength > 0:  # not the unit the power killed itself", "            if True:", "collateral rewards also for already dead units", None),
    ("BE27", BE, "    roll_reward_random_float()  # DooberManager", "    pass  # DooberManager", "doBattleRewards: no doober roll", None),
    ("BE28", BE, "reward.get('-percent') and mastery_scalar == 1:", "reward.get('-percent'):", "energy roll even with mastery", None),
    ("BE29", BE, "    coin_count = 0 if glancing else 3 if hit_type == \"criticalkill\" else 1", "    coin_count = 3 if hit_type == \"criticalkill\" else 1", "glancing pays coins in doBattleRewards", None),
    ("BE30", BE, "    xp = math.ceil(xp * mastery_scalar)", "    xp = xp", "xp not scaled by mastery", None),
    ("BE31", BE, "    coin_amount = as3_round(coin_amount * mastery_scalar) * coin_count", "    coin_amount = math.ceil(coin_amount * mastery_scalar) * coin_count", "coin mastery: ceil instead of round", None),
    ("BE32", BE, "    resources['oil'] += math.ceil(strength * 0.001)", "    resources['oil'] += math.ceil(strength * 0.01)", "loss oil multiplier x10", None),
    ("BE33", BE, "    rare = next((rares[cost] for cost in unit.get(\"cost\", {}) if cost in rares), None)", "    rare = next((rares[cost] for cost in reversed(list(unit.get(\"cost\", {}))) if cost in rares), None)", "loss rare: last rare in cost, not first", None),
    ("BE34", BE, "    elif killed:\n        doLossRewards(unit, damage)", "    elif killed:\n        pass", "power kill of player unit: no loss loot", None),
    ("BE35", BE, "        handle_quest_progress(meta, progress_battle_damage_count(\"battleDamage\", damage, {}, unit))\n", "", "power hit: no battleDamage progress", None),
    ("BE36", BE, "    \"playerLevel\": int(session['user_object'][\"userInfo\"][\"player\"][\"level\"]),", "    \"playerLevel\": 1,", "survival fleet playerLevel 1", None),
    ("BE37", BE, "entries[-1])[attribute])", "entries[-1])[\"-strength\"])", "Titan attackStrength ignored", None),
    ("BE38", BE, "            if roll_reward_random_float() <= float(reward['-percent']):", "            if roll_reward_random_float() < float(reward['-percent']):", "energy roll boundary <= -> <", None),
    ("BE39", BE, "    rare_count = 3 if hit_type == \"criticalkill\" else 1 if hit_type == \"criticalhit\" else 0", "    rare_count = 3 if hit_type == \"criticalkill\" else 0", "criticalhit pays no rare", None),
    ("BE40", BE, "    rare_amount *= math.ceil(rare_count * mastery_scalar)", "    rare_amount *= rare_count", "rare not scaled by mastery", None),
    ("BE41", BE, "            doBattleRewards(\"kill\", get_unit_attack_strength(unit, False, params), damage, None)", "            doBattleRewards(\"kill\", get_unit_max_strength(unit, False, params), damage, None)", "power kill coins from max strength", None),
    ("BE42", BE, "                strength += strength * float(mod_damage) / 100", "                strength += int(strength * float(mod_damage) / 100)", "research percent truncated before rounding", None),
]
