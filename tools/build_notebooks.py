"""Generate the four tutorial notebooks (run from the repo root).

    python tools/build_notebooks.py          # writes notebooks/*.ipynb (unexecuted)

Then execute them in the "Python 3 [Pasqal]" kernel to refresh outputs and results/.
"""
import pathlib

import nbformat as nbf

ROOT = pathlib.Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"
NB.mkdir(exist_ok=True)

SETUP = '''\
# Setup: needs the "Python 3 [Pasqal]" kernel (qBraid environment "Pasqal (Pulser)").
import sys, json, pathlib
try:
    import pulser, qbraid
except ImportError:
    raise SystemExit('Switch the kernel to "Python 3 [Pasqal]" (Kernel > Change Kernel), '
                     'or install the environment with: qbraid envs install pasqal_js2dr3')
ROOT = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib.pyplot as plt
from pasqal_atoms import *
print("pulser", pulser.__version__, "| qbraid", qbraid.__version__)'''

TARGET_MD = '''\
### Where to run

| `TARGET` | Runs on | Cost | Atoms |
|---|---|---|---|
| `"local"` | exact simulation on this machine (`pulser-simulation`) | free | up to ~12 |
| `"emu"` | Pasqal's **EMU_FREE** cloud emulator, through qBraid | free | up to 12 |
| `"qpu"` | Pasqal's **FRESNEL_CAN1** neutral-atom QPU, through qBraid | per minute of QPU time | up to 100 |

The sequences are built on FRESNEL_CAN1's real device specs and calibrated layout, so the
*same* object runs on all three. Start with `"emu"`; switch to `"qpu"` only after the
emulator result looks right and you have checked the estimate below.'''

QPU_MD = '''\
## Run it on the QPU

Everything above ran on the free emulator. The same sequences run unchanged on FRESNEL_CAN1.
QPU time is billed per minute and jobs wait in Pasqal's queue (hours to days), so:

1. Check the estimate (credits; 1 credit = USD 0.01). It is based on ~1.2 s of QPU time per shot.
2. Set `CONFIRM_QPU = True` and run the cell. It submits and prints the job IDs; it does not wait.
3. Come back later: `qbraid jobs get <id>`, or the Lab's **Quantum Jobs** panel.'''


def notebook(cells):
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3 [Pasqal]",
                                 "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    for kind, src in cells:
        nb.cells.append(nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src))
    return nb


def md(s):
    return ("md", s)


def code(s):
    return ("code", s)


# ------------------------------------------------------------------ 01 blockade
nb1 = notebook([
    md('''\
# 1 · The Rydberg blockade

**One atom, two atoms, no double excitation.** A laser drives each rubidium atom between its
ground state |g⟩ and a huge Rydberg state |r⟩. Two Rydberg atoms repel with a van der Waals
interaction U = C₆/r⁶. Closer than the *blockade radius*, U is far larger than the drive Ω,
so the pair can share one excitation but never hold two. That single rule is the
entangling resource behind everything else in this project.

In one register we place three things, far enough apart that they don't talk to each other:

* **A**, two atoms 5 µm apart: blockaded (U ≈ 55 rad/µs ≫ Ω)
* **B**, two atoms 10 µm apart: almost independent (U ≈ 0.9 rad/µs < Ω)
* **C**, a single atom for reference

and drive them all with one resonant pulse of increasing length.'''),
    code(SETUP),
    md(TARGET_MD),
    code('''\
TARGET = "emu"        # "local", "emu" or "qpu"
SHOTS = 500
OMEGA = 2 * np.pi * 1.0   # Rabi frequency, rad/µs (1 MHz)

TRAPS = [9, 18, 56, 59, 8]        # A = (9, 18) at 5 µm, B = (56, 59) at 10 µm, C = 8
reg = layout_register(TRAPS)
pos = trap_positions()
print("A spacing %.1f µm, U = %.1f rad/µs" % (np.linalg.norm(pos[9] - pos[18]), interaction(5.0)))
print("B spacing %.1f µm, U = %.2f rad/µs" % (np.linalg.norm(pos[56] - pos[59]), interaction(10.0)))
print("blockade radius at this Ω: %.1f µm" % blockade_radius(OMEGA))
reg.draw(blockade_radius=blockade_radius(OMEGA), draw_half_radius=True)'''),
    code('''\
DURATIONS = [16, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200]   # ns
seqs = [resonant_pulse(reg, t, OMEGA) for t in DURATIONS]
for s in seqs:
    check_for_qpu(s)          # raises if FRESNEL_CAN1 would reject it
print(len(seqs), "sequences pass the FRESNEL_CAN1 check")'''),
    code('''\
counts = run_many(seqs, target=TARGET, shots=SHOTS)
exact = run_many(seqs, target="local", shots=2000)   # noiseless reference, free'''),
    code('''\
def summary(c):
    p = densities(c)
    return {"A_any": prob(c, lambda b: "1" in b[0:2]), "A_both": prob(c, lambda b: b[0:2] == "11"),
            "B_both": prob(c, lambda b: b[2:4] == "11"), "B_each": p[2:4].mean(), "C": p[4]}
S, X = [summary(c) for c in counts], [summary(c) for c in exact]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
for key, lab, col in [("C", "single atom C", "C2"), ("A_any", "pair A: one excitation", "C0"),
                      ("A_both", "pair A: both excited", "C3")]:
    ax[0].plot(DURATIONS, [x[key] for x in X], "-", color=col, alpha=.5)
    ax[0].plot(DURATIONS, [s[key] for s in S], "o", color=col, label=lab)
ax[0].set(title="5 µm: blockaded", xlabel="pulse length (ns)", ylabel="probability")
for key, lab, col in [("B_each", "pair B: each atom", "C1"), ("B_both", "pair B: both excited", "C4")]:
    ax[1].plot(DURATIONS, [x[key] for x in X], "-", color=col, alpha=.5)
    ax[1].plot(DURATIONS, [s[key] for s in S], "o", color=col, label=lab)
ax[1].set(title="10 µm: independent", xlabel="pulse length (ns)")
for a in ax: a.legend(fontsize=8); a.grid(alpha=.3)
plt.tight_layout()'''),
    md('''\
**What to see.** The single atom flops with period 2π/Ω = 1000 ns. Pair A never has both
atoms excited, and its one shared excitation oscillates √2 times faster (period ≈ 707 ns):
the pair is in the entangled state (|gr⟩ + |rg⟩)/√2. Pair B behaves like two copies of
atom C: P(both) = P(one)². Dots are the cloud emulator; faint lines are the exact local
simulation.'''),
    code('''\
fit = lambda key: float(np.mean([abs(s[key] - x[key]) for s, x in zip(S, X)]))
result = {"chapter": 1, "traps": TRAPS, "omega": OMEGA, "durations": DURATIONS, "target": TARGET,
          "shots": SHOTS, "emu": S, "exact": X,
          "max_A_both": max(s["A_both"] for s in S),
          "mean_abs_dev": {k: fit(k) for k in S[0]}}
(ROOT / "results").mkdir(exist_ok=True)
json.dump(result, open(ROOT / "results" / "01_blockade.json", "w"), indent=1)
print("largest P(A both excited):", result["max_A_both"])
print("mean |emulator - exact|:", {k: round(v, 3) for k, v in result["mean_abs_dev"].items()})'''),
    md(QPU_MD),
    code('''\
CONFIRM_QPU = False
QPU_DURATIONS, QPU_SHOTS = [350, 700], 50     # half and full collective period: enough to see blockade
print(qpu_estimate(QPU_SHOTS, n_jobs=len(QPU_DURATIONS)))
if CONFIRM_QPU:
    jobs = [submit(resonant_pulse(reg, t, OMEGA), "qpu", QPU_SHOTS, confirm_qpu=True)
            for t in QPU_DURATIONS]
    print("QPU job IDs:", *[j.id for j in jobs], sep="\\n  ")
    # later: qpu_counts = wait(jobs, timeout=7 * 24 * 3600)'''),
])

# ------------------------------------------------------------- 02 AF chain
nb2 = notebook([
    md('''\
# 2 · Growing an antiferromagnet

**Sweep the laser, and order appears.** With the drive Ω on and the detuning Δ swept from
negative (Rydberg state costly) to positive (Rydberg state favoured), each atom wants to be
excited, but the blockade forbids neighbours. The compromise is a crystal: every other atom
excited, `1010101`. In spin language (Rydberg = ↑) this is a Néel antiferromagnet, the
Z₂-ordered phase first seen with 51 atoms by Bernien *et al.*, Nature 551, 579 (2017).

We use a straight chain of 7 atoms 5 µm apart on FRESNEL_CAN1's calibrated layout and sweep
to different final detunings, from the disordered side into the ordered phase.'''),
    code(SETUP),
    md(TARGET_MD),
    code('''\
TARGET = "emu"
SHOTS = 500
OMEGA = 2 * np.pi * 1.0          # rad/µs
DELTA_START = -2 * np.pi * 2.5   # rad/µs
TRAPS = [2, 10, 19, 28, 37, 46, 54]   # one row of the 60-trap layout, 5 µm apart
reg = layout_register(TRAPS)
reg.draw(blockade_radius=blockade_radius(OMEGA), draw_half_radius=True)
seq = adiabatic_sweep(reg, OMEGA, DELTA_START, 15.0)
seq.draw()'''),
    code('''\
DELTA_END = [-6, 0, 4, 8, 12, 16, 24]   # rad/µs
seqs = [adiabatic_sweep(reg, OMEGA, DELTA_START, d) for d in DELTA_END]
counts = run_many(seqs, target=TARGET, shots=SHOTS)
exact = run_many(seqs, target="local", shots=2000)'''),
    code('''\
N = len(TRAPS)
neel = "".join("1" if i % 2 == 0 else "0" for i in range(N))      # 1010101
def stag(c):
    """Staggered magnetization: +1 for 1010101, -1 for 0101010, 0 if disordered."""
    s = np.array([(-1) ** i for i in range(N)])
    tot = sum(c.values())
    return sum(v * np.mean(s * (2 * np.array([int(x) for x in b]) - 1)) for b, v in c.items()) / tot
S = [{"neel": prob(c, lambda b: b == neel), "stag": stag(c), "n": densities(c).tolist()} for c in counts]
X = [{"neel": prob(c, lambda b: b == neel), "stag": stag(c), "n": densities(c).tolist()} for c in exact]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
x = np.array(DELTA_END) / OMEGA
ax[0].plot(x, [e["neel"] for e in X], "-", alpha=.5, color="C0"); ax[0].plot(x, [s["neel"] for s in S], "o", color="C0", label="P(1010101)")
ax[0].plot(x, [e["stag"] for e in X], "-", alpha=.5, color="C1"); ax[0].plot(x, [s["stag"] for s in S], "s", color="C1", label="staggered magnetization")
ax[0].set(xlabel="final Δ / Ω", ylabel="order", title="disorder → Z₂ crystal"); ax[0].legend(); ax[0].grid(alpha=.3)
im = ax[1].imshow([s["n"] for s in S], aspect="auto", cmap="Blues", vmin=0, vmax=1,
                  extent=[-.5, N - .5, len(x) - .5, -.5])
ax[1].set_yticks(range(len(x)), [f"{v:.1f}" for v in x]); ax[1].set(xlabel="atom", ylabel="final Δ / Ω", title="Rydberg density per atom")
plt.colorbar(im, ax=ax[1]); plt.tight_layout()
print("most common outcomes at the largest Δ:", top(counts[-2], 4))'''),
    code('''\
result = {"chapter": 2, "traps": TRAPS, "omega": OMEGA, "delta_start": DELTA_START,
          "delta_end": DELTA_END, "target": TARGET, "shots": SHOTS, "emu": S, "exact": X,
          "snapshots": [b for b, _ in top(counts[-2], 6)]}
json.dump(result, open(ROOT / "results" / "02_af_chain.json", "w"), indent=1)
print({d: round(s["neel"], 2) for d, s in zip(DELTA_END, S)})'''),
    md('''\
**What to see.** At negative Δ nearly every shot is `0000000`. Past Δ ≈ Ω the Néel pattern
takes over, and from Δ/Ω ≈ 1.3 on most shots are the perfect crystal. The edges order best:
an end atom has only one neighbour blocking it. Remaining errors are mostly domain walls
(`1001001`), which grow at the largest Δ: the sweep covers more ground in the same time, so it
is less adiabatic. Try `adiabatic_sweep(..., duration=6000)`.'''),
    md(QPU_MD),
    code('''\
CONFIRM_QPU = False
QPU_SHOTS = 100
qpu_seq = adiabatic_sweep(reg, OMEGA, DELTA_START, 16)    # deep in the ordered phase
print(qpu_estimate(QPU_SHOTS))
if CONFIRM_QPU:
    job = submit(qpu_seq, "qpu", QPU_SHOTS, confirm_qpu=True)
    print("QPU job ID:", job.id)
    # later: qpu_counts = wait([job], timeout=7 * 24 * 3600)[0]; prob(qpu_counts, lambda b: b == neel)'''),
])

# ---------------------------------------------------------- 03 magnet of light
nb3 = notebook([
    md('''\
# 3 · A magnet made of light: the ⅓ plateau

**Frustration on a triangle.** Put the same rule on a triangular lattice and it can't be
satisfied: on every triangle at most one atom can be excited. The best the atoms can do is
excite **one of the three sublattices**, a √3×√3 crystal with exactly ⅓ of the atoms in the
Rydberg state. In spin language that is a **magnetization plateau at m = −⅓**: over a whole
range of "field" (detuning) the magnetization stops changing.

This is the physics of the triangular-lattice Ising antiferromagnet, the model behind the
rare-earth magnet **TmMgGaO₄**, whose ⅓ plateau has been studied with Pasqal's simulators.

We use a 3×4 rhombus of 12 atoms from FRESNEL_CAN1's calibrated layout. It was chosen so
that the largest blockade-respecting pattern has exactly 4 atoms, ⅓ of 12. Then we sweep to
a series of final detunings and watch the density lock at ⅓.'''),
    code(SETUP),
    md(TARGET_MD),
    code('''\
TARGET = "emu"
SHOTS = 500
OMEGA = 2 * np.pi * 1.0
DELTA_START = -2 * np.pi * 2.5
TRAPS = [1, 4, 7, 8, 12, 13, 16, 17, 21, 22, 26, 31]     # a 3x4 rhombus, 5 µm spacing
reg = layout_register(TRAPS)
E = unit_disk_edges(TRAPS)                              # nearest neighbours (blockaded)
k, crystals = max_independent_sets(len(TRAPS), E)
print(f"{len(TRAPS)} atoms, {len(E)} blockaded bonds, at most {k} excitations "
      f"(= {k / len(TRAPS):.3f}), {len(crystals)} perfect crystals")
print("nearest-neighbour U = %.0f rad/µs, next-nearest U = %.1f rad/µs" % (interaction(5), interaction(5 * 3 ** .5)))
reg.draw(blockade_radius=blockade_radius(OMEGA), draw_half_radius=True)'''),
    code('''\
DELTA_END = [-6, 0, 3, 6, 10, 16, 24, 40, 50, 60]      # rad/µs (|Δ| <= 62.8 on FRESNEL_CAN1)
seqs = [adiabatic_sweep(reg, OMEGA, DELTA_START, d, duration=5000) for d in DELTA_END]
counts = run_many(seqs, target=TARGET, shots=SHOTS)
exact = run_many(seqs, target="local", shots=2000)'''),
    code('''\
cset = set(crystals)
is_crystal = lambda b: tuple(i for i, x in enumerate(b) if x == "1") in cset
S = [{"n": float(densities(c).mean()), "m": magnetization(c), "crystal": prob(c, is_crystal),
      "n_i": densities(c).round(4).tolist()} for c in counts]
X = [{"n": float(densities(c).mean()), "m": magnetization(c), "crystal": prob(c, is_crystal)} for c in exact]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
ax[0].axhline(-1 / 3, ls="--", color="gray", lw=1); ax[0].text(25, -0.30, "m = −⅓ plateau", color="gray")
ax[0].plot(DELTA_END, [x["m"] for x in X], "-", alpha=.5, color="C0")
ax[0].plot(DELTA_END, [s["m"] for s in S], "o", color="C0")
ax[0].set(xlabel="final detuning Δ (rad/µs)  ≈ field", ylabel="magnetization m = ⟨2n−1⟩", title="magnetization curve")
ax[1].plot(DELTA_END, [x["crystal"] for x in X], "-", alpha=.5, color="C2")
ax[1].plot(DELTA_END, [s["crystal"] for s in S], "o", color="C2")
ax[1].axvline(interaction(5), ls=":", color="gray"); ax[1].text(interaction(5) - 2, .5, "U(5 µm)", rotation=90, color="gray")
ax[1].set(xlabel="final detuning Δ (rad/µs)", ylabel="P(perfect ⅓ crystal)", title="order parameter")
for a in ax: a.grid(alpha=.3)
plt.tight_layout()'''),
    md('''\
**What to see.** The magnetization climbs from −1 and then **locks at −⅓** for
Δ ≈ 10–50 rad/µs, where nearly every shot is a perfect ⅓ crystal. The plateau ends when
Δ approaches the nearest-neighbour interaction U(5 µm) ≈ 55 rad/µs: it then pays to put two
neighbours in the Rydberg state, and the crystal melts towards the next plateau. Real
TmMgGaO₄ shows the mirror-image plateau at m = +⅓ in a magnetic field. It is the same model;
only the sign of the field differs.'''),
    code('''\
snap_i = DELTA_END.index(24)
result = {"chapter": 3, "traps": TRAPS, "edges": E, "mis": k, "n_crystals": len(crystals),
          "omega": OMEGA, "delta_start": DELTA_START, "delta_end": DELTA_END, "target": TARGET,
          "shots": SHOTS, "emu": S, "exact": X,
          "snapshots": [b for b, _ in top(counts[snap_i], 6)],
          "snapshots_melted": [b for b, _ in top(counts[-1], 4)]}
json.dump(result, open(ROOT / "results" / "03_magnet.json", "w"), indent=1)
print({d: round(s["crystal"], 2) for d, s in zip(DELTA_END, S)})'''),
    md('''\
### Going bigger

12 atoms is the free emulator's limit. The same model at **49 atoms** (7×7, on the 217-trap
layout) needs the tensor-network emulator `pasqal:pasqal:sim:emu-mps` (billed per minute),
or the QPU itself. A 49-atom magnetization sweep run this way through qBraid is shown on the
project page. Swap `TRAPS` for a 217-trap register (`layout_register(ids, n_traps=217)`;
layouts above 60 traps must be 35–55% filled) and change `EMULATOR`.'''),
    md(QPU_MD),
    code('''\
CONFIRM_QPU = False
QPU_SHOTS = 50
QPU_DELTAS = [24, 60]          # on the plateau, and past it
print(qpu_estimate(QPU_SHOTS, n_jobs=len(QPU_DELTAS)))
if CONFIRM_QPU:
    jobs = [submit(adiabatic_sweep(reg, OMEGA, DELTA_START, d, duration=5000), "qpu", QPU_SHOTS,
                   confirm_qpu=True) for d in QPU_DELTAS]
    print("QPU job IDs:", *[j.id for j in jobs], sep="\\n  ")'''),
])

# ------------------------------------------------------------------ 04 MIS
nb4 = notebook([
    md('''\
# 4 · Solving a graph problem with atoms

**The blockade is a constraint solver.** Place atoms on the vertices of a graph so that
blockaded pairs are exactly its edges (a *unit-disk graph*). Then "as many Rydberg atoms as
possible, no two neighbours both excited" is the **Maximum Independent Set** (MIS) problem.
It is NP-hard in general and turns up in scheduling, wireless network design and
portfolio selection. An adiabatic sweep prepares the ground state, which *is* the MIS;
see Ebadi *et al.*, Science 376, 1209 (2022).

Here a 12-vertex graph is cut from the calibrated layout. We compare sweep speeds, and we
are honest about the classical side: at this size a laptop solves it exactly in
milliseconds. What carries over to large graphs is the *method*, and whether it beats
classical heuristics at scale is an open research question.'''),
    code(SETUP),
    md(TARGET_MD),
    code('''\
TARGET = "emu"
SHOTS = 500
OMEGA = 2 * np.pi * 1.0
DELTA_START, DELTA_END = -2 * np.pi * 2.5, 2 * np.pi * 2.0
TRAPS = [15, 19, 20, 23, 24, 28, 32, 33, 37, 38, 42, 47]
reg = layout_register(TRAPS)
E = unit_disk_edges(TRAPS)
import time as _t
t0 = _t.perf_counter(); k, best = max_independent_sets(len(TRAPS), E); t_bf = _t.perf_counter() - t0
print(f"graph: {len(TRAPS)} vertices, {len(E)} edges | exact MIS size {k}, unique: {len(best) == 1} "
      f"| brute force took {t_bf * 1e3:.1f} ms")
reg.draw(blockade_radius=blockade_radius(OMEGA), draw_half_radius=True)'''),
    code('''\
DURATIONS = [800, 2000, 3500, 5000]      # ns: from a quench to a slow, adiabatic sweep
seqs = [adiabatic_sweep(reg, OMEGA, DELTA_START, DELTA_END, duration=T, rise=min(500, T // 4))
        for T in DURATIONS]
counts = run_many(seqs, target=TARGET, shots=SHOTS)
exact = run_many(seqs, target="local", shots=2000)'''),
    code('''\
mis_set = set(best)
as_set = lambda b: tuple(i for i, x in enumerate(b) if x == "1")
def score(c):
    indep = {b: v for b, v in c.items() if is_independent(b, E)}
    best_found = max((b.count("1") for b in indep), default=0)
    return {"p_mis": prob(c, lambda b: as_set(b) in mis_set),
            "p_independent": prob(c, lambda b: is_independent(b, E)),
            "mean_size": float(sum(b.count("1") * v for b, v in indep.items()) / max(1, sum(indep.values()))),
            "best_found": best_found}
S, X = [score(c) for c in counts], [score(c) for c in exact]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
ax[0].plot(DURATIONS, [x["p_mis"] for x in X], "-", alpha=.5, color="C0")
ax[0].plot(DURATIONS, [s["p_mis"] for s in S], "o", color="C0")
ax[0].set(xlabel="sweep duration (ns)", ylabel="P(exact MIS)", title="slower sweep, better answer")
c = counts[-1]
outcomes = top(c, 6)
ax[1].barh([f"{b}  ({b.count('1')})" for b, _ in outcomes][::-1], [v / SHOTS for _, v in outcomes][::-1],
           color=["C2" if as_set(b) in mis_set else "C7" for b, _ in outcomes][::-1])
ax[1].set(xlabel="probability", title="top outcomes, slowest sweep (green = MIS)")
for a in ax: a.grid(alpha=.3)
plt.tight_layout()
print([{k2: round(v, 3) for k2, v in s.items()} for s in S])'''),
    md('''\
**What to see.** A fast sweep (0.8 µs) leaves the atoms in a jumble of valid but small
independent sets: the blockade is never violated, but the answer is poor. Slowing to 5 µs
makes the exact MIS the most likely outcome. The runner-up is a valid 4-atom set, one atom
short. Hardware MIS studies post-process samples, for example with a greedy "fill the holes"
pass, which turns many near-misses into the optimum and takes one line to add.'''),
    code('''\
result = {"chapter": 4, "traps": TRAPS, "edges": E, "mis": k, "mis_sets": best, "omega": OMEGA,
          "delta_start": DELTA_START, "delta_end": DELTA_END, "durations": DURATIONS,
          "target": TARGET, "shots": SHOTS, "emu": S, "exact": X, "classical_ms": t_bf * 1e3,
          "top_slowest": outcomes}
json.dump(result, open(ROOT / "results" / "04_mis.json", "w"), indent=1)'''),
    md(QPU_MD),
    code('''\
CONFIRM_QPU = False
QPU_SHOTS = 100
print(qpu_estimate(QPU_SHOTS))
if CONFIRM_QPU:
    job = submit(seqs[-1], "qpu", QPU_SHOTS, confirm_qpu=True)
    print("QPU job ID:", job.id)
    # later: score(wait([job], timeout=7 * 24 * 3600)[0])'''),
])

for name, nb in [("01_rydberg_blockade", nb1), ("02_antiferromagnet", nb2),
                 ("03_magnet_made_of_light", nb3), ("04_max_independent_set", nb4)]:
    nbf.write(nb, NB / f"{name}.ipynb")
    print("wrote", name)
