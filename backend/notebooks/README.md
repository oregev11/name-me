# ML sanity-check notebook

`ml_sanity_check.ipynb` loads the real `nameme` package and the real committed model
artifacts — the exact same code and data the running app uses — so you can manually poke at
the ML logic: compare arbitrary name pairs, run full searches with filters, and eyeball
results on the 2D map. Nothing in it is reimplemented; if something looks wrong here, it's
wrong in the app too.

## Running it

From `backend/` (the kernel needs the project's own `.venv`, where `nameme` is installed):

```bash
uv sync --group notebook
uv run jupyter lab notebooks/
```

Then open `ml_sanity_check.ipynb` and run cells top to bottom. After that, jump back into
any section, edit the names/filters, and re-run just that cell.

The `notebook` dependency group (`jupyterlab`, `ipykernel`, `matplotlib`) is separate from
the app's runtime and `dev` dependencies — same pattern as the `export` group used for the
offline ONNX model export — so it never ends up in the deployed image or CI. Concretely:
`backend-ci.yml`'s `uv sync --all-extras` step (see the backend README's
[CI/CD](../README.md#cicd) section) only ever installs the default + `dev` groups — this
notebook and its dependencies are simply invisible to CI, by design, not by accident. That
also means this notebook is never executed automatically anywhere — it's a manual tool, run
by hand and committed **with its cell outputs already in it** (`jupyter execute --inplace`
was run once before committing), so the numbers you see in the file on GitHub are real,
previously-produced results, not empty cells waiting to be run.

## What's in it

1. **Direct embedding checks** — `compare(name_a, name_b, model)`: raw cosine similarity
   between two bare names, bypassing search/ranking/filters entirely.
2. **Full search pipeline** — `run_search(liked_names, model, top_k, **filters)`: calls
   `search_service.search()` directly (no HTTP), returned as a tidy DataFrame. Any filter
   keyword the real endpoint accepts (`sex`, `sector`, `popularity`, `sort`, `year_min`,
   `year_max`) works here too.
3. **2D visualization** — `plot_search(...)`: a matplotlib version of the app's scatter
   plot (liked names as big stars, suggestions colored by sex and sized by popularity).
4. **Filter sanity checks** — interactive versions of the `test_corpus_store.py` /
   `test_search.py` regression tests, using real names with known, verifiable behavior.
5. **Try your own** — a blank cell to experiment freely.
