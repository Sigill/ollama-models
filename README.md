# ollama-models

A Python script to help copying models from one Ollama instance to another.

## Overview

For various reasons (a slow internet connection, an air-gaped machine, a corporate firewall...), you might not be able to `ollama pull` a model on a machine.

You can however do it in another machine, and would like to copy the model from this machine to the first one.

This script will help you identify and export the files composing an Ollama model.

## Requirements & installation

This script requires Python 3.8 or higher.

Just download `ollama-models.py` script somewhere and execute it.

No additional dependencies are required beyond the standard library.

## Usage

An Ollama model is just a handful of files stored somewhere on your disk. Refer to the [Ollama documentation](https://github.com/ollama/ollama/blob/main/docs/faq.md#where-are-models-stored) to find where.

Copying a model from one machine to another appears to be as simple as copying the files, but Ollama does not provide any mean to identify them.

> This script does not rely on any public Ollama API, it directly interacts with Ollama's internal storage. If Ollama's implementation changes, this script is likely to stop working or break you Ollama installation. Use it at your own risks.

This script essentially reads a model's manifest to identify those files.

Note: A manifest is just a JSON file. A model named `name:tag` has it's manifest located at `<OLLAMA_MODELS>/models/manifests/registry.ollama.ai/library/name/tag`.\
The commands below allows models to be specified using either their `name:tag` or their manifest.

### list command

The `list` commands will list the path of the files composing the model relative to the `OLLAMA_MODELS` directory.

```sh
$ ./ollama-models.py list qwen3:0.6b
manifests/registry.ollama.ai/library/qwen3/0.6b
blobs/sha256-b0830f4ff6a0220cfd995455206353b0ed23c0aee865218b154b7a75087b4e55
blobs/sha256-7f4030143c1c477224c5434f8272c662a8b042079a0a584f0a27a1684fe2e1fa
blobs/sha256-ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4
blobs/sha256-d18a5cc71b84bc4af394a31116bd3932b42241de70c77d2b76d69a314ec8aa12
blobs/sha256-cff3f395ef3756ab63e58b0ad1b32bb6f802905cae1472e6a12034e4246fbbdb
```

### copy command

Copy the files associated with some models to a directory.

```sh
./ollama-models.py copy mistral:latest /media/usb-key
```

Then, on the destination machine, you just have to copy the files to the `OLLAMA_MODELS` directory:

```sh
cp -r /tmp/usb-key/* $OLLAMA_MODELS
```

### tar command

The `tar` command allows to store the model in a tar archive:

```sh
# On machine A:
ollama-models.py tar mistral:latest --archive /tmp/mistral.tar

# Send it to machine B somehow...

# On machine B:
tar -xf /tmp/mistral.tar -C /usr/share/ollama/.ollama/models
```

### zip command

The `zip` command allows to store the model in a zip archive:

```sh
# On machine A:
ollama-models.py zip mistral:latest --archive /tmp/mistral.zip

# Send it to machine B somehow...

# On machine B:
unzip /tmp/mistral.zip -d /usr/share/ollama/.ollama/models
```

Note: The generated zip file is uncompressed, it is just used as a container.\
Models appears to compress poorly (only 5% file size reduction was observed), and while some compression algorithms have little to no impact on the compression time, the implementation is currently kept simple and does not use compression.

## Advanced usage

### Streaming data using rsync

Because Ollama models can be quite heavy, you might want to avoid creating intermediate copies or archives and directly send the models over the network.

The most efficient way is probably to rely on [rsync](https://rsync.samba.org/) to transport the files.

The `list` command can be used to instruct rsync which files to send from machine A to machine B.

```sh
# On machine A:
./ollama-models.py list qwen3:0.6b > /tmp/files.txt
```

```sh
# On machine A, to push to machine B:
rsync -avh --progress --files-from=/tmp/files.txt \
  /usr/share/ollama/.ollama/models \
  user@B:/usr/share/ollama/.ollama/models

# Or, on machine B, to pull from machine A:
rsync -avh --progress --files-from=:/tmp/files.txt \
  user@A:/usr/share/ollama/.ollama/models \
  /usr/share/ollama/.ollama/models
```

Note: Make sure to adjust the paths to wherever Ollama stores the models on both machines.

### Streaming data using scp

If `rsync` is unavailable, the files can be sent using scp with the `tar` or `zip` commands:

```sh
# On machine A, to push to machine B:
./ollama-models.py tar mistral:latest --archive - | ssh user@B tar -x -C /usr/share/ollama/.ollama/models

# Or, on machine B, to pull from machine A:
ssh user@B /somewhere/ollama-models.py tar mistral:latest --archive - | tar -x -C /usr/share/ollama/.ollama/models
```

## License

This project is licensed under the MIT License.
