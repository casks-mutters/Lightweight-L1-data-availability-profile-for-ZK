# README.md
# da_profile

Overview
da_profile is a small command-line tool that connects to an EVM-compatible network via web3.py and computes a data-availability profile over recent blocks. It focuses on calldata size and an approximate intrinsic gas cost, giving you a quick view of how “expensive” your L1 data layer is for rollups and ZK systems.

This profile can be used as a public input or calibration artifact in:
- Aztec-style rollups and privacy layers
- Zama-style ZK or homomorphic experiments that need realistic L1 gas/data parameters
- General soundness and cost-verification systems that must anchor to real L1 conditions

The tool does not prove anything by itself, but it provides a deterministic, JSON-encoded snapshot that can be embedded into ZK circuits, soundness verifiers, or monitoring pipelines.

Files
This repository consists of exactly two files:
1) app.py — the main script that computes the data-availability profile.
2) README.md — this documentation.

Requirements
- Python 3.10 or newer
- Internet access to reach an RPC endpoint
- An EVM-compatible JSON-RPC endpoint (Ethereum, Polygon, Optimism, Arbitrum, Base, etc.)
- Python package web3 installed in your environment

Installation
1) Install Python 3.10 or newer on your system.
2) Install web3 by running:
   pip install web3
3) Configure your RPC endpoint:
   - Set the RPC_URL environment variable, for example:
     export RPC_URL="https://mainnet.infura.io/v3/your_real_key"
   - Alternatively, pass the endpoint explicitly with the --rpc flag.

If RPC_URL is not set and the default URL still contains your_api_key, the script will warn you and likely fail until you provide a working endpoint.

Usage
Run with defaults (scan the last DA_PROFILE_BLOCKS blocks, sampling every DA_PROFILE_STEP):
   python app.py

Explicit RPC endpoint:
   python app.py --rpc https://your-rpc-url

Change the number of blocks scanned:
   python app.py --blocks 512

Sample every Nth block to reduce RPC load:
   python app.py --step 4

Pin the head block for reproducible ZK or soundness runs:
   python app.py --head 19000000

Pretty-print the JSON output:
   python app.py --pretty

Disable human-readable logging (only JSON on stdout):
   python app.py --no-human

All human-readable logs (network info, progress, timings) are written to stderr, so you can safely redirect JSON from stdout without mixing logs and structured data.

What the Script Computes
For each sampled block:
- Fetch all transactions (full_transactions=True).
- Extract tx input / calldata and compute:
  - calldataBytes: length of the hex-encoded input in bytes.
  - intrinsicGasEstimate: an approximate intrinsic gas cost assuming:
    - 4 gas per zero byte
    - 16 gas per non-zero byte
    - Using a simple 50/50 heuristic for zero vs non-zero distribution when needed.

The script aggregates:
- totalTxs: number of transactions scanned.
- txsWithCalldata: number of transactions whose calldataBytes is greater than zero.
- txsWithCalldataRatio: fraction of transactions carrying any calldata.
- calldataBytesStats: basic distribution statistics for calldata size.
- intrinsicGasEstimateStats: same statistics for intrinsic gas estimate.

For both bytes and gas, it computes:
- min
- max
- avg
- p50 (median)
- p90
- p99

Output Format
The script prints a single JSON object to stdout with the structure:

- mode: always "da_profile"
- generatedAtUtc: UTC timestamp when the profile was generated
- data:
  - chainId: numeric chain ID
  - network: human-readable network name when known
  - headBlock: latest block in the sampled window
  - oldestBlock: earliest block in the sampled window
  - sampledBlocks: number of blocks actually processed
  - step: sampling step between blocks
  - totalTxs: number of transactions seen
  - txsWithCalldata: number of transactions with non-empty calldata
  - txsWithCalldataRatio: txsWithCalldata / totalTxs as a float
  - calldataBytesStats: {min, max, avg, p50, p90, p99}
  - intrinsicGasEstimateStats: {min, max, avg, p50, p90, p99}
  - elapsedSec: total time spent computing the profile

ZK / Aztec / Zama / Soundness Context
The da_profile snapshot is intentionally compact but informative:
- It lets you model realistic bounds for calldata sizes and intrinsic gas when designing ZK circuits or rollup constraints.
- You can fix a particular profile as a public input to a proof, thereby tying a ZK system to a specific L1 data environment.
- Aztec or Zama-style experiments can use the profile to parameterize circuit sizes, fee bounds, or cryptographic batch sizes.

Examples:
- An Aztec rollup can use the profile to assert that its data-availability and fee assumptions are within realistic ranges observed on L1.
- A Zama experiment may use intrinsicGasEstimateStats as parameters for simulating gas-cost distributions inside a privacy-preserving analytics pipeline.
- A soundness checker can combine da_profile output with other on-chain commitments (e.g., state roots) to ensure the ZK system is not “lying” about its underlying L1 environment.

Notes and Limitations
- The intrinsic gas model used here is a simplified approximation (classic zero vs non-zero byte formula). It does not account for all EVM gas nuances and should not be treated as an exact fee oracle.
- The tool depends on the RPC endpoint for correctness. For critical environments, you should use a trusted node or cross-validate across multiple providers.
- Blocks and step affect both precision and runtime. A small step (1 or 2) yields more precise statistics but more RPC calls. A larger step trades precision for speed.
- This is read-only analysis. It does not send transactions or modify state.

Expected Result
When you run da_profile with a valid RPC endpoint, you should see:
- A short log on stderr describing the network, block range, number of sampled blocks, total transactions, and timing.
- A JSON object on stdout containing the DA profile, ready to be:
  - Stored as an artifact next to ZK proofs.
  - Ingested by Aztec/Zama proof tooling or research scripts.
  - Used by internal monitoring and soundness-verification pipelines that reason about L1 data availability and gas usage.
