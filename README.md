# Bachelorprojekt

Repository til bachelorprojektets notebooks, måledata, referencedokumenter og KiCad-hardwaredesign.

## Struktur

- `notebooks/` - Jupyter-notebooks til analyse, plots, målinger og kalibrering.
- `data/` - Måledata, kalibreringstabeller og genererede plots.
- `docs/` - Diagrammer og instrumentkalibrering brugt til dokumentation.
- `hardware/kicad/` - KiCad-printprojekt og produktionsfiler.
- `references/` - Datablade og artikler brugt som projektreferencer.

## Vigtige filer til bedømmelse

- `notebooks/Filtre.ipynb` - Bode-analyse af LPF- og HPF-trin.
- `notebooks/Plots.ipynb` - spektrale plots, LED-sammenligninger og projektfigurer.
- `notebooks/Live_pulsoximeter_maaling.ipynb` - notebook-version af live-målingen.
- `live_pulsoximeter_maaling.py` - selvstændig liveprototype til måling af HR og SpO2.
- `data/raw/daniel/leder/` - rå spektrometerdata for LED'er, finger og pulsoximeter.
- `data/calibration/` - kalibreringsdata og rå Bode-målinger.
- `data/plots/` - eksportklare figurer til rapport og præsentation.
- `hardware/kicad/` - kredsløbsdiagram, PCB-layout og produktionsfiler.
- `references/datasheets/` - datablade for centrale komponenter.

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
- Løse WaveForms-eksporter i repo-roden ignoreres. Rå målinger ligger i `data/calibration/`, og færdige figurer ligger i `data/plots/`.
