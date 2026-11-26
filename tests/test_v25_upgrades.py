"""tests/test_v25_upgrades.py – Positive & Negative tests for KanbanBoard v2.5 viewer scaling & UI fixes."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import viewer


class TestV25ScalingAndNormalization(unittest.TestCase):
    def test_normalize_tickets_handles_dict_owner_and_strips_heavy_fields_in_summary(self):
        raw = {
            "board": {
                "projects": [
                    {
                        "slug": "memberberries",
                        "doc": "Project Charter text",
                        "epics": [{"slug": "release", "doc": "Epic Spec text"}],
                        "tickets": [
                            {
                                "reference": "memberberries/release/T003",
                                "id": "T003",
                                "epic": "release",
                                "status": "backlog",
                                "title": "Package memb",
                                "owner": {"agent": "claude-code", "lease_until": "2026-11-25T00:00:00Z"},
                                "lease_status": "Lease Expired",
                                "body": "\n\n## Outcome\nShip v1.0\n",
                                "dag_nodes": [
                                    {"id": "A1", "checked": True, "text": "Step 1"},
                                    {"id": "A2", "checked": False, "text": "Step 2"},
                                ],
                                "execution_log": [{"ts": "2026-11-25", "node": "A1", "proof": "ok"}],
                            },
                            {
                                "reference": "memberberries/release/T004",
                                "id": "T004",
                                "epic": "release",
                                "status": "backlog",
                                "title": "Unassigned dict owner",
                                "owner": {},
                                "lease_status": "unclaimed",
                                "body": "## Outcome\nClean",
                                "dag_nodes": [],
                            },
                        ],
                    }
                ]
            }
        }
        summaries, details = viewer._normalize_tickets(raw)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["agent"], "claude-code")
        self.assertTrue(summaries[0]["lease_expired"])
        self.assertEqual(summaries[0]["todo_done"], 1)
        self.assertEqual(summaries[0]["todo_total"], 2)
        self.assertNotIn("body", summaries[0])  # Lightweight summary!
        self.assertEqual(summaries[1]["agent"], "")  # Never [object Object]!
        self.assertIn("body", details["memberberries/release/T003"])
        self.assertEqual(details["memberberries/release/T003"]["epic_doc"], "Epic Spec text")

    def test_board_html_prefills_boss_and_uses_slide_to_approve(self):
        html = (ROOT / "resources" / "board.html").read_text(encoding="utf-8")
        self.assertIn('id="m-approver" value="Boss"', html)
        self.assertIn('id="slide-approve"', html)
        self.assertNotIn('id="btn-submit-approve"', html)

    def test_board_js_has_no_inline_style_attrs_for_csp(self):
        js = (ROOT / "resources" / "board.js").read_text(encoding="utf-8")
        self.assertIn("<progress class=\"card-progress\"", js)
        self.assertNotIn('style="width:', js)
        self.assertNotIn("style=", js)

    def test_ui_action_buttons_provide_worked_and_failed_feedback(self):
        html = (ROOT / "resources" / "board.html").read_text(encoding="utf-8")
        css = (ROOT / "resources" / "board.css").read_text(encoding="utf-8")
        js = (ROOT / "resources" / "board.js").read_text(encoding="utf-8")

        self.assertIn('id="kb-toast"', html)
        self.assertIn(".btn-feedback-ok", css)
        self.assertIn(".btn-feedback-err", css)
        self.assertIn(".kb-toast.ok", css)
        self.assertIn(".kb-toast.err", css)
        self.assertIn("copyTextWithFallback", js)
        self.assertIn("handleCopyButton", js)
        self.assertIn("flashButtonFeedback", js)
        self.assertIn("Copied ✓", js)
        self.assertIn("Failed ✕", js)
        self.assertIn("Copied ref:", js)
        self.assertIn("Refresh failed:", js)


if __name__ == "__main__":
    unittest.main()
