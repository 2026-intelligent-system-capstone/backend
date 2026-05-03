from core.config.base import CommonSettings


def test_media_transcription_is_enabled_by_default_for_supported_media():
    settings = CommonSettings()

    assert settings.MEDIA_TRANSCRIPTION_ENABLED is True
