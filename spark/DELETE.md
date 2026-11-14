# DELETE.md — how to remove every trace of this project in one shot

**Read this before the wipe.** The operator's requirement is that `~/Desktop/AIGC-Model`
can be deleted in a single operation and the machine returns to pristine. That is only
true if everything this project put *outside* the folder is listed here.

Everything below is generated from `app/os/installed.tsv` (the install ledger) and
`app/os/apt.baseline.tsv` (the pristine baseline). If it is not in this file, it does not
exist — and if `bin/doctor.sh` reports something that is not in this file, that is a bug.

## 1. The folder itself

```bash
rm -rf ~/Desktop/AIGC-Model
```

That removes: models (picture, tts, asr), both venvs (`app/venv`, `app/venv-tts`), ComfyUI,
Blender, caches, temp, logs, work products, provenance, the ledger, and the `HOME` of any
process started under `env.sh` (because `env.sh` sets `HOME` inside the folder).

## 2. System packages installed by this project

Recorded in `app/os/installed.tsv`, layer `apt`. At the time of writing:

| Date | Package | Version | Why |
|---|---|---|---|
| 2026-11-13 | `python3.12-dev` | 3.12.3-1ubuntu0.17 | C headers — SageAttention and every torch extension compile needs `Python.h` |
| 2026-11-13 | `ffmpeg` (+75 deps) | 7:6.1.1-3ubuntu5+esm15 | every video lane; `libx264`/`libx265`/`aac`/`libopus` confirmed present |
| 2026-11-14 | `sox` (+`libsox-fmt-base`, `libsox3`) | 14.4.2+git20190427-4build4 | `qwen-tts` imports the pysox binding, which shells out to this binary — the *binary*, not `libsox-dev` headers |

Reverse them in one pass. The list file lives inside the folder, never in `/tmp`:

```bash
# regenerate the exact list from the ledger
awk -F'\t' '$2=="apt"{print $3}' ~/Desktop/AIGC-Model/app/os/installed.tsv \
  | tr ',' '\n' | sort -u > ~/Desktop/AIGC-Model/tmp/pkglist
sudo apt-get remove --purge -y $(cat ~/Desktop/AIGC-Model/tmp/pkglist)
sudo apt-get autoremove --purge -y
rm -f ~/Desktop/AIGC-Model/tmp/pkglist
```

## 3. Things in `/usr/local/bin`

`uv` installs to `~/.local/bin` (inside the redirected `HOME`, so it dies with the folder).
Anything installed to `/usr/local/bin` is captured by `app/os/usr-local-bin.txt` and diffed
by `doctor.sh`. Undo:

```bash
comm -13 <(sort ~/Desktop/AIGC-Model/app/os/usr-local-bin.baseline.txt 2>/dev/null) \
         <(ls -1 /usr/local/bin | sort) | sudo xargs -r -I{} rm -f /usr/local/bin/{}
```

## 4. Docker (Oracle stack — stopped, not ours, pending decision)

Images and volumes live in `/var/lib/docker`, outside the folder. They were **stopped**,
not created, by this project. If the stack is retired:

```bash
docker system prune -a --volumes -f     # destroys the Oracle DB images AND data
```

**This deletes the database.** It is a separate decision from the folder wipe and is
listed here only so the wipe is complete if that decision is ever taken.

## 5. Known residue that env vars cannot prevent

| Trace | Written by | Where | Harmless? |
|---|---|---|---|
| `/tmp/perf-<pid>.map` | PyTorch profiler symbols | `/tmp` | yes — delete with `rm -f /tmp/perf-*.map` |
| `~/.ssh/authorized_keys` | key auth setup, if installed | real home | remove the specific line |

`doctor.sh` reports both. Neither is a project artifact you need to keep.

## 6. Swap / clock / policy changes

None. This project does **not** run `swapoff`, does **not** set `nvidia-smi -lgc`, and
does **not** change any systemd unit. If a future step needs one, it is recorded in the
ledger and added here first.

## 7. Verification after the wipe

```bash
test -d ~/Desktop/AIGC-Model && echo "STILL THERE" || echo "folder gone"
ls ~/.cache/huggingface ~/.cache/torch ~/.cache/pip 2>/dev/null   # expect: nothing
free -m | head -2                                                  # memory back to idle
df -h / | tail -1                                                  # disk reclaimed
```
