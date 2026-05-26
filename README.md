# Bachelorprojekt: Prototype Pulsoximeter

Repository til bachelorprojektets notebooks, måledata, referencedokumenter
og KiCad-hardwaredesign for en prototypisk pulsoximeter til ikke-invasiv
måling af arteriel iltmætning (SpO₂).

Systemet bruger to multipleksede LED'er ved 660 nm og 940 nm, en
Hamamatsu S1223 fotodiode og en analog signalkæde med transimpedans-
forstærker, andenordens Sallen-Key lavpasfilter og et ikke-inverterende
gain-trin. Det optiske interface er en modulær 3D-printet fingerklemme,
og signalindsamling og -behandling håndteres af en Analog Discovery 3
og en Python-pipeline baseret på ratio-of-ratios-metoden.

Den fulde rapport ligger som [thesis.pdf](thesis.pdf).

## Resultater (live demo)

- HR: (51.7 ± 0.3) BPM
- SpO₂: (95.8 ± 1.5) %: proof of concept, ikke klinisk kalibreret
- LED-bølgelængder: 664.99 nm (FWHM 18.30 nm) og 951.79 nm (FWHM 27.25 nm)

## Struktur

- [notebooks/](notebooks/): Jupyter-notebooks til analyse, plots, målinger og kalibrering.
- [data/](data/): måledata, kalibreringstabeller, livemålinger og genererede plots.
- [docs/](docs/): diagrammer og instrumentkalibrering brugt til dokumentation.
- [hardware/kicad/](hardware/kicad/): KiCad-printprojekt og produktionsfiler.
- [references/](references/): datablade og artikler brugt som projektreferencer.
- [thesis.pdf](thesis.pdf): den endelige rapport.

## Vigtige filer

- [notebooks/filtre.ipynb](notebooks/filtre.ipynb): Bode-analyse af LPF- og HPF-trin.
- [notebooks/plots.ipynb](notebooks/plots.ipynb): spektrale plots, LED-sammenligninger og projektfigurer.
- [notebooks/optokæde.ipynb](notebooks/optokæde.ipynb): simulering af hele optokæden fra LED til signal.
- [notebooks/hyperspektral_pixelanalyse.ipynb](notebooks/hyperspektral_pixelanalyse.ipynb): pixelanalyse af hyperspektrale .tif-billeder.
- [notebooks/spektrometer.ipynb](notebooks/spektrometer.ipynb): spektrometeranalyse.
- [notebooks/lineær_stage_kalibrering.ipynb](notebooks/lineær_stage_kalibrering.ipynb): kalibrering af lineær stage.
- [live_pulsoximeter_måling.py](live_pulsoximeter_måling.py): selvstændig liveprototype til måling af HR og SpO₂.
- [plot_pulsoximeter_målinger.py](plot_pulsoximeter_målinger.py): genererer rapportplots fra livemålingerne.
- [data/live/](data/live/): livemålinger brugt til rapportens demonstrationsplots.
- [data/calibration/](data/calibration/): kalibreringsdata og rå Bode-målinger.
- [data/plots/](data/plots/): eksportklare figurer til rapport og præsentation.
- [hardware/kicad/](hardware/kicad/): kredsløbsdiagram, PCB-layout og produktionsfiler.
- [references/datasheets/](references/datasheets/): datablade for centrale komponenter.

## Krav og installation

- Python 3.10 eller nyere.
- Digilent WaveForms SDK installeret (kræves af `dwfpy` for at tale med Discovery 3).

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Live pulsoximeter

Kør livevisning med popout-plot:

```bash
python live_pulsoximeter_måling.py --cycle-rate 7.41
```

Regenerer rapportplots fra livemålingerne i [data/live/](data/live/):

```bash
python plot_pulsoximeter_målinger.py
```

## Noter

- Lokale editorfiler, Jupyter-cache, KiCad-låse-/historikfiler og genererede backup-zipfiler ignoreres.
- Løse WaveForms-eksporter og rå livemålinger i repo-roden ignoreres.
  Rå kalibreringsmålinger ligger i [data/calibration/](data/calibration/),
  navngivne livemålinger i [data/live/](data/live/), og færdige figurer
  ligger i [data/plots/](data/plots/).

## Licens

MIT: se [LICENSE](LICENSE).
