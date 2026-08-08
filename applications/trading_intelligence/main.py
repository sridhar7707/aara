"""Runtime entry point for the AARA Trading Intelligence application.

Only responsibility: build the application via the composition root
(bootstrap.build_application()) and launch the resulting Gradio interface.
All object construction stays in bootstrap.py -- this module constructs
nothing and does not touch sentinel_engine, dashboard, bot, or database
directly.

DecisionCenterUI.build() returns the underlying gr.Blocks instance (see
applications/trading_intelligence/ui/decision_center/gradio_view.py);
launching it is simply calling Gradio's own .launch() on that object, so
no change to the UI layer is needed to make the application runnable.
"""
from applications.trading_intelligence.bootstrap import build_application


def main() -> None:
    decision_center_ui = build_application()
    decision_center_ui.build().launch()


if __name__ == "__main__":
    main()
