"""Shared helpers for the notebooks: build Pulser sequences that Pasqal's FRESNEL_CAN1
accepts, run them on the free emulator, a local exact simulation, or the QPU through
qBraid, and analyse the bitstrings.

No Pasqal account or keys are needed. Device specs come from Pasqal's public endpoint,
and qBraid submits through its own Pasqal service account using your qBraid login.

    from pasqal_atoms import fresnel, layout_register, adiabatic_sweep, run
    reg = layout_register([2, 10, 19, 28, 37, 46, 54])
    seq = adiabatic_sweep(reg, omega=2 * np.pi, delta_start=-15.7, delta_end=15.0)
    counts = run(seq, target="emu", shots=500)       # free cloud emulator
"""

from __future__ import annotations

import functools
import itertools
import time
from collections.abc import Iterable, Sequence as Seq

import numpy as np
import requests
from pulser import Pulse, Register, Sequence
from pulser.devices import Device
from pulser.json.abstract_repr.deserializer import deserialize_device
from pulser.waveforms import ConstantWaveform, RampWaveform

PUBLIC_SPECS_URL = "https://apis.pasqal.cloud/core-fast/api/v1/devices/public-specs"

EMULATOR = "pasqal:pasqal:sim:emu-free"   # free, up to 12 atoms
QPU = "pasqal:pasqal:qpu:fresnel-can1"    # billed per minute of QPU time

# Observed on production, Nov 24 2026: 10 shots used 12 s of QPU time. Queue time is
# separate and is not billed. Treat the estimate below as a guide, not a quote.
SECONDS_PER_SHOT = 1.2


# --------------------------------------------------------------------------- device

@functools.lru_cache(maxsize=None)
def fresnel(name: str = "FRESNEL_CAN1", timeout: float = 30) -> Device:
    """Pasqal's live Pulser ``Device`` for the QPU: the specs Pasqal validates against."""
    data = requests.get(PUBLIC_SPECS_URL, timeout=timeout).json()["data"]
    for entry in data:
        if entry["device_type"] == name:
            return deserialize_device(entry["specs"])
    raise ValueError(f"{name} has no public specs; found {[e['device_type'] for e in data]}")


def layout(n_traps: int = 60):
    """One of FRESNEL_CAN1's calibrated layouts (60 or 217 traps, 5 µm triangular)."""
    for lay in fresnel().calibrated_register_layouts.values():
        if lay.number_of_traps == n_traps:
            return lay
    raise ValueError(f"No calibrated {n_traps}-trap layout on FRESNEL_CAN1")


def trap_positions(n_traps: int = 60) -> dict[int, np.ndarray]:
    """Trap id -> (x, y) in µm."""
    return {int(i): np.asarray(c, float) for i, c in layout(n_traps).traps_dict.items()}


def layout_register(trap_ids: Seq[int], n_traps: int = 60) -> Register:
    """A register on a calibrated layout. FRESNEL_CAN1 rejects free coordinates."""
    return layout(n_traps).define_register(
        *trap_ids, qubit_ids=[f"q{i}" for i in range(len(trap_ids))]
    )


def check_for_qpu(seq: Sequence) -> None:
    """Re-validate the sequence on FRESNEL_CAN1 the way Pasqal does.

    Raises the error Pasqal would return (layout, filling, distance, channel or
    duration rules) before anything is queued. The qBraid SDK (0.13.1+) runs the
    same check when you submit to the QPU.
    """
    dev = fresnel()
    if dev.requires_layout and seq.register.layout is None:
        raise ValueError("FRESNEL_CAN1 needs a register defined from a calibrated layout.")
    Sequence(seq.register, dev)
    if seq.device != dev:
        seq.switch_device(dev, strict=True)


# ------------------------------------------------------------------------- sequences

def _round(t: float) -> int:
    """Durations must be multiples of the 4 ns clock."""
    return int(4 * round(t / 4))


def resonant_pulse(reg: Register, duration: int, omega: float) -> Sequence:
    """A constant resonant drive of ``duration`` ns at Rabi frequency ``omega`` (rad/µs)."""
    seq = Sequence(reg, fresnel())
    seq.declare_channel("ryd", "rydberg_global")
    seq.add(Pulse.ConstantPulse(_round(duration), omega, 0.0, 0.0), "ryd")
    seq.measure("ground-rydberg")
    return seq


def adiabatic_sweep(reg: Register, omega: float, delta_start: float, delta_end: float,
                    duration: int = 4000, rise: int = 500) -> Sequence:
    """Ramp Ω up at negative detuning, sweep Δ across the transition, ramp Ω down.

    Starting with every atom in its ground state, a slow enough sweep follows the
    ground state of the Rydberg Hamiltonian into the ordered phase at ``delta_end``.
    Units: ``omega`` and detunings in rad/µs, durations in ns.
    """
    duration, rise = _round(duration), _round(rise)
    mid = duration - 2 * rise
    seq = Sequence(reg, fresnel())
    seq.declare_channel("ryd", "rydberg_global")
    seq.add(Pulse(RampWaveform(rise, 0.0, omega), ConstantWaveform(rise, delta_start), 0.0), "ryd")
    seq.add(Pulse(ConstantWaveform(mid, omega), RampWaveform(mid, delta_start, delta_end), 0.0), "ryd")
    seq.add(Pulse(RampWaveform(rise, omega, 0.0), ConstantWaveform(rise, delta_end), 0.0), "ryd")
    seq.measure("ground-rydberg")
    return seq


# ------------------------------------------------------------------------------ run

def qpu_estimate(shots: int, n_jobs: int = 1) -> dict:
    """Rough QPU cost from the device's per-minute price (credits; 1 credit = USD 0.01)."""
    from qbraid.runtime import QbraidProvider

    pricing = QbraidProvider().get_device(QPU).profile.pricing
    per_min = float(pricing["perMinute"] if isinstance(pricing, dict) else pricing.perMinute)
    seconds = SECONDS_PER_SHOT * shots * n_jobs
    credits = per_min * seconds / 60
    return {"credits_per_minute": per_min, "est_qpu_seconds": round(seconds, 1),
            "est_credits": round(credits, 1), "est_usd": round(credits / 100, 2)}


def submit(seq: Sequence, target: str = "emu", shots: int = 500, confirm_qpu: bool = False):
    """Submit one sequence through qBraid and return the job (does not wait).

    target: "emu" (free cloud emulator, <= 12 atoms) or "qpu" (FRESNEL_CAN1, billed).
    """
    from qbraid.runtime import QbraidProvider

    check_for_qpu(seq)  # the same sequence must be valid on the QPU, even for emulator runs
    if target == "qpu":
        if not confirm_qpu:
            est = qpu_estimate(shots)
            raise RuntimeError(
                f"QPU run not confirmed. Estimated {est['est_credits']:,} credits "
                f"(~${est['est_usd']}) for {shots} shots, plus queue time. "
                "Pass confirm_qpu=True to submit."
            )
        device_id = QPU
    elif target == "emu":
        device_id = EMULATOR
    else:
        raise ValueError("target must be 'emu' or 'qpu' (use simulate() for local runs)")
    return QbraidProvider().get_device(device_id).run(seq, shots=shots)


def wait(jobs, poll: float = 10, timeout: float = 1800) -> list[dict[str, int]]:
    """Wait for jobs and return their counts in order. QPU jobs can queue for days:
    keep the job IDs and come back later rather than waiting here."""
    jobs = list(jobs)
    t0 = time.time()
    while True:
        states = [str(j.status()).split(".")[-1] for j in jobs]
        if all(s in {"COMPLETED", "FAILED", "CANCELLED"} for s in states):
            break
        if time.time() - t0 > timeout:
            raise TimeoutError(f"Still waiting: {states}. Job IDs: {[j.id for j in jobs]}")
        time.sleep(poll)
    out = []
    for j, s in zip(jobs, states):
        if s != "COMPLETED":
            raise RuntimeError(f"Job {j.id} ended {s}")
        out.append(dict(j.result().data.get_counts()))
    return out


def run(seq: Sequence, target: str = "emu", shots: int = 500, confirm_qpu: bool = False):
    """Run one sequence and return bitstring counts.

    target: "local" (exact simulation on this machine, free), "emu" (Pasqal's free
    cloud emulator through qBraid) or "qpu" (FRESNEL_CAN1 through qBraid, billed).
    """
    if target == "local":
        return simulate(seq, shots)
    return wait([submit(seq, target, shots, confirm_qpu)])[0]


def run_many(seqs: Iterable[Sequence], target: str = "emu", shots: int = 500,
             confirm_qpu: bool = False) -> list[dict[str, int]]:
    """Submit several sequences at once (one job each), then collect them."""
    seqs = list(seqs)
    if target == "local":
        return [simulate(s, shots) for s in seqs]
    if target == "qpu" and not confirm_qpu:
        est = qpu_estimate(shots, n_jobs=len(seqs))
        raise RuntimeError(
            f"QPU run not confirmed. Estimated {est['est_credits']:,} credits "
            f"(~${est['est_usd']}) for {len(seqs)} jobs x {shots} shots, plus queue time. "
            "Pass confirm_qpu=True to submit."
        )
    jobs = [submit(s, target, shots, confirm_qpu) for s in seqs]
    print("submitted:", *[j.id for j in jobs], sep="\n  ")
    return wait(jobs)


def simulate(seq: Sequence, shots: int = 500, seed: int | None = 7) -> dict[str, int]:
    """Exact noiseless simulation with pulser-simulation (fine up to ~12 atoms)."""
    import warnings

    from pulser_simulation import QutipEmulator

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # at least ~50 time samples, so short pulses are resolved too
        rate = min(1.0, max(0.05, 50 / max(1, seq.get_duration())))
        res = QutipEmulator.from_sequence(seq, sampling_rate=rate).run()
    if seed is not None:
        np.random.seed(seed)
    return dict(res.sample_final_state(shots))


# ------------------------------------------------------------------------- analysis

def densities(counts: dict[str, int]) -> np.ndarray:
    """Probability each atom ends in the Rydberg state (bit '1')."""
    tot = sum(counts.values())
    n = len(next(iter(counts)))
    return np.array([sum(v for b, v in counts.items() if b[i] == "1") for i in range(n)]) / tot


def magnetization(counts: dict[str, int]) -> float:
    """Mean spin m = <2n-1>, with Rydberg = spin up. Ranges from -1 (none) to +1 (all)."""
    return float(2 * densities(counts).mean() - 1)


def prob(counts: dict[str, int], predicate) -> float:
    tot = sum(counts.values())
    return sum(v for b, v in counts.items() if predicate(b)) / tot


def top(counts: dict[str, int], k: int = 5) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: -kv[1])[:k]


def unit_disk_edges(trap_ids: Seq[int], radius: float = 5.5, n_traps: int = 60):
    """Edges between register atoms closer than ``radius`` µm (indices into trap_ids)."""
    pos = trap_positions(n_traps)
    return [(a, b) for a, b in itertools.combinations(range(len(trap_ids)), 2)
            if np.linalg.norm(pos[trap_ids[a]] - pos[trap_ids[b]]) < radius]


def is_independent(bits: str, edges) -> bool:
    return all(not (bits[a] == "1" and bits[b] == "1") for a, b in edges)


def max_independent_sets(n: int, edges) -> tuple[int, list[tuple[int, ...]]]:
    """Brute force: the MIS size and every MIS (fine for n <= ~20)."""
    adj = [set() for _ in range(n)]
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    for k in range(n, 0, -1):
        sets = [c for c in itertools.combinations(range(n), k)
                if all(b not in adj[a] for a, b in itertools.combinations(c, 2))]
        if sets:
            return k, sets
    return 0, []


def interaction(r_um: float) -> float:
    """Van der Waals interaction C6/r^6 between two Rydberg atoms, in rad/µs."""
    return fresnel().interaction_coeff / r_um ** 6


def blockade_radius(omega: float) -> float:
    """Distance (µm) at which the interaction equals ``omega`` (rad/µs)."""
    return fresnel().rydberg_blockade_radius(omega)


__all__ = [n for n in dir() if not n.startswith("_") and n not in {
    "annotations", "functools", "itertools", "time", "np", "requests",
    "Iterable", "Seq", "Pulse", "Register", "Sequence", "Device", "deserialize_device",
    "ConstantWaveform", "RampWaveform"}]
