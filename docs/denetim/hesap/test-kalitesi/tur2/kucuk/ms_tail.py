def test_playable_series_have_quests_and_entry_buildings():
    """Every series reads as the XML has it: its quests stage after stage, ending with the reward quest, and its
    entry building."""
    assert set(megaseries.SERIES) == set(xml_series())
    assert len(megaseries.PLAYABLE) >= 2  # the next tests offer two series one after the other
    for series_id in megaseries.SERIES:
        quests = xml_quests(series_id)
        assert megaseries.nodes(megaseries.SERIES[series_id]) == quests
        assert quests[-1] == xml_series()[series_id].get("rewardQuest")
    for series_id in megaseries.PLAYABLE:
        assert megaseries.entry_item(megaseries.SERIES[series_id])["-name"] == \
            xml_series()[series_id].get("entryPointName")


def test_login_offers_a_series_with_building_experiment_and_first_quest():
    with app.test_request_context():
        setup_session()
        user, new_quests = login()
        player = user["userInfo"]["player"]

        series_id = first_offered(40)
        assert player["megaseriesList"] == {series_id: xml_quests(series_id)[0]}
        assert [q["name"] for q in new_quests] == [xml_quests(series_id)[0]]
        name, variant = xml_experiment(series_id)
        assert user["experiments"][name] == variant
        entry_name = xml_series()[series_id].get("entryPointName")
        entry = [o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == entry_name]
        assert len(entry) == 1 and entry[0]["state"] == "0" and entry[0]["id"] == 101  # globalObjectId 100 + 1

        login()  # nothing new while the series is not finished
        assert list(player["megaseriesList"]) == [series_id]
        assert len([o for o in user["userInfo"]["world"]["objects"] if o["itemName"] == entry_name]) == 1


def test_no_series_without_water_or_below_level():
    with app.test_request_context():
        setup_session(with_water=False)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}
        lowest = min(int(xml_series()[s].find("criteria/level").get("min")) for s in megaseries.PLAYABLE)
        setup_session(level=lowest - 1)
        user, _ = login()
        assert user["userInfo"]["player"]["megaseriesList"] == {}
        setup_session(level=lowest)
        user, _ = login()
        assert list(user["userInfo"]["player"]["megaseriesList"]) == [first_offered(lowest)]


def test_finished_series_keeps_its_key_and_makes_room_for_the_next():
    with app.test_request_context():
        user = setup_session()
        login()
        player = user["userInfo"]["player"]
        first = first_offered(40)
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in xml_quests(first)]

        login()

        second = first_offered(40, skip=[first])
        assert player["megaseriesList"] == {first: xml_series()[first].get("rewardQuest"),
                                            second: xml_quests(second)[0]}
        assert player["megaseriesFinished"] == [first]


def test_reset_starts_the_series_again():
    with app.test_request_context():
        user = setup_session()
        login()
        series_id = first_offered(40)
        quests = xml_quests(series_id)
        session["quests"][:] = [{"name": q, "complete": True, "expired": False, "progress": [], "completedTasks": 0}
                                for q in quests[:3]]

        megaseries.reset_response([series_id])

        assert [q["name"] for q in session["quests"]] == [quests[0]]
        assert session["quests"][0]["complete"] is False
        assert user["userInfo"]["player"]["megaseriesList"][series_id] == quests[0]
