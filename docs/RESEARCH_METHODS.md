# Research Methods

## Research question

Where might current agricultural economics understate future land-use optionality enough to justify deeper diligence?

## Current-use economics

The demonstration uses:

`current_use_value_per_acre = annual_cash_rent / farmland_cap_rate`

This is a simplified capitalization proxy, not an appraisal.

## Optionality screening signal

The score is an interpretable weighted screen using:
- substation proximity;
- fiber proximity;
- transmission proximity;
- highway proximity;
- data-center proximity;
- acreage;
- slope;
- flood exposure;
- wetland exposure;
- zoning.

The weights are transparent in SQL.

## Why not a black-box model?

The first objective is methodological defensibility. A complex model trained only on synthetic data would demonstrate modeling mechanics but not necessarily better research judgment.

## Evaluation strategy

The synthetic DGP gives a known five-year conversion label. The project checks conversion rate by optionality-score decile.

A real-data version would add:
- out-of-time validation;
- geographic holdouts;
- calibration;
- ablation tests;
- spatial dependence diagnostics;
- sensitivity analysis;
- transaction-level back-testing.

## Causal inference boundary

The current score is predictive/screening research, not causal inference. Claims such as "a data-center announcement causes land prices to rise X%" require a different design, such as difference-in-differences with a defensible comparison group and parallel-trends validation.
