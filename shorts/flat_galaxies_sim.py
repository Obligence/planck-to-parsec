#!/usr/bin/env python3
"""A small, genuine N-body simulation of why galaxies are flat. Used by shorts/flat_galaxies.py.

Two kinds of particle, "gas" and "dark matter", start mixed in one slowly rotating cloud that is too cold to hold
itself up, so it collapses. Both feel exactly the same gravity. The only difference between them:

  * gas is dissipative: every step, gas particles that share a small cell are nudged toward that cell's mean
    velocity (a crude model of collisions that turn random motion into heat, which is radiated away). This keeps
    the momentum of every cell, so the total momentum is conserved and the spin is very nearly conserved.
  * dark matter gets no such step. It only feels gravity.

Gravity is self-consistent: a particle-mesh solver (cloud-in-cell mass assignment, FFT convolution with the
softened 1/r kernel on a zero-padded grid, so the cloud is isolated and not periodic), leapfrog time stepping.
Units: G = 1, total mass = 1, initial cloud radius = 2.

Nothing about the outcome is drawn by hand. `python3 flat_galaxies_sim.py` runs it, prints the measured shapes
over time and writes the cache that the scene script loads. Research simulations use billions of particles and
add star formation, pressure, cooling physics and feedback; this is the simplest model that keeps the argument.
"""
import os, sys, time
import numpy as np
from scipy import fft as sfft

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(HERE), "build", "flat_galaxies", "sim_v1.npz")

N_GAS, N_DM = 24000, 24000
F_GAS = 0.12                 # gas share of the mass; dark matter is the other 88%
R0 = 2.0                     # initial cloud radius
VIRIAL = 0.35                # random kinetic energy as a fraction of what would hold the cloud up (sub-virial)
SPIN = 0.6                  # solid-body rotation rate, in units of the circular rate at the cloud's edge
NG, BOX = 96, 7.0            # mesh cells per side and box size (cell = BOX / NG)
SOFT = 0.07                  # gravitational softening length
DT, T_END, SNAP = 0.008, 26.0, 0.08
GAS_CELL, GAS_TAU = 0.08, 0.4    # collision cell size and relaxation time of the gas
GAS_FLOOR = 0.17                 # the gas stays slightly warm: random speeds below this are not damped
SEED = 3


def greens():
    """FFT of the softened -1/r kernel on the doubled (zero-padded) grid."""
    n2 = 2 * NG; h = BOX / NG
    k = np.arange(n2); k = np.minimum(k, n2 - k) * h
    r2 = k[:, None, None] ** 2 + k[None, :, None] ** 2 + k[None, None, :] ** 2
    g = -1.0 / np.sqrt(r2 + SOFT ** 2)
    return sfft.rfftn(g.astype(np.float32), workers=2)


def cic_weights(pos):
    h = BOX / NG
    u = (pos + BOX / 2) / h - 0.5
    i0 = np.floor(u).astype(np.int64); f = (u - i0).astype(np.float32)
    ok = np.all((i0 >= 0) & (i0 < NG - 1), axis=1)
    return i0, f, ok


def accel(pos, mass, GK):
    """Self-gravity of all particles on the mesh. Particles that leave the box feel the cloud as a point mass."""
    h = BOX / NG; n2 = 2 * NG
    i0, f, ok = cic_weights(pos)
    cells = np.zeros(NG ** 3, np.float64)
    ii, ff, mm = i0[ok], f[ok], mass[ok]
    for dx in (0, 1):
        wx = ff[:, 0] if dx else 1 - ff[:, 0]
        for dy in (0, 1):
            wy = ff[:, 1] if dy else 1 - ff[:, 1]
            for dz in (0, 1):
                wz = ff[:, 2] if dz else 1 - ff[:, 2]
                flat = ((ii[:, 0] + dx) * NG + ii[:, 1] + dy) * NG + ii[:, 2] + dz
                cells += np.bincount(flat, mm * wx * wy * wz, NG ** 3)
    rho = np.zeros((n2, n2, n2), np.float32)
    rho[:NG, :NG, :NG] = cells.reshape(NG, NG, NG)
    phi = sfft.irfftn(sfft.rfftn(rho, workers=2) * GK, s=(n2, n2, n2), workers=2)[:NG, :NG, :NG]
    gx, gy, gz = np.gradient(-phi, h)
    acc = np.empty_like(pos)
    for c, g in enumerate((gx, gy, gz)):
        a = np.zeros(len(ii), np.float32)
        for dx in (0, 1):
            wx = ff[:, 0] if dx else 1 - ff[:, 0]
            for dy in (0, 1):
                wy = ff[:, 1] if dy else 1 - ff[:, 1]
                for dz in (0, 1):
                    wz = ff[:, 2] if dz else 1 - ff[:, 2]
                    a += g[ii[:, 0] + dx, ii[:, 1] + dy, ii[:, 2] + dz] * wx * wy * wz
        acc[ok, c] = a
    out = ~ok
    if out.any():
        com = (pos[ok] * mass[ok, None]).sum(0) / mass[ok].sum()
        d = pos[out] - com; r = np.sqrt((d ** 2).sum(1) + SOFT ** 2)
        acc[out] = -mass[ok].sum() * d / r[:, None] ** 3
    return acc


def collide(pos, vel, dt):
    """The gas-only step: relax each gas particle toward the mean velocity of its cell (momentum conserving)."""
    c = np.floor(pos / GAS_CELL).astype(np.int64) + 512
    key = (c[:, 0] * 1024 + c[:, 1]) * 1024 + c[:, 2]
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    mean = np.stack([np.bincount(inv, vel[:, k], len(uniq)) for k in range(3)], 1) / cnt[:, None]
    dv = vel - mean[inv]
    sp = np.sqrt((dv ** 2).sum(1)) + 1e-12
    keep = np.maximum(np.exp(-dt / GAS_TAU), np.minimum(1.0, GAS_FLOOR / sp))   # random speeds below the floor are left alone
    vel[:] = mean[inv] + dv * keep[:, None]


def shape(pos):
    """Flatness of one species: 1 = round ball, 0 = perfectly flat. Uses the inner 80% of the particles and
    compares the spread along the spin axis (z) with the spread in the plane."""
    p = pos - np.median(pos, axis=0)
    r = np.sqrt((p ** 2).sum(1)); p = p[r < np.quantile(r, 0.8)]
    return float(np.sqrt(2 * (p[:, 2] ** 2).mean() / ((p[:, 0] ** 2).mean() + (p[:, 1] ** 2).mean())))


def run(verbose=True):
    rng = np.random.default_rng(SEED)
    n = N_GAS + N_DM
    d = rng.normal(size=(n, 3)); d /= np.linalg.norm(d, axis=1)[:, None]
    pos = d * (R0 * rng.uniform(size=n) ** (1 / 3))[:, None]            # uniform ball, both species mixed
    mass = np.empty(n); mass[:N_GAS] = F_GAS / N_GAS; mass[N_GAS:] = (1 - F_GAS) / N_DM
    sig = np.sqrt(VIRIAL * 0.2 / R0)                                    # 3 sig^2 = VIRIAL * (3/5) GM/R
    vel = rng.normal(size=(n, 3)) * sig
    w = SPIN * np.sqrt(1.0 / R0 ** 3)                                   # same spin for both species
    vel[:, 0] += -w * pos[:, 1]; vel[:, 1] += w * pos[:, 0]
    vel -= (vel * mass[:, None]).sum(0); pos -= (pos * mass[:, None]).sum(0)
    GK = greens()
    gas = slice(0, N_GAS); dm = slice(N_GAS, n)

    def lz(s):
        return float((mass[s] * (pos[s, 0] * vel[s, 1] - pos[s, 1] * vel[s, 0])).sum())

    lz0 = lz(slice(0, n)); lg0 = lz(gas)
    steps = int(round(T_END / DT)); every = int(round(SNAP / DT))
    P, V, TT, QG, QD = [], [], [], [], []
    acc = accel(pos, mass, GK); t0 = time.time()
    for i in range(steps + 1):
        if i % every == 0:
            P.append(pos.astype(np.float32)); V.append(vel.astype(np.float32)); TT.append(i * DT)
            QG.append(shape(pos[gas])); QD.append(shape(pos[dm]))
            if verbose and (i // every) % 25 == 0:
                print(f"t={i * DT:5.1f}  gas flatness {QG[-1]:.2f}  dark matter {QD[-1]:.2f}  "
                      f"Lz total {lz(slice(0, n)) / lz0:.3f}  Lz gas {lz(gas) / lg0:.3f}  ({time.time() - t0:.0f}s)", flush=True)
        vel += 0.5 * DT * acc
        pos += DT * vel
        acc = accel(pos, mass, GK)
        vel += 0.5 * DT * acc
        collide(pos[gas], vel[gas], DT)        # views: updates the gas velocities in place
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + f".{os.getpid()}.tmp.npz"
    np.savez(tmp, pos=np.array(P), vel=np.array(V).astype(np.float16), t=np.array(TT), qg=np.array(QG), qd=np.array(QD),
             n_gas=N_GAS, lz_total=lz(slice(0, n)) / lz0, lz_gas=lz(gas) / lg0)
    os.replace(tmp, CACHE)
    return CACHE


def load():
    if not os.path.exists(CACHE):
        print("flat_galaxies: running the simulation once (a few minutes)...", flush=True)
        run(verbose=False)
    return np.load(CACHE)


if __name__ == "__main__":
    run()
    z = np.load(CACHE)
    print("saved", CACHE, z["pos"].shape, "final flatness: gas %.2f, dark matter %.2f" % (z["qg"][-1], z["qd"][-1]))
