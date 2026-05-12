import pytest
from snkmt.console.views.overview import WorkflowListView


def test_workflow_list_view_posts_selected_message():
    """WorkflowListView must declare a WorkflowSelected message with a workflow_id str."""
    msg_cls = WorkflowListView.WorkflowSelected
    import inspect
    sig = inspect.signature(msg_cls.__init__)
    assert "workflow_id" in sig.parameters
