import unittest
from pathlib import Path


EVAL_TESTS = Path(__file__).resolve().parents[1] / "evals" / "tests"


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    return loader.discover(
        str(EVAL_TESTS),
        pattern="test_*.py",
        top_level_dir=str(EVAL_TESTS),
    )
