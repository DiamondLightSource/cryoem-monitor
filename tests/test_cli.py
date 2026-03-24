import subprocess


def test_cli_exists():
    cmd = ["cryoem_monitor.run", "--help"]
    run_out = subprocess.check_output(cmd).decode()
    assert run_out.split("\n")[0] == "usage: cryoem_monitor.run [-h] --server HOST:PORT"
