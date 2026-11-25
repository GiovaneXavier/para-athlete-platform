"""image-and-report check: consistency check between an image and a report (prototype, evidence level N1).

Pure logic and level 1 (a mannequin drawn by us). Nothing here imports `torch`, `transformers`
or anything that reaches the network; the model extractors belong to a later PR, under
`spikes/imagem_laudo/`. The result is always a warning for human review. See
`docs/consistencia-imagem-laudo.md`.
"""
