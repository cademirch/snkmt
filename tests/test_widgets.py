import inspect
from snkmt.console.views.overview import WorkflowListView
from snkmt.console.widgets import render_progress_bar


def test_workflow_list_view_posts_selected_message():
    """WorkflowListView must declare a WorkflowSelected message with a workflow_id str."""
    msg_cls = WorkflowListView.WorkflowSelected
    sig = inspect.signature(msg_cls.__init__)
    assert "workflow_id" in sig.parameters


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


def test_workflow_detail_screen_importable():
    from snkmt.console.views.detail import WorkflowDetailScreen
    assert WorkflowDetailScreen is not None
