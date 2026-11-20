"""Copia consistente de SQLite, utilizable para respaldar o recuperar a un archivo nuevo."""
from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile


def copy_database(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.absolute()
    with NamedTemporaryFile(prefix=".openmarket-", dir=destination.parent, delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        with (
            closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=15)) as original,
            closing(sqlite3.connect(staged)) as copy,
        ):
            original.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("La copia no supera la comprobación de integridad")
            if copy.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise sqlite3.DatabaseError("La copia contiene relaciones inválidas")
            version = copy.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if version is None:
                raise sqlite3.DatabaseError("La copia no contiene un esquema de OpenMarket")
        os.link(staged, destination)
    finally:
        staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origen", type=Path)
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    try:
        copy_database(args.origen, args.destino)
    except (OSError, sqlite3.Error) as exc:
        parser.exit(1, f"No se pudo completar la copia ({type(exc).__name__}).\n")
    print("Copia SQLite verificada.")


if __name__ == "__main__":
    main()
