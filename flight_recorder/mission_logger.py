from __future__ import annotations

import datetime
import os
import sys
import uuid
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Dict, Optional


@dataclass
class FlightRecorder:
    """Context manager that captures stdout + writes a Markdown report per run."""

    experiment_name: str
    author: str = "Hermes"
    base_dir: str = "mission_logs"

    id: str = field(init=False)
    timestamp: str = field(init=False)
    folder_name: str = field(init=False)

    console_output: StringIO = field(init=False)
    original_stdout: Any = field(init=False)
    metrics: Dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_name = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in self.experiment_name)
        self.folder_name = os.path.join(self.base_dir, f"{self.timestamp}_{safe_name}_{self.id}")
        self.console_output = StringIO()
        self.original_stdout = sys.stdout

    def __enter__(self) -> "FlightRecorder":
        os.makedirs(self.folder_name, exist_ok=True)
        sys.stdout = self.console_output
        print(f"--- MISSION START: {self.experiment_name} [{self.id}] ---")
        return self

    def log_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value
        print(f"[TELEMETRY] {key}: {value}")

    def save_plot(self, fig: Any, filename: str = "visual_telemetry.png") -> str:
        path = os.path.join(self.folder_name, filename)
        fig.savefig(path, dpi=150)
        print(f"[VISUAL] Saved telemetry to {path}")
        return path

    def write_report(
        self,
        *,
        status: str,
        outcome: str,
        net_impulse: Optional[float] = None,
        plot_filename: str = "visual_telemetry.png",
        error: Optional[str] = None,
    ) -> str:
        report_path = os.path.join(self.folder_name, "COUNCIL_REPORT.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# AURA PROPULSION REPORT: {self.experiment_name}\n")
            f.write(
                f"**Date:** {self.timestamp} | **ID:** {self.id} | **Author:** {self.author}\n"
            )
            f.write(f"**Status:** `{status}` | **Outcome:** `{outcome}`\n\n")

            f.write("## 1. Executive Summary\n")
            if net_impulse is not None:
                f.write(f"> **Net Impulse:** `{net_impulse:.6e}`\n")
            for k, v in self.metrics.items():
                if k == "Net Impulse":
                    continue
                f.write(f"> **{k}:** {v}\n")

            f.write("\n## 2. Visual Telemetry\n")
            f.write(f"![Telemetry Graph]({plot_filename})\n")

            f.write("\n## 3. Mission Transcript (Stdout)\n")
            f.write("```text\n")
            f.write(self.console_output.getvalue())
            f.write("```\n")

            if error:
                f.write("\n## 4. Error Logs\n")
                f.write(f"```\n{error}\n```\n")

        return report_path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        sys.stdout = self.original_stdout

        status = "SUCCESS" if exc_type is None else "CRITICAL FAILURE"
        net_impulse = self.metrics.get("Net Impulse")

        outcome = "CONSERVATIVE (No Thrust)"
        if isinstance(net_impulse, (int, float)) and abs(float(net_impulse)) > 1e-4:
            outcome = "NON-CONSERVATIVE (THRUST DETECTED)"
            status = "ANOMALY DETECTED"

        error = None
        if exc_type is not None:
            error = str(exc_val)

        # If the experiment already saved a plot with a different name, it can override this via metrics.
        plot_filename = self.metrics.get("Plot Filename", "visual_telemetry.png")
        self.write_report(
            status=status,
            outcome=outcome,
            net_impulse=float(net_impulse) if isinstance(net_impulse, (int, float)) else None,
            plot_filename=str(plot_filename),
            error=error,
        )

        # Do not suppress exceptions.
        return False
