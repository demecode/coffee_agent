from coffee_agent import brew


def test_brew_defaults_to_espresso() -> None:
    assert brew() == "Brewing espresso"
