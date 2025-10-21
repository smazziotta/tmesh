import sys
from dataclasses import dataclass
from openai import OpenAI, AsyncOpenAI, APIConnectionError
import asyncio
import importlib.resources
import json
import random
import time
from urllib.parse import urlparse, urlunparse

@dataclass
class RequestStats: 
    start_time: float
    first_token_time: float
    end_time: float
    input_length: int
    output_length: int

@dataclass
class PrefillPairs: 
    input_length: int
    prefill_time: float

@dataclass
class DecodePairs: 
    output_length: int
    decode_time: float

class ObservabilityPanel: 
    def __init__(self, workload_config: "WorkloadConfig"): 
        print(
            f"Workload Specifications:\n"
            f"Model: {workload_config.model_name}\n"
            f"Number of Contexts: {workload_config.num_contexts}\n"
            f"Number of Questions per Context: {workload_config.questions_per_context}\n"
            f"Max Inflight Requests (Load-Balancing): {workload_config.max_inflight_requests}\n"
            f"Input Length: {workload_config.input_length}\n"
            f"Output Length: {workload_config.output_length}\n"
        )
        self.num_requests = 0
        # cleared after every non-empty interval
        self.interval_requests = 0
        self.interval_prefill_stats: list[PrefillPairs] = []
        self.interval_decode_stats: list[DecodePairs] = []

        self.running_ttft = 0
        self.running_itl = 0
        self.running_prefill_throughput = 0
        self.running_decode_throughput = 0
        self.start_time = time.time()

        # every 5 seconds, we will update the current values
        self.log_update_interval = 5
    
    async def start(self): 
        asyncio.create_task(self.stat_logger())

    def on_request_finished(self, request_stats: RequestStats):
        self.interval_requests += 1
        self.interval_prefill_stats.append(PrefillPairs(request_stats.input_length, request_stats.first_token_time - request_stats.start_time))
        self.interval_decode_stats.append(DecodePairs(request_stats.output_length, request_stats.end_time - request_stats.first_token_time))
    
    # an async daemon
    async def stat_logger(self): 
        while True: 
            now = time.time()
            elapsed_time = now - self.start_time
            total_requests = self.num_requests + self.interval_requests
            # avoid division by zero if we didn't finish any requests in this interval
            if not self.interval_prefill_stats or not self.interval_decode_stats:
                await asyncio.sleep(self.log_update_interval)
                continue
            interval_ttft = sum(prefill_pair.prefill_time for prefill_pair in self.interval_prefill_stats) / len(self.interval_prefill_stats)
            # + 1 for EOS token
            interval_itl = sum(decode_pair.decode_time / (decode_pair.output_length + 1) for decode_pair in self.interval_decode_stats) / len(self.interval_decode_stats)
            interval_prefill_throughput = sum(prefill_pair.input_length / prefill_pair.prefill_time for prefill_pair in self.interval_prefill_stats) / len(self.interval_prefill_stats)
            interval_decode_throughput = sum(decode_pair.output_length / decode_pair.decode_time for decode_pair in self.interval_decode_stats) / len(self.interval_decode_stats)
            old_weight, new_weight = self.num_requests / total_requests, self.interval_requests / total_requests
            self.running_ttft = old_weight * self.running_ttft + new_weight * interval_ttft
            self.running_itl = old_weight * self.running_itl + new_weight * interval_itl
            self.running_prefill_throughput = old_weight * self.running_prefill_throughput + new_weight * interval_prefill_throughput
            self.running_decode_throughput = old_weight * self.running_decode_throughput + new_weight * interval_decode_throughput

            self.num_requests = total_requests
            qps = self.num_requests / elapsed_time
            self.interval_prefill_stats = []
            self.interval_decode_stats = []
            print(
                f"Elapsed Time: {elapsed_time}\n"
                f"Total Number of Requests Processed: {self.num_requests}\n"
                f"QPS: {qps}\n"
                f"Global Average TTFT: {self.running_ttft}\n"
                f"Global Average ITL: {self.running_itl}\n"
                f"Global Average Prefill Throughput: {self.running_prefill_throughput}\n"
                f"Global Average Decode Throughput: {self.running_decode_throughput}\n"
                f"Requests Processed in Last {self.log_update_interval} second Interval: {self.interval_requests}\n"
                f"Interval Average TTFT: {interval_ttft}\n"
                f"Interval Average ITL: {interval_itl}\n"
                f"Interval Average Prefill Throughput: {interval_prefill_throughput}\n"
                f"Interval Average Decode Throughput: {interval_decode_throughput}\n"
            )
            self.interval_requests = 0
            await asyncio.sleep(self.log_update_interval)
            


@dataclass
class WorkloadConfig: 
    num_contexts: int
    questions_per_context: int
    model_name: str
    max_inflight_requests: int
    # hardcoded for now
    input_length: int = 32000
    output_length: int = 100

    @staticmethod
    def _find_model(endpoint: str, api_key: str) -> str:
        client = OpenAI(base_url=endpoint, api_key=api_key)
        try:
            models = client.models.list()
            model = models.data[0].id
            print(f"found model: {model}")
            return model
        except APIConnectionError:
            print(
                f"\n[ERROR] Could not connect to endpoint: {endpoint}\n"
                f"Make sure a model server is running and accessible.\n"
                f"Try: curl {endpoint}/models\n"
            )
            sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] Failed to query models from {endpoint}: {e}\n")
            sys.exit(1)

    @staticmethod
    def calculate_workload(model_config: dict) -> "WorkloadConfig": 
        tp = int(model_config["tensorParallelSize"])
        cpu_size = int(model_config["cpuOffloadingBufferSize"])
        disk_size = int(model_config["diskOffloadingBufferSize"])
        remote_size = int(model_config["remoteOffloadingBufferSize"])
        bytes_per_tok = int(model_config["bytes_per_tok"])
        offload_size = max(cpu_size * tp, disk_size * tp, remote_size)
        print(f"offload_size: {offload_size}")
        # 90% of the buffer we have (accounting for fragmentation etc.)
        conservative_ratio = 0.9
        num_contexts = int((conservative_ratio * offload_size) // (bytes_per_tok * WorkloadConfig.input_length / 1024 ** 3))
        questions_per_context = num_contexts
        # have 1/3 of the contexts be inflight at any time
        max_inflight_requests = num_contexts // 3
        return WorkloadConfig(
            num_contexts=num_contexts,
            questions_per_context=questions_per_context,
            model_name=model_config["model_name"],
            max_inflight_requests=max_inflight_requests,
            input_length=WorkloadConfig.input_length,
            output_length=WorkloadConfig.output_length)

    @staticmethod
    def from_endpoint(endpoint: str, api_key: str) -> "WorkloadConfig": 
        # assumptions: 
        # all of the hardcoded specs are inside of model_configs.json
        # this will automatically match a model name to: 
        # TP, bytes_per_tok, cpu size, disk size, remote size
        # we will create a workload that maximally stresses a buffer of size
        # max(cpu size * TP, disk size * TP, remote size)
        model = WorkloadConfig._find_model(endpoint, api_key)
        with importlib.resources.files("tensormesh.cli.benchmark").joinpath("model_configs.json").open("r") as f:
            model_configs = json.load(f)
            for model_config in model_configs:
                if model_config["model_name"] == model:
                    return WorkloadConfig.calculate_workload(model_config)
            raise ValueError(f"model {model} not found in model_configs.json")

class WorkloadGenerator: 
    @staticmethod
    def generate_context_pool(num_contexts: int, context_length: int) -> list[str]: 
        return [f"{i}" + "hi" * context_length for i in range(num_contexts)]
    
    @staticmethod
    def generate_question_pool(num_questions: int) -> list[str]: 
        return [f"{i}" + "tell me a long story" for i in range(num_questions)]
    
    @staticmethod
    def has_content(chunk): 
        return bool(chunk.choices) and (chunk.choices[0].text is not None)
    
    @staticmethod
    def extract_content(chunk): 
        return chunk.choices[0].text or ""

    def __init__(self, workload_config: "WorkloadConfig", endpoint: str, api_key: str): 
        self.observability_panel = ObservabilityPanel(workload_config)
        self.workload_config = workload_config
        self.client = AsyncOpenAI(
            base_url=endpoint, 
            api_key=api_key
        )
        self.context_pool = WorkloadGenerator.generate_context_pool(self.workload_config.num_contexts, self.workload_config.input_length)
        # we do a tiling pattern for context pool to maximize evictions between context reuse
        self.context_counter = 0
        self.question_pool = WorkloadGenerator.generate_question_pool(self.workload_config.questions_per_context)

        self.sem = asyncio.Semaphore(self.workload_config.max_inflight_requests)

    async def process_single_prompt(self, prompt: str): 
        start_time = time.time()
        first_token_time = None

        response = await self.client.completions.create(
            model=self.workload_config.model_name,
            prompt=prompt,
            stream=True,
            max_tokens=self.workload_config.output_length,
        )
        pieces = []
        async for chunk in response: 
            if not WorkloadGenerator.has_content(chunk): 
                continue
            content = WorkloadGenerator.extract_content(chunk)
            if first_token_time is None: 
                first_token_time = time.time()
            pieces.append(content)
        
        end_time = time.time()
        final_response = "".join(pieces)
        stat = RequestStats(
            start_time=start_time,
            first_token_time=first_token_time,
            end_time=end_time,
            input_length=len(prompt),
            output_length=len(final_response),
        )
        self.observability_panel.on_request_finished(stat)


    async def infinitely_benchmark(self): 
        await self.observability_panel.start()
        while True: 
            await self.sem.acquire()
            context = self.context_pool[self.context_counter]
            self.context_counter = (self.context_counter + 1) % self.workload_config.num_contexts
            question = random.choice(self.question_pool)
            future = asyncio.create_task(self.process_single_prompt(context + question))
            future.add_done_callback(lambda _: self.sem.release())

def url_reduce(endpoint: str) -> str: 
    # we want to accept any open ai endpoint
    # example 1: http://localhost:8000
    # example 1.1: http://localhost:8000/
    # example 2: http://localhost:8000/v1
    # example 2.1: http://localhost:8000/v1/
    # example 3: http://localhost:8000/v1/completions
    # example 3.1: http://localhost:8000/v1/completions/
    # example 4: http://localhost:8000/v1/chat/completions
    # example 4.1: http://localhost:8000/v1/chat/completions/
    # Ensure scheme
    if endpoint.startswith("https://"):
        endpoint = endpoint.replace("https://", "http://")
    if not endpoint.startswith(("http://")):
        endpoint = "http://" + endpoint

    parsed = urlparse(endpoint)
    scheme = parsed.scheme
    netloc = parsed.netloc or parsed.path  # handles bare host:port inputs
    # Ensure /v1/ suffix
    normalized = urlunparse((scheme, netloc, "/v1/", "", "", ""))
    return normalized

def run_benchmark(args):
    endpoint = args.endpoint
    api_key = args.api_key
    print(f"endpoint: {endpoint}")
    print(f"api_key: {api_key}")
    endpoint = url_reduce(endpoint)
    print(f"normalized endpoint: {endpoint}")
    workload_config = WorkloadConfig.from_endpoint(endpoint, api_key)
    workload_generator = WorkloadGenerator(workload_config, endpoint, api_key)
    asyncio.run(workload_generator.infinitely_benchmark())