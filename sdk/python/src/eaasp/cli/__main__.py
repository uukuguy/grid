"""CLI entry point — eaasp init / validate / test / submit / ecosystem."""

from __future__ import annotations

import click

from eaasp.cli.ecosystem_cmd import ecosystem_cmd
from eaasp.cli.init_cmd import init_cmd
from eaasp.cli.run_cmd import run_cmd
from eaasp.cli.submit_cmd import submit_cmd
from eaasp.cli.test_cmd import test_cmd
from eaasp.cli.validate_cmd import validate_cmd


@click.group()
@click.version_option(version="0.1.0", prog_name="eaasp")
def main() -> None:
    """EAASP Enterprise SDK — create, validate, and test Skills."""


main.add_command(init_cmd, "init")
main.add_command(validate_cmd, "validate")
main.add_command(test_cmd, "test")
main.add_command(run_cmd, "run")
main.add_command(submit_cmd, "submit")
main.add_command(ecosystem_cmd, "ecosystem")

if __name__ == "__main__":
    main()
