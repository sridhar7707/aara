"""Transforms NavigationModel into PlatformShellView.

Presentation model only: no frontend code, no routes, no React, no
authentication. A direct field transformation today -- kept as its own
class/method (not inlined into NavigationBuilder) so future view-specific
shaping (e.g. grouping by product) has a natural home without needing to
touch NavigationBuilder's own responsibility.
"""
from applications.platform.navigation.navigation_model import NavigationModel
from applications.platform.shell.platform_shell_view import PlatformShellView


class ShellPresenter:
    def present(self, navigation_model: NavigationModel) -> PlatformShellView:
        return PlatformShellView(
            current_user=navigation_model.current_user,
            navigation=list(navigation_model.items),
        )
