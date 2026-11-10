"""Guard: the dashboard's Settings number boxes must use the dark surface, not Gradio's light input
background with the default text colour (which rendered the digits white on white).
"""
import re

from dashboard.layout import GRADIO_CSS


def test_number_inputs_get_the_dark_surface_and_readable_text():
    match = re.search(r'input\[type="number"\]\s*\{([^}]*)\}', GRADIO_CSS)
    assert match, "dashboard CSS must style input[type=number] (Settings slider number boxes)"
    rule = match.group(1)
    assert "background:" in rule and "color:" in rule
    assert "!important" in rule
