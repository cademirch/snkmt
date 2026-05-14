from snkmt.console.widgets import render_progress_bar


def test_progress_bar_empty():
    result = render_progress_bar(0.0)
    assert result.plain == "0%"


def test_progress_bar_full():
    result = render_progress_bar(1.0)
    assert result.plain == "100%"


def test_progress_bar_half():
    result = render_progress_bar(0.5)
    assert result.plain == "50%"


def test_progress_bar_clamps():
    result = render_progress_bar(1.5)
    assert result.plain == "100%"
