"""Assemble the standalone project page from results/*.json (run from the repo root).

    python site/build_page.py      # writes site/index.html (one file, no external assets)

Everything is inlined: published qBraid artifacts allow only inline scripts, styles and
data: images.
"""
import base64
import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
R = lambda name: json.loads((ROOT / "results" / name).read_text())

C6 = 865723.02                     # FRESNEL_CAN1 interaction coefficient, rad/µs·µm^6
PER_MIN = 6358.0                   # FRESNEL_CAN1 price, credits per QPU minute (Nov 2026)
SEC_PER_SHOT = 1.2                 # measured: 10 shots used 12 s
rb = lambda omega: (C6 / omega) ** (1 / 6)
u = lambda r: C6 / r ** 6

layout = json.loads((ROOT / "site" / "fresnel_60.json").read_text())

c1, c2, c3, c4, m49 = R("01_blockade.json"), R("02_af_chain.json"), R("03_magnet.json"), R("04_mis.json"), R("49_atom_emu_mps.json")

ch1 = {k: c1[k] for k in ("traps", "durations", "emu", "exact", "shots", "max_A_both")}
ch1["rb"] = rb(c1["omega"])
ch1["dev"] = sum(c1["mean_abs_dev"].values()) / len(c1["mean_abs_dev"])

ch2 = {k: c2[k] for k in ("traps", "omega", "delta_end", "emu", "exact", "snapshots")}
ch2["rb"] = rb(c2["omega"])
ch2["snap_index"] = len(c2["delta_end"]) - 2
ch2["best"] = max(range(len(c2["emu"])), key=lambda i: c2["emu"][i]["neel"])
neel = "".join("1" if i % 2 == 0 else "0" for i in range(len(c2["traps"])))
ch2["wall"] = next((b for b in c2["snapshots"] if b != neel), neel)

ch3 = {k: c3[k] for k in ("traps", "delta_end", "emu", "exact", "snapshots")}
ch3["rb"] = rb(c3["omega"])
ch3["n_per_atom"] = [e.get("n_i", [e["n"]] * len(c3["traps"])) for e in c3["emu"]]
ch3["u5"] = u(5.0)
ch3["snap_index"] = c3["delta_end"].index(24)
on = [d for d, e in zip(c3["delta_end"], c3["emu"]) if e["crystal"] >= 0.85]
ch3["plateau"] = [min(on), max(on)] if on else [10, 50]
ch3["best_crystal"] = max(e["crystal"] for e in c3["emu"])

edges = [tuple(e) for e in c4["edges"]]
indep = lambda b: all(not (b[a] == "1" and b[c] == "1") for a, c in edges)
ch4 = {k: c4[k] for k in ("traps", "edges", "mis", "mis_sets", "durations", "emu", "exact", "shots", "top_slowest", "classical_ms")}
ch4["indep"] = {b: indep(b) for b, _ in c4["top_slowest"]}

n_jobs = len(c1["durations"]) + len(c2["delta_end"]) + len(c3["delta_end"]) + len(c4["durations"])

costs = []
for name, jobs, shots in [("1 · Blockade: 2 pulse lengths", 2, 50), ("2 · Antiferromagnet: deep in the ordered phase", 1, 100),
                          ("3 · ⅓ plateau: on and past the plateau", 2, 50), ("4 · MIS: slowest sweep", 1, 100)]:
    sec = SEC_PER_SHOT * jobs * shots
    costs.append({"name": name, "jobs": jobs, "shots": shots, "seconds": sec, "credits": PER_MIN * sec / 60})

CODE = {
    "1": {
        "Emulator": {"src": '''import numpy as np
from pasqal_atoms import layout_register, resonant_pulse, run_many, densities, prob

OMEGA = 2 * np.pi * 1.0                       # rad/µs
reg = layout_register([9, 18, 56, 59, 8])     # A: 5 µm pair, B: 10 µm pair, C: lone atom
durations = [16, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200]
seqs = [resonant_pulse(reg, t, OMEGA) for t in durations]

counts = run_many(seqs, target="emu", shots=500)            # Pasqal EMU_FREE, free
for t, c in zip(durations, counts):
    print(t, "A both:", prob(c, lambda b: b[:2] == "11"),   # stays ~0: blockade
             "C:", densities(c)[4])'''},
        "QPU": {"src": '''from pasqal_atoms import qpu_estimate, submit, wait

print(qpu_estimate(shots=50, n_jobs=2))     # credits, before you commit
jobs = [submit(resonant_pulse(reg, t, OMEGA), "qpu", shots=50, confirm_qpu=True)
        for t in (350, 700)]                # half and full collective period
print([j.id for j in jobs])                 # QPU queues can take days: keep the IDs
# later: counts = wait(jobs, timeout=7 * 24 * 3600)'''},
        "Under the hood": {"src": '''import numpy as np
from pulser import Pulse, Sequence
from pasqal_atoms import fresnel, layout, check_for_qpu

dev = fresnel()                             # live FRESNEL_CAN1 specs from Pasqal's public API
reg = layout(60).define_register(9, 18, 56, 59, 8, qubit_ids=[f"q{i}" for i in range(5)])
seq = Sequence(reg, dev)                    # built on the real device, not AnalogDevice
seq.declare_channel("ryd", "rydberg_global")
seq.add(Pulse.ConstantPulse(352, 2 * np.pi, 0.0, 0.0), "ryd")   # ns, rad/µs
seq.measure("ground-rydberg")
check_for_qpu(seq)                          # raises what Pasqal would reject'''},
    },
    "2": {
        "Emulator": {"src": '''import numpy as np
from pasqal_atoms import layout_register, adiabatic_sweep, run_many, prob

OMEGA, DELTA_START = 2 * np.pi, -2 * np.pi * 2.5     # rad/µs
reg = layout_register([2, 10, 19, 28, 37, 46, 54])   # one row of the layout, 5 µm apart
deltas = [-6, 0, 4, 8, 12, 16, 24]                    # final detuning, rad/µs
seqs = [adiabatic_sweep(reg, OMEGA, DELTA_START, d, duration=4000) for d in deltas]

counts = run_many(seqs, target="emu", shots=500)
for d, c in zip(deltas, counts):
    print(f"Δ/Ω = {d / OMEGA:4.1f}   P(1010101) = {prob(c, lambda b: b == '1010101'):.2f}")'''},
        "QPU": {"src": '''from pasqal_atoms import qpu_estimate, submit

seq = adiabatic_sweep(reg, OMEGA, DELTA_START, 16, duration=4000)
print(qpu_estimate(shots=100))
job = submit(seq, "qpu", shots=100, confirm_qpu=True)
print(job.id)      # check later: qbraid jobs get <id>, or the Quantum Jobs panel'''},
    },
    "3": {
        "Emulator": {"src": '''import numpy as np
from pasqal_atoms import (layout_register, adiabatic_sweep, run_many, magnetization,
                          unit_disk_edges, max_independent_sets, prob)

TRAPS = [1, 4, 7, 8, 12, 13, 16, 17, 21, 22, 26, 31]      # 3x4 rhombus, 5 µm
reg = layout_register(TRAPS)
k, crystals = max_independent_sets(12, unit_disk_edges(TRAPS))   # k = 4 = 12/3
deltas = [-6, 0, 3, 6, 10, 16, 24, 40, 50, 60]               # |Δ| <= 62.8 rad/µs on FRESNEL_CAN1
seqs = [adiabatic_sweep(reg, 2 * np.pi, -2 * np.pi * 2.5, d, duration=5000) for d in deltas]

counts = run_many(seqs, target="emu", shots=500)
crystal = lambda b: tuple(i for i, x in enumerate(b) if x == "1") in set(crystals)
for d, c in zip(deltas, counts):
    print(f"Δ = {d:3d}   m = {magnetization(c):+.3f}   P(⅓ crystal) = {prob(c, crystal):.2f}")'''},
        "QPU": {"src": '''from pasqal_atoms import qpu_estimate, submit

print(qpu_estimate(shots=50, n_jobs=2))
jobs = [submit(adiabatic_sweep(reg, 2 * np.pi, -2 * np.pi * 2.5, d, duration=5000),
               "qpu", shots=50, confirm_qpu=True) for d in (24, 60)]   # on, and past, the plateau
print([j.id for j in jobs])'''},
        "49 atoms": {"src": '''# Bigger registers: the 217-trap layout (must be 35-55% filled) and a billed emulator
from pasqal_atoms import layout_register
import pasqal_atoms

reg49 = layout_register(trap_ids_7x7, n_traps=217)      # pick 49 trap ids from layout(217).traps_dict
pasqal_atoms.EMULATOR = "pasqal:pasqal:sim:emu-mps"     # tensor-network emulator, billed per minute
# check the price first: qbraid devices get pasqal:pasqal:sim:emu-mps'''},
    },
    "4": {
        "Emulator": {"src": '''import numpy as np
from pasqal_atoms import (layout_register, adiabatic_sweep, run_many, unit_disk_edges,
                          max_independent_sets, is_independent, prob)

TRAPS = [15, 19, 20, 23, 24, 28, 32, 33, 37, 38, 42, 47]
reg, E = layout_register(TRAPS), unit_disk_edges(TRAPS)    # edges = pairs 5 µm apart
k, best = max_independent_sets(12, E)                        # classical answer: size 5, unique
durations = [800, 2000, 3500, 5000]                          # ns
seqs = [adiabatic_sweep(reg, 2 * np.pi, -2 * np.pi * 2.5, 2 * np.pi * 2, duration=T,
                        rise=min(500, T // 4)) for T in durations]

counts = run_many(seqs, target="emu", shots=500)
is_mis = lambda b: tuple(i for i, x in enumerate(b) if x == "1") in set(best)
for T, c in zip(durations, counts):
    print(f"{T} ns   P(MIS) = {prob(c, is_mis):.2f}   valid = {prob(c, lambda b: is_independent(b, E)):.3f}")'''},
        "QPU": {"src": '''from pasqal_atoms import qpu_estimate, submit

print(qpu_estimate(shots=100))
job = submit(seqs[-1], "qpu", shots=100, confirm_qpu=True)   # the slow, 5 µs sweep
print(job.id)'''},
    },
    "run": {
        "qBraid project": {"sh": 1, "src": '''# In qBraid Lab: Explore → Projects → "Neutral Atoms on qBraid" → Install
# or from a terminal:
qbraid projects get __PROJECT_SLUG__ --setup --inspect-repository --json   # review what it installs
qbraid projects install __PROJECT_SLUG__ --reviewed-revision <revision from the command above>'''},
        "By hand": {"sh": 1, "src": '''git clone https://github.com/qBraid/pasqal-neutral-atoms.git
qbraid envs install pasqal_js2dr3                  # "Pasqal (Pulser)": qBraid SDK + Pulser, with kernel
qbraid skills install pasqal_wk1xlv --target all   # optional: the pasqal-on-qbraid agent skill
# open notebooks/01_rydberg_blockade.ipynb with the kernel "Python 3 [Pasqal]"'''},
        "One switch": {"src": '''TARGET = "emu"     # "local": exact simulation on this machine, free
                   # "emu":   Pasqal EMU_FREE through qBraid, free, up to 12 atoms
                   # "qpu":   Pasqal FRESNEL_CAN1 through qBraid, billed per QPU minute
CONFIRM_QPU = False   # the QPU cell prints an estimate and submits only when this is True'''},
    },
}

slug = (SITE / "project_slug.txt").read_text().strip() if (SITE / "project_slug.txt").exists() else "pasqal-neutral-atoms"
for tabs in CODE.values():
    for t in tabs.values():
        t["src"] = t["src"].replace("__PROJECT_SLUG__", slug)

DATA = {"layout": layout, "rb_hero": rb(2 * 3.141592653589793), "u5": u(5.0), "ch1": ch1, "ch2": ch2, "ch3": ch3, "ch4": ch4,
        "mps49": {"mps": m49["mps"], "exact": m49["exact"], "credits": m49["credits"]},
        "n_jobs": n_jobs, "costs": costs, "per_min": PER_MIN, "code": CODE,
        "built": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y")}

html = (SITE / "page.src.html").read_text()
qbraid = "data:image/svg+xml;base64," + base64.b64encode((SITE / "assets/qbraid_logo.svg").read_bytes()).decode()
pasqal = (SITE / "assets/pasqal_wordmark.svg").read_text().strip()
three = (SITE / "vendor/three.min.js").read_text()
data = json.dumps(DATA, separators=(",", ":")).replace("</", "<\\/")
html = (html.replace("/*__THREE__*/", three).replace("/*__DATA__*/", data)
        .replace("__QBRAID_SRC__", qbraid).replace("<!--__PASQAL__-->", pasqal))
(SITE / "index.html").write_text(html)
print(f"wrote site/index.html, {len(html) // 1024} KiB, {n_jobs} emulator jobs")
