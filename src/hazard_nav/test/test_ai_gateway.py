import unittest

from hazard_nav.ai_gateway import OPENROUTER_BASE_URL, load_ai_settings


class AIGatewayTests(unittest.TestCase):
    def test_openrouter_is_the_preferred_provider(self):
        settings = load_ai_settings(
            {
                "OPENROUTER_API_KEY": "or-key",
                "OPENAI_API_KEY": "oa-key",
            }
        )

        self.assertEqual(settings.provider, "openrouter")
        self.assertEqual(settings.api_key, "or-key")
        self.assertEqual(settings.base_url, OPENROUTER_BASE_URL)
        self.assertEqual(settings.planner_model, "openrouter/free")
        self.assertEqual(
            settings.transcription_model,
            "openai/whisper-large-v3-turbo",
        )
        self.assertEqual(
            settings.request_extra_body,
            {"provider": {"require_parameters": True}},
        )

    def test_openrouter_values_can_be_overridden(self):
        settings = load_ai_settings(
            {
                "OPENROUTER_API_KEY": "or-key",
                "OPENROUTER_BASE_URL": "https://example.invalid/v1",
                "OPENROUTER_MODEL": "vendor/planner",
                "OPENROUTER_TRANSCRIBE_MODEL": "vendor/transcriber",
                "OPENROUTER_HTTP_REFERER": "https://hazard-nav.invalid",
                "OPENROUTER_APP_NAME": "Rescue Demo",
            }
        )

        self.assertEqual(settings.base_url, "https://example.invalid/v1")
        self.assertEqual(settings.planner_model, "vendor/planner")
        self.assertEqual(settings.transcription_model, "vendor/transcriber")
        self.assertEqual(
            settings.default_headers,
            {
                "HTTP-Referer": "https://hazard-nav.invalid",
                "X-Title": "Rescue Demo",
            },
        )

    def test_native_openai_remains_available(self):
        settings = load_ai_settings(
            {
                "OPENAI_API_KEY": "oa-key",
                "OPENAI_MODEL": "gpt-test",
                "OPENAI_TRANSCRIBE_MODEL": "transcribe-test",
            }
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.planner_model, "gpt-test")
        self.assertEqual(settings.transcription_model, "transcribe-test")
        self.assertIsNone(settings.base_url)
        self.assertIsNone(settings.request_extra_body)

    def test_missing_key_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            load_ai_settings({})


if __name__ == "__main__":
    unittest.main()
