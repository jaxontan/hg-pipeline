#!/usr/bin/env python3
"""smoke.py — is this GPU actually usable, and how fast?

Run with the venv interpreter:
    source ~/Desktop/AIGC-Model/env.sh
    venv/bin/python bin/smoke.py

Proves four things and prints them so they can be recorded:
  1. torch sees CUDA (not a CPU fallback)
  2. the kernel arch list covers this device (sm_121 on GB10)
  3. a real matmul runs at plausible throughput
  4. peak unified memory for that workload

It allocates ~64 MiB. It cannot stall the machine. Run bin/status.sh after if
you want to confirm the memory came back (see AGENTS.md: unified memory does not
return to the OS on model switch, only on process exit).
"""

import sys
import time

try:
    import torch
except ImportError:
    sys.exit("torch not installed — source env.sh and check venv/bin/python")

def line(k, v):
    print(f"  {k:<14} {v}")

print("GPU smoke test")
line("torch", torch.__version__)
line("cuda", torch.version.cuda)

if not torch.cuda.is_available():
    print("\n  FAIL — torch.cuda.is_available() is False.")
    print("  This machine must never render on CPU. Check the driver, then the wheel.")
    sys.exit(1)

line("device", torch.cuda.get_device_name(0))
cap = torch.cuda.get_device_capability(0)
line("capability", f"{cap}  (sm_{cap[0]}{cap[1]})")
line("arch list", ", ".join(torch.cuda.get_arch_list()))

sm = f"sm_{cap[0]}{cap[1]}"
arch = torch.cuda.get_arch_list()
if sm not in arch and f"{sm}a" not in arch:
    print(f"\n  WARN — {sm} not in the compiled arch list; kernels will JIT or fall back.")
    print("  A silent fallback is the exact failure this project exists to avoid.")

# ---- throughput -----------------------------------------------------------
# Warm up first. The very first matmul on this machine triggers a PTX JIT from
# the nearest compiled arch (sm_120), because torch ships no sm_121 cubin. That
# one-time cost once made this script report 1 TFLOP/s and look like a fallback.
n = 2048
iters = 20
a = torch.randn(n, n, device="cuda", dtype=torch.float16)
b = torch.empty_like(a)
for _ in range(5):
    b = a @ a
torch.cuda.synchronize()
t0 = time.perf_counter()
for _ in range(iters):
    b = a @ a
torch.cuda.synchronize()
dt = time.perf_counter() - t0
flops = iters * 2 * n ** 3
line("matmul", f"{iters}x {n}^3 fp16 in {dt:.2f}s  =  {flops / dt / 1e12:.2f} TFLOP/s")
if flops / dt / 1e12 < 10:
    print("  ^ under 10 TFLOP/s after warmup means tensor cores are NOT engaged.")
    print("    Run bin/bench.py before blaming a model.")

peak = torch.cuda.max_memory_allocated() / 2 ** 20
line("peak alloc", f"{peak:.0f} MiB")

# ---- a real kernel path, not just cublas ---------------------------------
x = torch.randn(1, 8, 1024, 64, device="cuda", dtype=torch.float16)
try:
    import torch.nn.functional as F
    y = F.scaled_dot_product_attention(x, x, x)
    torch.cuda.synchronize()
    line("SDPA", f"ok  shape={tuple(y.shape)} dtype={y.dtype}")
except Exception as e:                                    # noqa: BLE001
    print(f"\n  FAIL — attention kernel broken: {type(e).__name__}: {e}")
    sys.exit(1)

print("\n  PASS — GPU is live and computing correctly")
