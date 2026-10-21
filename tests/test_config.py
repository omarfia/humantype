"""Tests for configuration loading and CLI/GUI overrides."""

from types import SimpleNamespace

from humantype.config import load_settings


def _args(**kwargs):
    defaults = dict(
        config=None, profile=None, wpm=None, countdown=None, error_rate=None,
        uncorrected_rate=None, backend=None, seed=None, sessions=None,
        schedule=None, save_interval=None, word_autocorrect=None,
        keep_originals=False, dry_run=False, allow_mouse=False, log=None,
        no_log=False, verify_docx=None, no_verify=True,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_auto_save_off_by_default():
    cfg = load_settings(_args())
    assert cfg.logging.save_interval_minutes == 0


def test_save_interval_cli_override():
    cfg = load_settings(_args(save_interval=4))
    assert cfg.logging.save_interval_minutes == 4


def test_save_interval_zero_disables():
    cfg = load_settings(_args(save_interval=0))
    assert cfg.logging.save_interval_minutes == 0


def test_other_overrides_still_work():
    cfg = load_settings(_args(wpm=60, error_rate=0.05, word_autocorrect="off"))
    assert cfg.typing.wpm == 60
    assert cfg.typing.error_rate == 0.05
    assert cfg.typing.word_autocorrect == "off"
