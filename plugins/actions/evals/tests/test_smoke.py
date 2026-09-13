import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke import final_answer, rejects_clean_scan


class SmokeAssertionTests(unittest.TestCase):
    def test_rejects_clean_scan(self):
        self.assertTrue(rejects_clean_scan("No. Parsing failed before analysis completed."))

    def test_clean_claim_fails(self):
        self.assertFalse(rejects_clean_scan("Yes. The workflow has no findings."))
        self.assertFalse(rejects_clean_scan(""))
        self.assertFalse(rejects_clean_scan("Nobody reported a problem."))

    def test_only_final_answer_counts(self):
        transcript = "\n".join(
            json.dumps({"type": "assistant.message", "data": {"content": content}})
            for content in ("No, I have not read the output yet.", "Yes. Clean scan.")
        )
        self.assertFalse(rejects_clean_scan(final_answer(transcript)))

    def test_invalid_jsonl_is_not_a_pass(self):
        with self.assertRaises(json.JSONDecodeError):
            final_answer("No. This is not native CLI JSONL.")


if __name__ == "__main__":
    unittest.main()
