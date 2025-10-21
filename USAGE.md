# tmesh CLI User Documentation

## Overview

`tmesh-cli` is a benchmarking tool for LLM inference endpoints. It measures performance metrics for OpenAI-compatible API endpoints, with a focus on testing KV cache offloading capabilities in TensorMesh deployments.

## Installation

### Prerequisites

tmesh requires Python 3.9 or higher.

#### Check if Python is Installed

```bash
python3 --version
```

If you see output like `Python 3.9.x` or higher, you're ready to proceed. If not, see the installation instructions below.

#### Installing Python 3

**macOS:**
```bash
# Using Homebrew (recommended)
brew install python3

# Or download from python.org
# Visit: https://www.python.org/downloads/macos/
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

**Linux (Fedora/RHEL/CentOS):**
```bash
sudo dnf install python3 python3-pip
```

**Windows:**
```bash
# Download from python.org
# Visit: https://www.python.org/downloads/windows/
# Make sure to check "Add Python to PATH" during installation
```

Alternatively, use [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):
```bash
winget install Python.Python.3.12
```

#### Verify pip is Installed

pip usually comes with Python 3.4+. Check if it's available:

```bash
pip --version
# or
pip3 --version
```

If pip is not found, install it:

**macOS/Linux:**
```bash
python3 -m ensurepip --upgrade
```

**Windows:**
```bash
python -m ensurepip --upgrade
```

### Installing tmesh

Once Python 3 and pip are installed:

```bash
pip install tmesh
```

Or if you need to use `pip3` explicitly:

```bash
pip3 install tmesh
```

#### Using Virtual Environments (Recommended)

To avoid conflicts with other Python packages, use a virtual environment:

```bash
# Create a virtual environment
python3 -m venv tmesh-env

# Activate it
# On macOS/Linux:
source tmesh-env/bin/activate
# On Windows:
tmesh-env\Scripts\activate

# Install tmesh
pip install tmesh

# When done, deactivate
deactivate
```

#### Install from Source

For the latest development version:

```bash
git clone https://github.com/your-org/tmesh.git
cd tmesh
pip install -e .
```

### Verify Installation

After installation, verify tmesh is available:

```bash
tmesh-cli --help
```

You should see the help menu with available commands.

## Quick Start

Run a benchmark against your LLM endpoint:

```bash
tmesh-cli benchmark --endpoint "http://localhost:8000" --api-key "your-api-key"
```

The benchmark will run continuously until interrupted (Ctrl+C).

## Command Reference

### `tmesh-cli benchmark`

Runs an infinite benchmarking workload against an OpenAI-compatible LLM endpoint.

#### Required Arguments

- `--endpoint <URL>` - The OpenAI-compatible API endpoint URL
- `--api-key <KEY>` - API key for authentication

#### Endpoint URL Formats

The tool accepts various URL formats and normalizes them to `/v1/`:

```bash
# All of these are valid and equivalent:
tmesh-cli benchmark --endpoint "http://localhost:8000" --api-key "sk-123"
tmesh-cli benchmark --endpoint "http://localhost:8000/" --api-key "sk-123"
tmesh-cli benchmark --endpoint "http://localhost:8000/v1" --api-key "sk-123"
tmesh-cli benchmark --endpoint "http://localhost:8000/v1/" --api-key "sk-123"
tmesh-cli benchmark --endpoint "localhost:8000" --api-key "sk-123"
```

**Note**: HTTPS URLs are automatically converted to HTTP.

#### Example

```bash
tmesh-cli benchmark \
  --endpoint "http://89.169.111.29:30080/" \
  --api-key "vllm_sk_555a1b7ff3e0f617b1240375ea411c2a5f08d2666fcdc718075f66c9"
```

## How It Works

### 1. Model Discovery

The tool automatically discovers the model name from your endpoint:

```
endpoint: http://localhost:8000/v1/
found model: Qwen/Qwen3-30B-A3B-Instruct-2507
```

### 2. Workload Calculation

Based on the discovered model (matched against `model_configs.json`), the tool calculates optimal workload parameters:

```
offload_size: 100
Workload Specifications:
Model: Qwen/Qwen3-30B-A3B-Instruct-2507
Number of Contexts: 30
Number of Questions per Context: 30
Max Inflight Requests (Load-Balancing): 10
Input Length: 32000
Output Length: 100
```

The workload is designed to stress-test the KV cache offloading buffer by:
- Creating multiple long contexts (32k tokens each)
- Reusing contexts with different questions
- Managing concurrent requests with load balancing

### 3. Continuous Benchmarking

The tool sends requests continuously using a tiling pattern:
- Cycles through all contexts sequentially
- Appends random questions to each context
- Maintains max inflight requests for load balancing
- Maximizes cache evictions to test offloading

### 4. Real-time Metrics

Every 5 seconds, the tool displays performance metrics:

```
Elapsed Time: 165.07
Total Number of Requests Processed: 280
QPS: 1.70
Global Average TTFT: 3.77
Global Average ITL: 0.015
Global Average Prefill Throughput: 22871.74
Global Average Decode Throughput: 104.12
Requests Processed in Last 5 second Interval: 56
Interval Average TTFT: 2.60
Interval Average ITL: 0.012
Interval Average Prefill Throughput: 25740.82
Interval Average Decode Throughput: 90.82
```

## Metrics Explained

### Global Metrics (Cumulative)

- **Elapsed Time**: Total time since benchmark started (seconds)
- **Total Number of Requests Processed**: All completed requests
- **QPS (Queries Per Second)**: Average throughput over entire run
- **Global Average TTFT**: Average time to first token (seconds)
- **Global Average ITL**: Average inter-token latency (seconds per token)
- **Global Average Prefill Throughput**: Average input tokens processed per second
- **Global Average Decode Throughput**: Average output tokens generated per second

### Interval Metrics (Last 5 Seconds)

- **Requests Processed in Last 5 second Interval**: Requests completed in the last interval
- **Interval Average TTFT**: TTFT for recent requests only
- **Interval Average ITL**: ITL for recent requests only
- **Interval Average Prefill Throughput**: Recent prefill performance
- **Interval Average Decode Throughput**: Recent decode performance

Global metrics provide overall performance, while interval metrics show current behavior and help detect performance changes over time.

## Workload Configuration

### Hardcoded Parameters

- **Input Length**: 32,000 tokens per context
- **Output Length**: 100 tokens per completion

### Auto-calculated Parameters

Based on model specifications in `model_configs.json`:

- **Number of Contexts**: Calculated from offload buffer size
- **Number of Questions per Context**: Equal to number of contexts
- **Max Inflight Requests**: 1/3 of number of contexts

Formula for number of contexts:
```
num_contexts = (0.9 × offload_size) / (bytes_per_token × input_length / 1024³)
```

## Supported Models

The tool supports these pre-configured models:

1. **openai/gpt-oss-120b** (36 layers, 73,728 bytes/token)
2. **openai/gpt-oss-20b** (24 layers, 49,152 bytes/token)
3. **Qwen/Qwen3-235B-A22B-Instruct-2507-FP8** (94 layers, TP=8, 96,256 bytes/token)
4. **Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8** (62 layers, TP=8, 253,952 bytes/token)
5. **Qwen/Qwen3-30B-A3B-Instruct-2507** (48 layers, TP=1, 98,304 bytes/token)

To add support for additional models, edit `model_configs.json` with the model's specifications.

## Troubleshooting

### Connection Errors

If you see:
```
[ERROR] Could not connect to endpoint: http://localhost:8000/v1/
Make sure a model server is running and accessible.
Try: curl http://localhost:8000/v1/models
```

**Solutions**:
- Verify the endpoint URL is correct
- Check that the model server is running
- Test connectivity with: `curl <endpoint>/v1/models`
- Ensure firewall/network allows connections

### Model Not Found

If you see:
```
[ERROR] model <model_name> not found in model_configs.json
```

**Solutions**:
- Check if your model is supported (see Supported Models section)
- Add your model's configuration to `model_configs.json`
- Ensure the model name returned by `/v1/models` matches exactly

### Stopping the Benchmark

The benchmark runs indefinitely. To stop:
- Press **Ctrl+C** (or send SIGINT/SIGTERM)
- The tool will gracefully shutdown and display final metrics

## Advanced Usage

### Testing Different Endpoints

Compare performance across different deployments:

```bash
# Test local deployment
tmesh-cli benchmark --endpoint "http://localhost:8000" --api-key "test"

# Test remote deployment
tmesh-cli benchmark --endpoint "http://production.example.com" --api-key "prod-key"
```

### Long-running Tests

For extended testing, run in the background and redirect output:

```bash
nohup tmesh-cli benchmark \
  --endpoint "http://localhost:8000" \
  --api-key "sk-123" \
  > benchmark.log 2>&1 &
```

Monitor with:
```bash
tail -f benchmark.log
```

### Analyzing Results

The metrics help identify:
- **Throughput bottlenecks**: Low QPS or decode throughput
- **Latency issues**: High TTFT or ITL
- **Cache performance**: Changes in interval metrics when contexts rotate
- **Resource constraints**: Degrading metrics over time

## API Compatibility

The tool uses the OpenAI Python SDK and expects these endpoints:

- **GET /v1/models** - List available models
- **POST /v1/completions** - Streaming completions API

Your endpoint must support:
- Streaming responses (`stream=True`)
- `max_tokens` parameter
- Standard OpenAI response format

## Best Practices

1. **Warm-up period**: Ignore first 30-60 seconds of metrics (cold start effects)
2. **Steady state**: Look at metrics after several full context rotations
3. **Compare intervals**: Watch for performance degradation over time
4. **Resource monitoring**: Monitor CPU, memory, GPU usage alongside tmesh metrics
5. **Network stability**: Run from stable network connection for accurate latency measurements

## Support

For issues, questions, or contributions, visit the project repository.
