# app.py
"""
da_profile: Lightweight L1 data-availability profile for ZK / rollup soundness.

This script:
  - Connects to an EVM-compatible network via web3.py
  - Samples recent blocks (or a user-defined range)
  - Computes stats on calldata size and intrinsic gas usage per transaction
  - Outputs a compact JSON summary suitable for Aztec-style rollups, Zama experiments,
    or any soundness-focused system that needs an L1 data-availability profile.
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, List
from web3 import Web3

DEFAULT_RPC = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")
DEFAULT_BLOCKS = int(os.getenv("DA_PROFILE_BLOCKS", "256"))
DEFAULT_STEP = int(os.getenv("DA_PROFILE_STEP", "1"))

NETWORKS: Dict[int, str] = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
    8453: "Base",
    43114: "Avalanche C-Chain",
}


def network_name(cid: int) -> str:
    return NETWORKS.get(cid, f"Unknown (chain ID {cid})")


def connect(rpc: str) -> Web3:
    start = time.time()
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 25}))
    if not w3.is_connected():
        print(f"❌ Failed to connect to RPC endpoint: {rpc}", file=sys.stderr)
        sys.exit(1)

    latency = time.time() - start
    try:
        cid = int(w3.eth.chain_id)
        tip = int(w3.eth.block_number)
        print(
            f"🌐 Connected to {network_name(cid)} (chainId {cid}, tip={tip}) in {latency:.2f}s",
            file=sys.stderr,
        )
    except Exception:
        print(f"🌐 Connected to RPC (chain info unavailable) in {latency:.2f}s", file=sys.stderr)

    return w3


def tx_calldata_bytes(tx: Any) -> int:
    """
    Return size of tx input data in bytes.
    Works for both dict and AttributeDict tx objects.
    """
    if isinstance(tx, dict):
        data = tx.get("input") or tx.get("data") or ""
    else:
        data = getattr(tx, "input", "") or getattr(tx, "data", "")
    if not isinstance(data, str):
        return 0
    if data.startswith("0x"):
        data = data[2:]
    if not data:
        return 0
    return len(data) // 2


def intrinsic_gas_estimate(data_bytes: int) -> int:
    """
    Approximate intrinsic gas cost for transaction data only,
    following the classic formula:
      4 gas for each zero byte,
      16 gas for each non-zero byte.
    Here we approximate assuming half zero / half non-zero when unknown.
    """
    if data_bytes <= 0:
        return 0
    # naive heuristic: 50% zero, 50% non-zero
    half = data_bytes // 2
    zeros = data_bytes - half
    nonzeros = half
    return zeros * 4 + nonzeros * 16


def analyze_da_profile(w3: Web3, blocks: int, step: int, head: int | None = None) -> Dict[str, Any]:
    tip = int(w3.eth.block_number) if head is None else int(head)
    start_block = max(0, tip - blocks + 1)

    print(
        f"🔍 Sampling data-availability profile from blocks [{start_block}, {tip}] "
        f"(step={step})...",
        file=sys.stderr,
    )

    t0 = time.time()
    total_txs = 0
    txs_with_data = 0
    bytes_list: List[int] = []
    intrinsic_gas_list: List[int] = []
    sampled_blocks = 0

    for n in range(tip, start_block - 1, -step):
        blk = w3.eth.get_block(n, full_transactions=True)
        sampled_blocks += 1
        for tx in blk.transactions:
            total_txs += 1
            b = tx_calldata_bytes(tx)
            if b > 0:
                txs_with_data += 1
            bytes_list.append(b)
            intrinsic_gas_list.append(intrinsic_gas_estimate(b))

        if sampled_blocks % 16 == 0:
            print(
                f"   ⏳ At block {n} (sampled={sampled_blocks}, txs={total_txs})",
                file=sys.stderr,
            )

    elapsed = time.time() - t0

    def stats(xs: List[int]) -> Dict[str, float | int]:
        if not xs:
            return {"min": 0, "max": 0, "avg": 0.0, "p50": 0.0, "p90": 0.0, "p99": 0.0}
        ys = sorted(xs)
        n = len(ys)

        def percentile(q: float) -> float:
            if n == 1:
                return float(ys[0])
            q = max(0.0, min(1.0, q))
            idx = int(round(q * (n - 1)))
            return float(ys[idx])

        avg = sum(ys) / n
        return {
            "min": float(ys[0]),
            "max": float(ys[-1]),
            "avg": float(round(avg, 3)),
            "p50": float(round(percentile(0.5), 3)),
            "p90": float(round(percentile(0.9), 3)),
            "p99": float(round(percentile(0.99), 3)),
        }

    bytes_stats = stats(bytes_list)
    gas_stats = stats(intrinsic_gas_list)
    cid = int(w3.eth.chain_id)

    return {
        "chainId": cid,
        "network": network_name(cid),
        "headBlock": tip,
        "oldestBlock": start_block,
        "sampledBlocks": sampled_blocks,
        "step": step,
        "totalTxs": total_txs,
        "txsWithCalldata": txs_with_data,
        "txsWithCalldataRatio": float(round(txs_with_data / total_txs, 4)) if total_txs else 0.0,
        "calldataBytesStats": bytes_stats,
        "intrinsicGasEstimateStats": gas_stats,
        "elapsedSec": float(round(elapsed, 3)),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Profile L1 data-availability (calldata bytes and intrinsic gas) for ZK/soundness systems.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default from RPC_URL env)")
    p.add_argument("-b", "--blocks", type=int, default=DEFAULT_BLOCKS, help="Number of recent blocks to scan")
    p.add_argument("-s", "--step", type=int, default=DEFAULT_STEP, help="Sample every Nth block")
    p.add_argument("--head", type=int, help="Override head block (default: current chain tip)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    p.add_argument("--no-human", action="store_true", help="Disable human-readable summary")
    return p.parse_args()


def main() -> None:
    if "your_api_key" in DEFAULT_RPC:
        print(
            "⚠️  RPC_URL is not set and DEFAULT_RPC still uses a placeholder key. "
            "Set RPC_URL or pass --rpc.",
            file=sys.stderr,
        )

    args = parse_args()
    if args.blocks <= 0 or args.step <= 0:
        print("❌ --blocks and --step must be > 0", file=sys.stderr)
        sys.exit(1)

    print(
        f"📅 da_profile run at UTC {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}",
        file=sys.stderr,
    )
    print(f"🔗 Using RPC endpoint: {args.rpc}", file=sys.stderr)

    w3 = connect(args.rpc)
    result = analyze_da_profile(w3, args.blocks, args.step, args.head)

    payload = {
        "mode": "da_profile",
        "generatedAtUtc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "data": result,
    }

    if not args.no-human:
        # small human summary to stderr
        print(
            f"🌐 {result['network']} (chainId {result['chainId']}) "
            f"blocks [{result['oldestBlock']}, {result['headBlock']}] "
            f"sampled={result['sampledBlocks']} step={result['step']}",
            file=sys.stderr,
        )
        print(
            f"📦 totalTxs={result['totalTxs']} txsWithCalldata={result['txsWithCalldata']} "
            f"ratio={result['txsWithCalldataRatio']}",
            file=sys.stderr,
        )
        print(
            f"⏱️  Elapsed: {result['elapsedSec']}s",
            file=sys.stderr,
        )

    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
