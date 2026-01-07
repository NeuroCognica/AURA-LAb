"""Experiment entrypoints.

Each experiment module should expose a `run(**kwargs)` function.
"""

from __future__ import annotations

from typing import Callable, Dict


def get_experiments() -> Dict[str, Callable[..., object]]:
    """Returns a mapping of experiment names to their run callables."""
    # Import locally to keep import time fast and avoid heavy deps unless needed.
    from . import experiment1
    from . import experiment2_sawtooth
    from . import experiment3_floquet_scattering
    from . import experiment4_thermal_decoherence
    from . import experiment4b_langevin_damping
    from . import experiment4c_floquet_langevin
    from . import experiment4d_high_power
    from . import experiment4e_thermal_stress_optimized
    from . import experiment5_active_feedback
    from . import experiment5b_demon_controls
    from . import experiment6_qsic

    return {
        "experiment1": experiment1.run,
        "experiment2_sawtooth": experiment2_sawtooth.run,
        "experiment3_floquet_scattering": experiment3_floquet_scattering.run,
        "experiment4_thermal_decoherence": experiment4_thermal_decoherence.run,
        "experiment4b_langevin_damping": experiment4b_langevin_damping.run,
        "experiment4c_floquet_langevin": experiment4c_floquet_langevin.run,
        "experiment4d_high_power": experiment4d_high_power.run,
        "experiment4e_thermal_stress_optimized": experiment4e_thermal_stress_optimized.run,
        "experiment5_active_feedback": experiment5_active_feedback.run,
        "experiment5b_demon_controls": experiment5b_demon_controls.run,
        "experiment6_qsic": experiment6_qsic.run,
    }
