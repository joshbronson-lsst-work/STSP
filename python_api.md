# Python API

## Overview

The `stsp` Python package in this repo provides a small, typed API to
assemble STSP input files and run actions, producing NumPy arrays from
STSP outputs. The code consists mainly of Action types, which specify
parameters and configuration, and ActionRunner types, which take
Action instances and execute them by shelling out to the `stsp_bin`
binary.

## Installation

    cd /path/to/this/repo
    pip install -e .

## Action Classes

The actions are named for compatibility with the C-code:

- `stsp.actions.ActionL` refers to forward modeling, which generates
  an expected light curve given a specified configuration. Instances
  of this class should be run with the stsp.runner.ActionLRunner
  class.
- `stsp.actions.ActionM` refers to MCMC, which optimizes parameters to
  match an observed light curve. It can be used with optional
  parameters `sigma_radius`, `sigma_angle`, `seed_spot_triplets`, and
  `seed_brightness_correction` to run seeded MCMC, corresponding to
  the C code's action s, or without those parameters to run unseeded
  MCMC, corresponding to the C code's action m. Instances of this
  class should be run with the stsp.runner.ActionMRunner class.

## Examples

See the following examples:
- [ActionL](sample/run_l.py)
- [ActionM (unseeded)](sample/run_m.py)
- [ActionM (seeded)](sample/run_s.py)

## Quick Start

Run an example: 

    cd sample 
    PATH=../bin:$PATH PYTHONPATH=.. python3 run_l.py

In addition to creating a numpy array, the example script will emit
`pyact-l_lcout.txt`, and write it (using numpy's `savetext` function)
to a file compatible with the C-code output.
