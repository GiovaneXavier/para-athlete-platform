"""K35: a small network trained on synthetic images, against the form. Evidence level N1 (synthetic drawings, labels by construction).

Run from the repository root with `PYTHONPATH=src;spikes` (Windows) and the `k34-models` environment, which already has `torch`:

    python -m k35.make_data      # generates the image sets (outside the repository)
    python -m k35.train          # trains on CPU, checks on the development set only
    python -m k35.final          # the ONE run on the test set (refuses a second run)

Nothing here is imported by `para_triage`. No weight, image or output is stored in the repository.
"""
