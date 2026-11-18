"""What the chat understands in a message: the shopping list, reminders, and how long home."""

from datetime import datetime

from custom_components.hus_chat.smart import eta_minutes, reminder, shop_items

NOW = datetime(2026, 11, 18, 14, 0)  # a Wednesday


def test_shopping_list():
    assert shop_items("køb mælk, brød og æg") == ["Mælk", "Brød", "Æg"]
    assert shop_items("Husk at købe ost") == []  # "købe" is not "køb ..." - left alone
    assert shop_items("buy milk and eggs") == ["Milk", "Eggs"]
    assert shop_items("Kan du købe mælk?") == []
    assert shop_items("Jeg køber pizza") == []
    assert shop_items("køb lige kaffe") == ["Kaffe"]


def test_reminders():
    r = reminder("mind mig om tandlæge i morgen kl. 8", NOW)
    assert r["when"] == datetime(2026, 11, 19, 8, 0) and r["what"] == "Tandlæge" and not r["all"]
    assert reminder("mind mig om at tage vasketøjet om 20 min", NOW)["when"] == datetime(2026, 11, 18, 14, 20)
    r = reminder("mind os om fodbold på fredag kl 17:30", NOW)
    assert r["when"] == datetime(2026, 11, 20, 17, 30) and r["all"] and r["what"] == "Fodbold"
    assert reminder("mind mig om skraldespanden i aften", NOW)["when"] == datetime(2026, 11, 18, 19, 0)
    assert reminder("mind mig om medicin kl 9", NOW)["when"] == datetime(2026, 11, 19, 9, 0)  # 9 has passed: tomorrow
    assert reminder("remind me to call mum in 2 hours", NOW)["what"] == "Call mum"
    assert reminder("mind mig om noget", NOW) is None  # no time: nothing guessed
    assert reminder("hej med dig", NOW) is None


def test_eta():
    assert eta_minutes(55.6761, 12.5683, 55.6761, 12.5683) == 0
    assert 20 <= eta_minutes(55.70, 12.40, 55.6761, 12.5683) <= 40
    assert eta_minutes(None, None, 55.0, 12.0) is None
