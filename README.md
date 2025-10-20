# Installation

```python
pip install tmesh
```

# CLI Tree

## 1. `tmesh-cli benchmark --endpoint "<YOUR_OPEN_AI_API_ENDPOINT>" --api-key "<OPTIONAL_API_KEY>"`

Example: 

`tmesh-cli benchmark --endpoint "http://89.169.111.29:30080/" --api-key "vllm_sk_555a1b7ff3e0f617b1240375ea411c2a5f08d2666fcdc718075f66c9"`

The model at the endpoint will automatically be discovered and the benchmark will run ad infinitum. 

### Discovery and Configuration: 

```text
endpoint: http://localhost:8000/v1/
found model: Qwen/Qwen3-30B-A3B-Instruct-2507
offload_size: 100
Workload Specifications:
Model: Qwen/Qwen3-30B-A3B-Instruct-2507
Number of Contexts: 30
Number of Questions per Context: 30
Max Inflight Requests (Load-Balancing): 10
Input Length: 32000
Output Length: 100
```

Continually send M long contexts that will always have N randomly generated questions appended to them.

Hardcoded Configurations:

- 32k token context length
- 100 token output length
- TensorMesh SaaS configurations in: `src/benchmark/model_configs.json`

Discovered Configurations:

- Model name (must be one of the ones supported by LMIgnite inside of model_configs.json)
- Number of contexts
- Number of questions per context
- Maximum Inflight Requests

### Refreshing Logs every 5 seconds

```text
Elapsed Time: 165.0652596950531
Total Number of Requests Processed: 280
QPS: 1.696298788232491
Global Average TTFT: 3.77425986954144
Global Average ITL: 0.01485872107813842
Global Average Prefill Throughput: 22871.74402415523
Global Average Decode Throughput: 104.11856198232987
Requests Processed in Interval: 0
Interval Average TTFT: 2.5995567440986633
Interval Average ITL: 0.012132209007956864
Interval Average Prefill Throughput: 25740.820827727515
Interval Average Decode Throughput: 90.82104365217528
```

## 2. 