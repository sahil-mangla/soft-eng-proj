from simulation.cli import run_and_report
from simulation.engine import RunMode
from simulation.scenario import Scenario


def test_cli_report_uses_the_shared_metrics(capsys):
    run_and_report(Scenario(background_vehicles=10), RunMode.CORRIDOR_RECOVERY)
    out = capsys.readouterr().out
    assert "Mode: corridor_recovery" in out and "Ambulance transit time:" in out and "over 10 vehicles" in out
