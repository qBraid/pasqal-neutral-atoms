<a href="https://account.qbraid.com?install-project=pasqal-neutral-atoms"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/qBraid/pasqal-neutral-atoms/main/assets/launch-on-qbraid-dark.svg"><img src="https://raw.githubusercontent.com/qBraid/pasqal-neutral-atoms/main/assets/launch-on-qbraid-light.svg" alt="Launch on qBraid" height="30"></picture></a>

# Neutral Atoms on qBraid: blockade, magnets and graphs with Pasqal

Four short, runnable notebooks that program **Pasqal's neutral-atom quantum computer** with
[Pulser](https://github.com/pasqal-io/Pulser) through [qBraid](https://www.qbraid.com). Each
one runs for free on Pasqal's cloud emulator, and the exact same sequences run unchanged on
the **FRESNEL_CAN1** QPU.

| # | Notebook | What you'll see | Atoms |
|---|---|---|---|
| 1 | [`01_rydberg_blockade`](notebooks/01_rydberg_blockade.ipynb) | Two atoms that can share one excitation but never two; √2-faster collective Rabi oscillations | 5 |
| 2 | [`02_antiferromagnet`](notebooks/02_antiferromagnet.ipynb) | Sweeping the laser grows a `1010101` Néel crystal out of nothing | 7 |
| 3 | [`03_magnet_made_of_light`](notebooks/03_magnet_made_of_light.ipynb) | A frustrated triangular magnet locks into the m = −⅓ magnetization plateau (the TmMgGaO₄ model) | 12 |
| 4 | [`04_max_independent_set`](notebooks/04_max_independent_set.ipynb) | The blockade as a constraint solver for Maximum Independent Set, with an honest classical comparison | 12 |

Every notebook already contains its outputs from a real run on Pasqal's emulator, so you
can read the results before running anything.

## Run it on qBraid

**As a qBraid project (recommended).** Click **Launch on qBraid** above, or in qBraid Lab open
**Explore → Projects**, find *Neutral Atoms on qBraid*, and choose **Install** (or **Start with an
agent**). That copies
this repository to `~/projects/`, installs the **Pasqal (Pulser)** environment with its
notebook kernel, and adds the `pasqal-on-qbraid` agent skill. From a terminal:

```bash
qbraid projects get pasqal-neutral-atoms --setup --inspect-repository --json   # review what it installs
qbraid projects install pasqal-neutral-atoms --reviewed-revision <revision>
```

**By hand.**

```bash
git clone https://github.com/qBraid/pasqal-neutral-atoms.git
qbraid envs install pasqal_js2dr3            # "Pasqal (Pulser)": qBraid SDK, pulser-core, pulser-simulation
qbraid skills install pasqal_wk1xlv --target all   # optional: teaches coding agents the Pasqal rules
```

Then open a notebook and pick the kernel **Python 3 [Pasqal]** (Python 3.12). Each notebook's
first cell checks the kernel and tells you if it's the wrong one. You only need a qBraid
account: qBraid submits to Pasqal Cloud with its own service account, so you don't need
Pasqal credentials.

## Emulator first, then the QPU

Each notebook has one switch:

```python
TARGET = "emu"     # "local": exact simulation here, free
                   # "emu":   Pasqal EMU_FREE through qBraid, free, up to 12 atoms
                   # "qpu":   Pasqal FRESNEL_CAN1 through qBraid, billed per QPU minute
```

and ends with a **Run it on the QPU** cell that prints a cost estimate and submits only
when you set `CONFIRM_QPU = True`. Things to know before using the QPU:

- **Price.** `qbraid devices get pasqal:pasqal:qpu:fresnel-can1` shows it (credits per minute;
  1 credit = USD 0.01). One measured run: 10 shots used 12 s of QPU time, so
  `qpu_estimate()` assumes ~1.2 s per shot. Treat it as a guide, not a quote.
- **Queue.** QPU jobs wait in Pasqal's queue for hours to days. The cell prints job IDs and
  returns at once; check later with `qbraid jobs get <id>` or the Lab's **Quantum Jobs** panel.
- **Rejected sequences are free.** Every sequence here is built on FRESNEL_CAN1's live device
  specs and a calibrated register layout, and `check_for_qpu()` re-validates it the way
  Pasqal does. The qBraid SDK (0.13.1+) runs the same check on submit and raises
  `TransformError` with the fix. Fix the sequence rather than turning the check off.
- **Access.** Pasqal devices on qBraid are in early access. If `get_device` says the device
  isn't found, ask for access; it isn't a bug in your code.

## What's in the repository

```
pasqal_atoms.py        helpers: live FRESNEL_CAN1 device, calibrated registers, sweeps,
                       run on local / emu / qpu, cost estimate, analysis (MIS, magnetization)
notebooks/             the four chapters, with outputs from an emulator run
results/               the numbers each notebook produced (JSON), used by the project page
tools/build_notebooks.py   regenerates the notebooks from one source
```

`pasqal_atoms.py` needs only `pulser-core`, `pulser-simulation`, `requests` and the qBraid
SDK, all in the **Pasqal (Pulser)** environment.

## Honest notes

- These are textbook demonstrations at small sizes. The 12-atom problems are easy for a
  laptop: the MIS notebook times the brute-force solution next to the quantum one. They
  show *how* to program the hardware, not a quantum advantage.
- The emulator is noiseless. Real QPU shots include preparation and detection errors of a few
  percent per atom and imperfect sweeps, so expect lower crystal probabilities on hardware.
- The ⅓-plateau model is the triangular-lattice Ising antiferromagnet behind TmMgGaO₄. A
  12-atom cluster shows the plateau but not the thermodynamic phase transition.

## References

- H. Bernien *et al.*, *Probing many-body dynamics on a 51-atom quantum simulator*, Nature 551, 579 (2017)
- S. Ebadi *et al.*, *Quantum optimization of maximum independent set using Rydberg atom arrays*, Science 376, 1209 (2022)
- H. Li *et al.*, *Kosterlitz-Thouless melting of magnetic order in the triangular quantum Ising material TmMgGaO₄*, Nat. Commun. 11, 1111 (2020)
- Pulser documentation: <https://pulser.readthedocs.io>; Pasqal Cloud: <https://docs.pasqal.com/cloud/>

Licensed under the Apache License 2.0.
