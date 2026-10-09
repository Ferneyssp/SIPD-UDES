from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from config.risk import RiskLevel, classify_risk, get_thresholds


class RiskThresholdTests(SimpleTestCase):
    def test_default_thresholds(self):
        self.assertEqual(get_thresholds(), {"low": 0.30, "medium": 0.60})

    def test_boundaries(self):
        self.assertEqual(classify_risk(0.0), RiskLevel.LOW)
        self.assertEqual(classify_risk(0.2999), RiskLevel.LOW)
        self.assertEqual(classify_risk(0.30), RiskLevel.MEDIUM)
        self.assertEqual(classify_risk(0.5999), RiskLevel.MEDIUM)
        self.assertEqual(classify_risk(0.60), RiskLevel.HIGH)
        self.assertEqual(classify_risk(1.0), RiskLevel.HIGH)

    @override_settings(RISK_LOW_THRESHOLD=0.2, RISK_MEDIUM_THRESHOLD=0.5)
    def test_thresholds_are_configurable(self):
        self.assertEqual(classify_risk(0.25), RiskLevel.MEDIUM)
        self.assertEqual(classify_risk(0.55), RiskLevel.HIGH)

    @override_settings(RISK_LOW_THRESHOLD=0.7, RISK_MEDIUM_THRESHOLD=0.5)
    def test_invalid_threshold_configuration(self):
        with self.assertRaises(ImproperlyConfigured):
            classify_risk(0.4)

    def test_invalid_probability(self):
        with self.assertRaises(ValueError):
            classify_risk(1.5)
