from datetime import datetime
from typing import Any

from tube_explore.models import ConversionPreset, QualityMode
from tube_explore.ytdlp import _build_audio_format_str, _build_conversion_args, _build_video_format_str


def _make_preset(**overrides: Any) -> ConversionPreset:
    base: dict[str, Any] = dict(
        id=0, name="test", container="mp4", output_ext="mp4",
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    base.update(overrides)
    return ConversionPreset(**base)


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
    """When no value provided for at_most, fallback to 1080."""
    result = _build_video_format_str(QualityMode.at_most)
    assert "height<=1080" in result


def test_build_video_format_at_least_default():
    """When no value provided for at_least, fallback to 480."""
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


def test_build_conversion_args_simple():
    preset = _make_preset()
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    assert "-i" in args
    assert "in.mp4" in args
    assert "out.mp4" in args
    assert "-y" in args


def test_build_conversion_args_video_codec():
    preset = _make_preset(video_codec="h264")
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    assert "-c:v" in args
    assert "libx264" in args


def test_build_conversion_args_video_hevc():
    preset = _make_preset(video_codec="hevc")
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    assert "libx265" in args


def test_build_conversion_args_audio():
    preset = _make_preset(audio_codec="aac", audio_bitrate="256k")
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    assert "-c:a" in args
    assert "aac" in args
    assert "-b:a" in args
    assert "256k" in args


def test_build_conversion_args_scale():
    preset = _make_preset(max_width=1920, max_height=1080)
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    vf_idx = args.index("-vf")
    assert "scale=1920:1080" in args[vf_idx + 1]


def test_build_conversion_args_all_params():
    preset = _make_preset(
        video_codec="h264", video_bitrate="5M", video_fps=30,
        video_preset="slow", video_pixfmt="yuv420p",
        audio_codec="aac", audio_bitrate="192k",
        audio_samplerate=48000, audio_channels=2,
    )
    args = _build_conversion_args("in.mp4", "out.mp4", preset)
    assert "libx264" in args
    assert "5M" in args
    assert "30" in args or "30.0" in args
    assert "slow" in args
    assert "yuv420p" in args
    assert "192k" in args
    assert "48000" in args or 48000 in [int(a) for a in args if a.isdigit()]
