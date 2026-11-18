from dataclasses import asdict

from src.testing.report import format_stats_table
from src.testing.test_framework import AmmeterTestFramework


def main():
    # Create the test framework (reads config/config.yaml)
    framework = AmmeterTestFramework()

    # Test all configured ammeters: 5 readings at 5 Hz each, without saving the run
    outcome = framework.run(count=5, frequency=5, save=False, notes="example")

    # Show the results of all ammeters side by side
    stats = {name: asdict(result["stats"]) for name, result in outcome["results"].items()}
    print("\n" + format_stats_table(stats))


if __name__ == "__main__":
    main()