#!/usr/bin/env python3
import datetime as dt
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_DIR / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from equity_screener.freshness import freshness_decision


class FreshnessGuardTest(unittest.TestCase):
    def test_retries_refresh_when_pricing_data_is_more_than_50h_stale_even_on_weekend(self):
        now = dt.datetime(2026, 6, 28, 21, 30, tzinfo=dt.timezone.utc)  # Sunday
        latest = now - dt.timedelta(hours=53)

        decision = freshness_decision(latest, now)

        self.assertTrue(decision.should_retry_refresh)
        self.assertFalse(decision.ok_to_build)
        self.assertIn('re-attempt warehouse refresh', decision.message)

    def test_weekend_build_allowed_after_retry_if_under_weekend_threshold(self):
        now = dt.datetime(2026, 6, 28, 21, 30, tzinfo=dt.timezone.utc)  # Sunday
        latest = now - dt.timedelta(hours=53)

        decision = freshness_decision(latest, now, refresh_already_retried=True)

        self.assertFalse(decision.should_retry_refresh)
        self.assertTrue(decision.ok_to_build)
        self.assertEqual(decision.threshold_hours, 80)

    def test_weekday_stale_after_retry_refuses_build(self):
        now = dt.datetime(2026, 6, 29, 21, 30, tzinfo=dt.timezone.utc)  # Monday
        latest = now - dt.timedelta(hours=53)

        decision = freshness_decision(latest, now, refresh_already_retried=True)

        self.assertFalse(decision.should_retry_refresh)
        self.assertFalse(decision.ok_to_build)
        self.assertEqual(decision.threshold_hours, 30)


if __name__ == '__main__':
    unittest.main()
