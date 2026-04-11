"""This module provides the logme CLI."""

from os import makedirs
from pathlib import Path
from typing import List, Optional
import typer
from logme import ERRORS, __app_name__, __version__, config, sourcesList
from logme.logme import source_trigger
from logme.storage.database import DEFAULT_DB_FILE_PATH
import logme.utils.Utils as u

app = typer.Typer()

@app.command()
def init(
    db_path: str = typer.Option(
        str(DEFAULT_DB_FILE_PATH),
        "--db-path",
        "-db",
        prompt="logme database location?",
    ),
) -> None:
    """Initialize the logme database."""
    app_init_error = config.init_app(db_path)
    if app_init_error:
        typer.secho(
            f"Creating config file failed with " f'"{ERRORS[app_init_error]}"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    dst = u.get_local_storage_path(config.CONFIG_FILE_PATH)
    db_init_error = logme.storage.database.DatabaseHandler.init_database(Path(db_path))
    if db_init_error:
        typer.secho(
            f"Creating database failed with " f'"{ERRORS[db_init_error]}"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    else:
        typer.secho(f"The logme database is " f"{db_path}", fg=typer.colors.GREEN)


@app.command(name="source")
def process_src(
    src: str = typer.Argument(
        default="", help=f"Chose one of the implemented sources:\n" f"{sourcesList}"), 
        amount: int = typer.Option(6, "--amount", "-a", help="How many items to process.")
        ) -> int:
    """Process a source."""

    if not config.CONFIG_FILE_PATH.exists():
        typer.secho(
            "Config file not found.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if not src in sourcesList:
        typer.secho(
            f'There is not a source "{src}".\n'
            f"Chose one of the implemented sources:\n"
            f"{sourcesList}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    dst = u.get_local_storage_path(config.CONFIG_FILE_PATH)
    if not dst.exists():
        print(f"Creates directory: {dst}")
        makedirs(dst)
    print(f"dst: {dst}")
    source_trigger(src, amount)
    return 0


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return
