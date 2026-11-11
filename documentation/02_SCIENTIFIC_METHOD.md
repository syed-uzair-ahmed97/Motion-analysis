# Scientific method

## Spatial sea-state methods

- **Zone:** include every source-grid cell whose centre lies inside the selected bounds. Every valid selected Hs–Tp observation contributes equally to the occurrence matrix, which is then normalized to 100%. No latitude multiplier is applied.
- **Location:** select one nearest ERA5 grid cell by great-circle distance and use its time history without spatial averaging. Results record requested coordinates, matched coordinates, and offset.
- **Route:** sample the generated maritime line, snap samples to ERA5 cells, collapse repeated matches, and weight cell histories by along-route coverage. The route may contain one optional stopover. The route is for analysis visualization, not navigation.

These weights answer different questions and must not be interchanged.

## 1. Sea-state occurrence matrix

For every paired observation `(Hs_i, Tp_i)`:

1. Reject non-finite values.
2. Reject `Hs < 0` and `Tp <= 0`.
3. Apply time and geographical filters, if supplied.
4. Place the sample into half-open bins `[lower, upper)`, with the final edge inclusive.

For cell `(j, k)`:

```text
count[j,k] = number of observations in Hs bin j and Tp bin k
probability[j,k] = 100 * count[j,k] / Nvalid
```

The sum of all probability cells must equal 100% within numerical tolerance.

The selected sea state retains:

- Lower and upper `Hs` bounds.
- Lower and upper `Tp` bounds.
- Observation count.
- Probability.
- Midpoint `Hs` and `Tp`, used only as editable defaults downstream.

## 2. PM and JONSWAP spectrum

The supplied MATLAB reference defines peak angular frequency:

```text
omega_p = 2*pi/Tp
```

Pierson–Moskowitz spectrum:

```text
S_PM(omega) = (5/16) Hs^2 omega_p^4 omega^-5
              exp[-(5/4)(omega/omega_p)^-4]
```

JONSWAP peak shape:

```text
sigma = 0.07, omega <= omega_p
sigma = 0.09, omega > omega_p
r = exp[-0.5 ((omega - omega_p)/(sigma omega_p))^2]
A_gamma = 0.2 / (0.065 gamma^0.803 + 0.135)
S_J(omega) = A_gamma S_PM(omega) gamma^r
```

Reported validation quantities:

```text
m0 = integral S_J(omega) d omega
Hm0 = 4 sqrt(m0)
```

## 3. RAO source

The Capytaine `rao.csv` fields used are:

- `omega` in rad/s.
- `wave_direction` in radians.
- `radiating_dof`.
- `real` and `imag` complex components.
- `period` in seconds.

For each requested heading, the nearest solved circular heading is selected and reported. Real and imaginary components are interpolated separately over frequency.

Translational RAOs are interpreted as `m/m`; rotational RAOs are interpreted as `rad/m`.

## 4. Encounter frequency

With vessel speed `U`, gravitational acceleration `g`, and relative wave heading `beta`:

```text
k = omega^2/g                         (deep water)
omega_e = omega - k U cos(beta)
```

The response integration remains on monotonically increasing absolute wave frequency `omega`; `abs(omega_e)` is used for response time derivatives.

## 5. DOF response spectra

For a complex displacement RAO `H_q(omega)`:

```text
S_q(omega) = |H_q(omega)|^2 S_eta(omega)
S_qdd(omega) = |omega_e|^4 |H_q(omega)|^2 S_eta(omega)
q_RMS = sqrt(integral S_q d omega)
qdd_RMS = sqrt(integral S_qdd d omega)
```

## 6. Point acceleration

Let evaluation point `r = (x, y, z)` be relative to the centre of gravity. Let the six complex RAOs be `(X, Y, Z, Phi, Theta, Psi)`.

Using the supplied small-angle rigid-body convention:

```text
H_ax = -omega_e^2 (X + z Theta - y Psi) - g Theta
H_ay = -omega_e^2 (Y + x Psi - z Phi)   + g Phi
H_az = -omega_e^2 (Z - x Theta + y Phi)
```

Then:

```text
S_ax = |H_ax|^2 S_eta
S_ay = |H_ay|^2 S_eta
S_az = |H_az|^2 S_eta
```

This formulation preserves RAO phase and all cross terms.

## 7. RMS, spectral period, and expected maximum

For each point-acceleration spectrum:

```text
m0 = integral S_a d omega
m2 = integral omega_e^2 S_a d omega
a_RMS = sqrt(m0)
Tz = 2*pi sqrt(m0/m2)
N = exposure_seconds/Tz
factor = sqrt(2 ln(N/alpha))
a_expected_max = factor * a_RMS
```

`alpha` is entered as a probability fraction by the API and displayed as percent in the UI. For example, 1% is sent as `0.01`.

The maximum is a narrow-band statistical estimate, not a deterministic design acceleration. The UI must label it as an expected maximum for the configured exposure and exceedance probability.

## 8. Known boundaries

- Linear potential-flow RAOs and linear superposition are assumed.
- The sea state is stationary and represented by one spectrum.
- Directional spreading is not included in version one.
- Forward-speed effects modify encounter frequency but do not recompute forward-speed hydrodynamic coefficients.
- Structural flexibility, slamming, green water, nonlinear roll damping outside the configured hydrodynamic model, and transient events are excluded.
- A point coordinate must use the same axes and origin as the mesh/RAO model: `x` forward, `y` port, `z` upward, relative to the centre of gravity.
