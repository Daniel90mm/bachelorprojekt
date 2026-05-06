# Bachelorprojekt

Repository til bachelorprojektets notebooks, måledata, referencedokumenter og KiCad-hardwaredesign.

## Struktur

- `notebooks/` - Jupyter-notebooks til analyse, plots, målinger og kalibrering.
- `data/` - Måledata, kalibreringstabeller og genererede plots.
- `docs/` - Diagrammer og instrumentkalibrering brugt til dokumentation.
- `hardware/kicad/` - KiCad-printprojekt og produktionsfiler.
- `references/` - Datablade og artikler brugt som projektreferencer.

## Live pulsoximeter

Kør livevisning med popout-plot:

```bash
python live_pulsoximeter_maaling.py --duration 90 --cycle-rate 10
```

Kør kun LED-test:

```bash
python live_pulsoximeter_maaling.py --led-test
```

## Noter

- Lokale editorfiler, Jupyter-cache, KiCad-låse-/historikfiler og genererede backup-zipfiler ignoreres.
- KiCad-backupmappen indeholder stadig tidligere trackede backups, men nye backup-zipfiler ignoreres som standard.
