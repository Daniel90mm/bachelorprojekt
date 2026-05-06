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
- `notebooks/Live_pulsoximeter_måling.ipynb` - notebook-version af live-målingen.
- `live_pulsoximeter_måling.py` - selvstændig liveprototype til måling af HR og SpO2.
- `data/raw/daniel/leder/` - rå spektrometerdata for LED'er, finger og pulsoximeter.
- `data/calibration/` - kalibreringsdata og rå Bode-målinger.
- `data/plots/` - eksportklare figurer til rapport og præsentation.
- `hardware/kicad/` - kredsløbsdiagram, PCB-layout og produktionsfiler.
- `references/datasheets/` - datablade for centrale komponenter.

## Krav og installation

<!-- Samler Python-afhængigheder ét sted, så bedømmer/medstuderende kan
     opsætte miljøet uden at læse imports manuelt. -->

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
python live_pulsoximeter_måling.py --duration 90 --cycle-rate 10
```

Kør kun LED-test:

```bash
python live_pulsoximeter_måling.py --led-test
```

## Licens

<!-- Gør betingelserne for genbrug eksplicitte, så koden kan deles uden
     tvivl om rettigheder. MIT er valgt som permissiv standard. -->

Koden i dette repository er udgivet under MIT-licens — se [LICENSE](LICENSE).
Måledata, figurer og rapportmateriale er ophavsretligt beskyttet og må kun
genbruges efter aftale.

## Noter

- Lokale editorfiler, Jupyter-cache, KiCad-låse-/historikfiler og genererede backup-zipfiler ignoreres.
- Løse WaveForms-eksporter i repo-roden ignoreres. Rå målinger ligger i `data/calibration/`, og færdige figurer ligger i `data/plots/`.
