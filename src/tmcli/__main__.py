import argparse
from tmcli.benchmark.bench import run_benchmark

def main():
    parser = argparse.ArgumentParser(prog="tm-cli")
    subparsers = parser.add_subparsers(dest="command")

    # --- benchmark subcommand ---
    p_bench = subparsers.add_parser("benchmark", help="Run benchmark")
    p_bench.add_argument("--endpoint", required=True)
    p_bench.add_argument("--api-key", required=True)
    p_bench.set_defaults(func=run_benchmark)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)