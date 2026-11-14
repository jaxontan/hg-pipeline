#!/usr/bin/env python3
"""bench-sage.py — prove SageAttention is real on this GPU.

    source ~/Desktop/AIGC-Model/env.sh && venv/bin/python bin/bench-sage.py

A SageAttention install can "succeed" three different ways and only one of them
is useful:

  1. the module imports, but the kernel for this arch was never compiled, so
     every call raises and the caller silently falls back to SDPA  (invisible)
  2. the kernel exists but runs a generic path for the wrong arch          (slow)
  3. the kernel is native for sm_121 and beats SDPA measurably           (this)

This script distinguishes all three: it times both paths, and it checks the
numbers against exact attention so a fast-but-wrong kernel cannot pass.
"""

import sys
import time

import torch
import torch.nn.functional as F


def line(k, v):
    print(f"  {k:<16} {v}")


def med(fn, iters=20, warmup=5):
    """Median seconds per call.

    Each *block* is timed between two synchronises. Timing individual async
    launches measures the CUDA driver queueing a kernel (~10 us), not the kernel
    running — which once made this script report 11,579 TFLOP/s and a 0.13x
    "speedup". Sync per block, divide by the number of calls.
    """
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        for _ in range(iters):
            fn()
        torch.cuda.synchronize()
        ts.append((time.perf_counter() - t0) / iters)
    ts.sort()
    return ts[len(ts) // 2]


print("=" * 66)
print("SageAttention proof ·", torch.cuda.get_device_name(0))
print("=" * 66)

try:
    import sageattention
    from sageattention import sageattn
except Exception as e:                                    # noqa: BLE001
    print(f"  FAIL — import: {type(e).__name__}: {e}")
    sys.exit(1)

try:
    from importlib.metadata import version as _v
    line("version", _v("sageattention"))
except Exception:
    line("version", "unknown")

# Which compiled kernels actually exist for this device?
import sageattention as _sa
mods = {}
for name in ("_qattn_sm80", "_qattn_sm89", "_qattn_sm90", "_fused"):
    try:
        getattr(_sa, name)
        mods[name] = "loaded"
    except Exception as e:                                # noqa: BLE001
        mods[name] = f"absent ({type(e).__name__})"
for k, v in mods.items():
    line("kernel " + k, v)

cap = torch.cuda.get_device_capability(0)
line("device", f"sm_{cap[0]}{cap[1]}")

# ---- does it actually run? -----------------------------------------------
B, H, S, D = 1, 24, 4096, 128
q = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)
k = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)
v = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)

print()
try:
    out_sage = sageattn(q, k, v, is_causal=False, tensor_layout="HND")
    torch.cuda.synchronize()
    line("first call", f"ok  shape={tuple(out_sage.shape)} dtype={out_sage.dtype}")
except Exception as e:                                    # noqa: BLE001
    print(f"  FAIL — sageattn raised: {type(e).__name__}: {e}")
    print("  A raise here is usually 'not compiled for this arch'. Fallbacks are silent")
    print("  in ComfyUI, which is exactly why this script exists.")
    sys.exit(1)

# ---- accuracy: fast-but-wrong must not pass ------------------------------
ref = F.scaled_dot_product_attention(q, k, v)
a = out_sage.float().flatten()
b = ref.float().flatten()
cos = torch.nn.functional.cosine_similarity(a, b, dim=0).item()
rel = (out_sage.float() - ref.float()).abs().mean().item() / ref.float().abs().mean().item()
line("cosine vs SDPA", f"{cos:.6f}")
line("mean rel error", f"{rel:.4%}")
if cos < 0.99:
    print("  FAIL — output diverges from exact attention. Do not ship this build.")
    sys.exit(1)

# ---- speed ---------------------------------------------------------------
print(f"\n  {'seq':>6} {'SDPA ms':>9} {'sage ms':>9} {'speedup':>8} {'sage TFLOP/s':>13}")
best = 0.0
for S in (1024, 2048, 4096, 8192, 16384, 32768):
    q = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)
    k = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)
    v = torch.randn(B, H, S, D, device="cuda", dtype=torch.float16)
    flops = 4 * B * H * S * S * D
    iters = max(3, int(1e11 / flops))
    t_ref = med(lambda: F.scaled_dot_product_attention(q, k, v), iters=iters, warmup=3)
    t_sage = med(lambda: sageattn(q, k, v, is_causal=False, tensor_layout="HND"), iters=iters, warmup=3)
    tf = flops / t_sage / 1e12
    best = max(best, t_ref / t_sage)
    print(f"  {S:>6} {t_ref*1e3:>9.2f} {t_sage*1e3:>9.2f} {t_ref/t_sage:>7.2f}x {tf:>13.1f}")
    del q, k, v
    torch.cuda.empty_cache()

print()
line("peak allocated", f"{torch.cuda.max_memory_allocated()/2**30:.2f} GiB")
print()
if best >= 1.5:
    print(f"  VERDICT: ACTIVE — up to {best:.2f}x SDPA, numerics within tolerance")
elif best >= 1.05:
    print(f"  VERDICT: working but marginal — {best:.2f}x. Check the kernel arch with cuobjdump.")
else:
    print(f"  VERDICT: NO GAIN ({best:.2f}x) — it runs, but not natively. Do not enable it.")
    print("           ComfyUI would take the slow path believing it is accelerated.")
    sys.exit(2)
