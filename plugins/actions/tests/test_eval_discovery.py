import unittest
from unittest import mock

import test_evals


class EvalDiscoveryTests(unittest.TestCase):
    def test_nested_discovery_does_not_reuse_parent_loader(self):
        parent_loader = mock.Mock(spec=unittest.TestLoader)
        parent_loader.discover.side_effect = AssertionError(
            "Nested discovery must not change the parent loader's project root"
        )

        suite = test_evals.load_tests(parent_loader, unittest.TestSuite(), None)

        parent_loader.discover.assert_not_called()
        self.assertIsInstance(suite, unittest.TestSuite)
        self.assertGreater(suite.countTestCases(), 0)
