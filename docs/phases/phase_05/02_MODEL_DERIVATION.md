# Phase 05 model derivation

## 1. Usable pack energy

\[
E_{usable}=E_{nominal}\,f_{usable}\,f_{derating}
\]

## 2. Pack-side power

\[
P_{pack}=rac{P_{thrusters}+P_{hotel}}{\eta_{DC}}
\]

## 3. Pack current

\[
I_{pack}=rac{P_{pack}}{V_{pack}(SOC)}
\]

The voltage curve is conceptual and is used only to estimate current.

## 4. SOC update

\[
SOC_{k+1}=\max\left(0,SOC_k-rac{P_{pack}\Delta t}{3600E_{usable}}\,M_Pight)
\]

where \(M_P\) is the current-dependent Peukert-style multiplier.

## 5. Return-home decision

\[
SOC_{command}=\max\left(SOC_{configured},rac{E_{return}+E_{reserve}}{E_{usable}}ight)
\]

This preserves both an energy-based requirement and a deliberately conservative fixed SOC floor.
