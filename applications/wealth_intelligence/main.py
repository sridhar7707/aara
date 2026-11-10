"""Runtime entry point for the AARA Wealth Intelligence application.

Only responsibility: build the application via the composition root
(bootstrap.build_application()) and launch the resulting Gradio interface.
All object construction stays in bootstrap.py -- this module constructs
nothing and does not touch sentinel_engine, dashboard, bot, or database
directly.

InvestorWorkspaceUI.build() returns the underlying gr.Blocks instance
(see applications/wealth_intelligence/ui/investor_workspace.py); launching
it is simply calling Gradio's own .launch() on that object, so no change
to the UI layer is needed to make the application runnable.
"""
import spaces

from applications.wealth_intelligence.bootstrap import build_application


# The Space runs on ZeroGPU (requested_hardware zero-a10g). ZeroGPU refuses to start any
# Space with no @spaces.GPU function detected at startup, and this app has no GPU workload.
# This probe exists only to satisfy that check; it is never called by the application.
@spaces.GPU
def _zero_gpu_startup_probe() -> None:
    return None


def main() -> None:
    workspace_ui = build_application()
    workspace_ui.build().launch()


if __name__ == "__main__":
    main()
