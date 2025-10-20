#!/usr/bin/env python3

import argparse
import json
from os import environ, path, makedirs
import re
import shutil
import sys
import tarfile
from typing import Any, Generator, List, NamedTuple, Sequence, TypedDict
import zipfile


class KnownError(Exception):
    pass


def get_ollama_models_dir() -> str:
    """Return the path to the OLLAMA_MODELS directory based on the OS."""
    # Check if OLLAMA_MODELS environment variable is set
    ollama_models = environ.get('OLLAMA_MODELS')
    if ollama_models:
        return ollama_models

    # If not set, use default paths based on OS
    if sys.platform in ("win32", "darwin"):
        return path.join(path.expanduser('~'), '.ollama', 'models')
    else:
        return '/usr/share/ollama/.ollama/models'


class ManifestLayer(TypedDict):
    mediaType: str
    digest: str
    size: int


class Manifest(TypedDict):
    schemaVersion: int
    mediaType: str
    config: ManifestLayer
    layers: Sequence[ManifestLayer]


def read_ollama_manifest(manifest_path: str) -> Manifest:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


class ManifestData(NamedTuple):
    root: str
    files: Sequence[str]
    size: int


def get_ollama_manifest_data(manifest: str):
    manifest_absolute_path = path.abspath(manifest)
    root = path.dirname(path.dirname(path.dirname(path.dirname(path.dirname(manifest_absolute_path)))))
    manifest_data = read_ollama_manifest(manifest_absolute_path)

    digests: List[str] = [
        manifest_data["config"]["digest"],
        *[layer["digest"] for layer in manifest_data["layers"]]
    ]

    files = [
        path.relpath(manifest_absolute_path, root),
        *[path.join('blobs', digest.replace(':', '-')) for digest in digests]
    ]

    size = sum(layer["size"] for layer in manifest_data["layers"]) + manifest_data["config"]["size"]

    for f in files:
        abs_path = path.join(root, f)
        if not path.isfile(abs_path):
            raise KnownError(f"File not found: {abs_path}")

    return ManifestData(root=root, files=files, size=size)


def get_ollama_manifests_data(manifests: List[str]) -> List[ManifestData]:
    return [get_ollama_manifest_data(manifest) for manifest in manifests]


def check_single_ollama_root(manifests_data: List[ManifestData]):
    if len({manifest.root for manifest in manifests_data}) != 1:
        raise KnownError("All manifests must be in the same OLLAMA_MODELS directory.")


def list_command(manifests: List[str]):
    manifests_data = get_ollama_manifests_data(manifests)

    check_single_ollama_root(manifests_data)

    for manifest_data in manifests_data:
        for file in manifest_data.files:
            print(file)


def copy_command(manifests: List[str], destination: str):
    manifests_data = get_ollama_manifests_data(manifests)

    for manifest_data in manifests_data:
        for file in manifest_data.files:
            source_path = path.join(manifest_data.root, file)
            destination_path = path.join(destination, file)

            destination_dir = path.dirname(destination_path)
            makedirs(destination_dir, exist_ok=True)
            shutil.copy2(source_path, destination_path, follow_symlinks=True)


def tar_command(manifests: List[str], archive_path: str):
    manifests_data = get_ollama_manifests_data(manifests)

    archive_name = None if archive_path == "-" else archive_path
    fileobj = sys.stdout.buffer if archive_path == "-" else None
    with tarfile.open(archive_name, "w", fileobj=fileobj) as archive:
        # TODO identify duplicated files.
        for data in manifests_data:
            for file in data.files:
                archive.add(path.join(data.root, file), file)


def zip_command(manifests: List[str], archive_path: str):
    manifests_data = get_ollama_manifests_data(manifests)

    io = sys.stdout.buffer if archive_path == "-" else archive_path
    with zipfile.ZipFile(io, "w", compression=zipfile.ZIP_STORED) as archive:
        # TODO identify duplicated files.
        for data in manifests_data:
            for file in data.files:
                archive.write(path.join(data.root, file), file)


def resolve_manifests(values: List[str], models_dir: str) -> list[str]:
    """
    Resolve a list of manifest paths or model names to actual manifest file paths.
    """

    def gen() -> Generator[str, Any, None]:
        model_pattern = re.compile(r'^(?P<name>[a-zA-Z0-9][a-zA-Z0-9._-]*):(?P<tag>[a-zA-Z0-9][a-zA-Z0-9._-]*)$')

        for model_or_manifest in values:
            match = model_pattern.match(model_or_manifest)
            if match:
                manifest = path.join(
                    models_dir,
                    'manifests', 'registry.ollama.ai', 'library',
                    match["name"], match["tag"]
                )
                if path.isfile(manifest):
                    yield manifest
                else:
                    raise KnownError(f"{model_or_manifest} manifest's not found: {manifest}")
            else:
                if path.isfile(model_or_manifest):
                    yield model_or_manifest
                else:
                    raise KnownError(f"File not found: {model_or_manifest}")

    return list(gen())


if __name__ == '__main__':
    def main() -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--version", action='version', version="1.1.0")

        subparsers = parser.add_subparsers(dest="command")

        parent_parser = argparse.ArgumentParser(add_help=False)
        parent_parser.add_argument(
            "--models-dir", metavar="DIRECTORY",
            help=f"""
            Directory where Ollama stores its models.
            Not required using manifest.
            (default: {get_ollama_models_dir()})
            """,
            default=get_ollama_models_dir()
        )
        parent_parser.add_argument(
            "model", nargs='+',
            help="Name of a model or path to its manifest."
        )

        subparsers.add_parser("list", parents=[parent_parser])

        parser_copy = subparsers.add_parser("copy", parents=[parent_parser])
        parser_copy.add_argument(
            "--to", metavar="DIRECTORY", required=True,
            help="Directory where the files will be copied. Will be created if it does not exists."
        )

        parser_tar = subparsers.add_parser('tar', parents=[parent_parser])
        parser_tar.add_argument(
            "--archive",
            help="""
            Archive to store the models in.
            Use '-' to send the archive to the standard output.
            """
        )

        parser_zip = subparsers.add_parser('zip', parents=[parent_parser])
        parser_zip.add_argument(
            "--archive",
            help="""
            Archive to store the models in.
            Use '-' to send the archive to the standard output.
            """
        )

        try:
            args = parser.parse_args()

            manifests = resolve_manifests(args.model, args.models_dir)

            if args.command == "list":
                list_command(manifests)
            elif args.command == "copy":
                copy_command(manifests, args.to)
            elif args.command == "tar":
                tar_command(manifests, args.archive)
            elif args.command == "zip":
                zip_command(manifests, args.archive)
        except KnownError as e:
            sys.exit(str(e))

    main()
