#!/usr/bin/env python3
"""bench.py — measure this GPU honestly, so a slow path cannot hide.

    source ~/Desktop/AIGC-Model/env.sh && venv/bin/python bin/bench.py

Almost every "the box is slow" story in diffusion work is one of four things:
a kernel that silently fell back to a reference path, a dtype that lost tensor
cores, clocks that never left idle, or unified memory thrashing. This script
separates all four. It allocates at most ~1.5 GiB and runs in well under a
minute, so it cannot disturb the machine.
"""

import sys
import time

import torch


def bench(fn, iters, warmup=3):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


def line(k, v):
    print(f"  {k:<22} {v}")


print("=" * 62)
print("GPU benchmark ·", torch.cuda.get_device_name(0))
print("=" * 62)

props = torch.cuda.get_device_properties(0)
line("torch", torch.__version__)
line("cuda", torch.version.cuda)
line("capability", f"sm_{props.major}{props.minor}")
line("arch list", ", ".join(torch.cuda.get_arch_list()))
line("SMs", getattr(props, "multi_processor_count", "?"))
line("total mem", f"{props.total_memory / 2**30:.1f} GiB")
line("tf32 matmul", torch.backends.cuda.matmul.allow_tf32)
line("cudnn tf32", torch.backends.cudnn.allow_tf32)

exact = f"sm_{props.major}{props.minor}"
archs = torch.cuda.get_arch_list()
print()
if exact in archs or f"{exact}a" in archs:
    print(f"  arch: native {exact} present")
else:
    best = max((int(a.split("_")[1].rstrip("a")) for a in archs), default=0)
    native = int(f"{props.major}{props.minor}")
    verdict = "PTX JIT from" if native > best else "backwards-compatible from"
    print(f"  arch: {verdict} the nearest compiled target ({exact} absent).")
    print("        A JIT is a one-time cost, but a *fallback* is permanent. The")
    print("        throughput table below is what tells the two apart.")

# ---- matmul: the tensor-core test ----------------------------------------
print("\nmatmul (2*N^3 per call)")
print(f"  {'N':>6} {'dtype':>7} {'ms':>9} {'TFLOP/s':>9} {'':>4}")
best_fp16 = 0.0
for dtype in (torch.float16, torch.bfloat16, torch.float32):
    for n in (1024, 2048, 4096, 8192):
        try:
            a = torch.randn(n, n, device="cuda", dtype=dtype)
            b = torch.randn(n, n, device="cuda", dtype=dtype)
            secs = bench(lambda: a @ b, iters=max(2, int(3e10 / (2 * n ** 3))), warmup=2)
            tflops = 2 * n ** 3 / secs / 1e12
            if dtype is torch.float16:
                best_fp16 = max(best_fp16, tflops)
            print(f"  {n:>6} {str(dtype).split('.')[-1]:>7} {secs*1e3:>9.2f} {tflops:>9.2f}")
            del a, b
            torch.cuda.empty_cache()
        except torch.OutOfMemoryError:
            print(f"  {n:>6} {str(dtype).split('.')[-1]:>7}   out of memory")
            torch.cuda.empty_cache()

# ---- memory bandwidth: the unified-memory test ---------------------------
print("\nmemory bandwidth (copy)")
for mib in (256, 1024):
    n = mib * 2 ** 20 // 4
    src = torch.empty(n, device="cuda", dtype=torch.float32)
    dst = torch.empty(n, device="cuda", dtype=torch.float32)
    secs = bench(lambda: dst.copy_(src), iters=20, warmup=3)
    gbps = 2 * n * 4 / secs / 1e9          # read + write
    print(f"  {mib:>4} MiB copy  {secs*1e3:>7.2f} ms  {gbps:>7.1f} GB/s")
    del src, dst
    torch.cuda.empty_cache()

# ---- attention: the path diffusion actually uses -------------------------
print("\nattention (SDPA, fp16, batch 1, heads 24, dim 128)")
import torch.nn.functional as F
for seq in (1024, 4096, 8192):
    q = torch.randn(1, 24, seq, 128, device="cuda", dtype=torch.float16)
    try:
        secs = bench(lambda: F.scaled_dot_product_attention(q, q, q), iters=10, warmup=2)
        tflops = 4 * seq * seq * 128 * 24 / secs / 1e12
        print(f"  seq {seq:>5}  {secs*1e3:>7.2f} ms  {tflops:>7.2f} TFLOP/s")
    except torch.OutOfMemoryError:
        print(f"  seq {seq:>5}  out of memory")
    del q
    torch.cuda.empty_cache()

# ---- verdict -------------------------------------------------------------
print()
print(f"  peak allocated this run: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
if best_fp16 >= 50:
    print(f"  VERDICT: healthy — {best_fp16:.0f} TFLOP/s fp16 is tensor-core territory")
elif best_fp16 >= 10:
    print(f"  VERDICT: usable but slow — {best_fp16:.0f} TFLOP/s fp16; tensor cores partly engaged")
else:
    print(f"  VERDICT: SLOW PATH — {best_fp16:.1f} TFLOP/s fp16. Not tensor cores.")
    print("           Investigate the kernel selection before blaming the model.")
