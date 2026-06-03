def brew(coffee_type: str = "espresso") -> str:
    return f"Brewing {coffee_type}"


def main() -> None:
    print(brew())
