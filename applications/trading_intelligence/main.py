"""Runtime entry point for the AARA Trading Intelligence application.

Only responsibility: build the application via the composition root
(bootstrap.build_trading_intelligence_app()) and launch the resulting
Gradio interface. All object construction stays in bootstrap.py -- this
module constructs nothing and does not touch sentinel_engine, dashboard,
bot, or database directly.

build_trading_intelligence_app() returns a gr.TabbedInterface (itself a
gr.Blocks subclass) composing every Trading Intelligence screen -- see
bootstrap.py's own docstring on that function; launching it is simply
calling Gradio's own .launch() on that object, so no change to the UI
layer is needed to make the application runnable.

Deployment note: the HF Space this app deploys to (ksri77/aara-trading-
intelligence) is provisioned on ZeroGPU hardware (requested_hardware:
zero-a10g) -- downgrading to cpu-basic requires HF Pro on this account,
confirmed via a live API call (402 Payment Required). ZeroGPU's runtime
refuses to start any Space with no @spaces.GPU function detected at
startup. _zero_gpu_startup_probe() below exists solely to satisfy that
check -- Decision Center has no GPU workload and this function is never
called by the real application.
"""
import spaces

from applications.trading_intelligence.bootstrap import build_trading_intelligence_app


@spaces.GPU
def _zero_gpu_startup_probe() -> None:
    return None


def main() -> None:
    build_trading_intelligence_app().launch()


if __name__ == "__main__":
    main()
