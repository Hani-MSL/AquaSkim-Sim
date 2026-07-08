# Phase 06 — Model Derivation

## Kinematics

\[
\dot{x}=u\cos\psi-v\sin\psi,
\qquad
\dot{y}=u\sin\psi+v\cos\psi,
\qquad
\dot{\psi}=r
\]

## Planar dynamics

\[
m_u(\dot{u}-vr)=T_P+T_S+X_D
\]

\[
m_v(\dot{v}+ur)=Y_D
\]

\[
I_z\dot{r}=\frac{b}{2}(T_S-T_P)+N_D
\]

where `P` and `S` denote port and starboard. Added mass is represented through effective surge and sway masses plus an effective yaw inertia.

## Current-relative drag

For earth-fixed current vector \(V_c^n\), body-frame current is:

\[
V_c^b=R(\psi)^T V_c^n
\]

and relative water velocity is:

\[
\nu_r = [u,v]^T-V_c^b.
\]

The Phase 04 total resistance at \(|\nu_r|\) is projected onto the body-x direction. Explicit linear-plus-quadratic damping is used for sway and yaw.

## Integration

The state is stepped with fourth-order Runge–Kutta using the configured `0.05 s` interval. Output samples are decimated to `0.10 s` for compact reproducible CSV artifacts.
