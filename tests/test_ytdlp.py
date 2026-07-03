from tube_explore.models import QualityMode
from tube_explore.ytdlp import _build_audio_format_str, _build_video_format_str


def test_build_video_format_best():
    result = _build_video_format_str(QualityMode.best)
    assert result == "bestvideo+bestaudio/best"


def test_build_video_format_least():
    result = _build_video_format_str(QualityMode.least)
    assert result == "worstvideo+worstaudio/worst"


def test_build_video_format_at_most():
    result = _build_video_format_str(QualityMode.at_most, value=1080)
    assert "height<=1080" in result


def test_build_video_format_at_least():
    result = _build_video_format_str(QualityMode.at_least, value=480)
    assert "height>=480" in result


def test_build_video_format_with_ext():
    result = _build_video_format_str(QualityMode.best, ext="mp4")
    assert "[ext=mp4]" in result


def test_build_video_format_at_most_default():
    result = _build_video_format_str(QualityMode.at_most)
    assert "height<=1080" in result


def test_build_video_format_at_least_default():
    result = _build_video_format_str(QualityMode.at_least)
    assert "height>=480" in result


def test_build_audio_format_best():
    result = _build_audio_format_str(QualityMode.best)
    assert result == "bestaudio/best"


def test_build_audio_format_least():
    result = _build_audio_format_str(QualityMode.least)
    assert result == "worstaudio/worst"


def test_build_audio_format_with_ext():
    result = _build_audio_format_str(QualityMode.best, ext="m4a")
    assert "[ext=m4a]" in result
