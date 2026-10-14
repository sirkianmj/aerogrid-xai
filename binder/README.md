# Binder configuration for AeroGrid-XAI

This directory configures a MyBinder build of AeroGrid-XAI's
reproducibility notebook (`notebooks/11_binder_ready.ipynb`).

## What is in the Binder environment

`binder/environment.yml` narrows the repository's full `environment.yml`
to the dependencies the reproducibility notebook needs: Python 3.12,
NumPy, SciPy, Matplotlib, Z3, PyJWT, JupyterLab, and a small set of pip
packages for the `app` modules' transitive imports.

**Not included** (and not needed by Notebook 11): PostgreSQL, Redis,
MinIO, Node.js, cmake, the frontend toolchain, the SaaS layer's
database driver. Notebook 11 does not touch the multi-tenant SaaS path;
it reproduces the paper's Section 5 numbers using only the CLEAR-D
modules and the physics models.

## How to launch

Click the Binder badge in the repository README, or open directly:

    https://mybinder.org/v2/gh/sirkianmj/aerogrid-xai/HEAD?labpath=notebooks%2F11_binder_ready.ipynb

## Build time

The narrowed environment typically builds in 4-6 minutes on MyBinder's
infrastructure. The full `environment.yml` at the repository root would
take 15-20 minutes because of the native services it pulls in, which
Notebook 11 does not use.

## What this configuration does not do

- It does not build the FastAPI backend as a live service. The notebook
  imports `app.*` modules directly; no HTTP server runs.
- It does not provision a database. If you need to reproduce the SaaS
  layer's RLS tests, run them against a local PostgreSQL per the main
  repository README; the Binder environment is intentionally narrower.
