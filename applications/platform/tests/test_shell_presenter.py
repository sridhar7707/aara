"""Tests for applications.platform.shell.shell_presenter.ShellPresenter."""
from applications.platform.identity.user import User
from applications.platform.navigation.navigation_item import NavigationItem
from applications.platform.navigation.navigation_model import NavigationModel
from applications.platform.shell.shell_presenter import ShellPresenter


def _make_item(**overrides):
    defaults = dict(
        product_id="trading_intelligence",
        workspace_id="trading_intelligence.decision_center",
        label="Decision Center",
        order=0,
        visibility="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return NavigationItem(**defaults)


def test_navigation_transforms_correctly():
    first = _make_item(workspace_id="trading_intelligence.decision_center", order=0)
    second = _make_item(
        workspace_id="trading_intelligence.portfolio", label="Portfolio", order=1
    )
    model = NavigationModel(current_user=None, items=[first, second])

    view = ShellPresenter().present(model)

    assert view.navigation == [first, second]


def test_user_information_preserved():
    user = User(user_id="user-001", display_name="Jordan Smith")
    model = NavigationModel(current_user=user, items=[])

    view = ShellPresenter().present(model)

    assert view.current_user == user


def test_empty_navigation_works():
    model = NavigationModel(current_user=None, items=[])

    view = ShellPresenter().present(model)

    assert view.current_user is None
    assert view.navigation == []
