# LocalLM abliterated

This repository provides a self-hosted solution for running an unrestricted llm with web search engine.
All of that is bundled inside Open WebUI

## Models

We provide two models for you to choose from:
- `jialinyyzz/Qwen3.8-27B-abliterated-MLX-4bit`: A 27B parameter model with 4-bit quantization, designed for general-purpose reasoning and coding tasks.
- `qwen3-4b-instruct-2507-4bit`: A 4B parameter model with 4-bit quantization, optimized for instruction-following tasks.

## System Prompt

There is a file named `system_prompt.txt` in the root directory.
You will have to manually set the system prompt for the model you are using.

## Usage

Run the following command in 2 distinct terminal to start the 2 llm:

```sh
rapid-mlx serve jialinyyzz/Qwen3.8-27B-abliterated-MLX-4bit \
  --host 0.0.0.0 \
  --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder_xml \
  --reasoning-parser qwen3 \
  --prefill-step-size 8192 \
  --hybrid-cache-entries 2
```

```sh
rapid-mlx serve qwen3-4b-instruct-2507-4bit \
  --host 0.0.0.0 \
  --port 8001 \
  --prefill-step-size 8192
```

Then, you can run the following command to start the rest of the services:

```sh
docker compose up -d
```
