# FloodNet Davao ML

**Live map:** <https://floodnet-davao.onrender.com>

**Complete project report and instructions:** [reports/PROJECT_REPORT.md](reports/PROJECT_REPORT.md)

The source geospatial data is in the sibling `floodnetData\data` directory.
This project starts by auditing the Davao layers before building a training
dataset.

## Set up

From this directory, create the Conda environment and run the audit. In a
Miniforge Prompt:

```powershell
conda env create -f environment.yml
conda run -n floodnet-ml python scripts/audit_davao.py
```

In a regular PowerShell terminal, call Conda by its per-user install path:

```powershell
$conda = "$env:USERPROFILE\miniforge3\Scripts\conda.exe"
& $conda env create -f environment.yml
& $conda run -n floodnet-ml python scripts/audit_davao.py
```

The audit reports vector-layer schemas, feature counts, coordinate systems,
extents, and the elevation raster properties. It does not modify the source
data.

## Build the training table

After reviewing the audit, create a GeoPackage with one row per road segment
inside the Metro Davao study area:

```powershell
conda run -n floodnet-ml python scripts/build_training_data.py
```

The three `flood_*` columns are separate binary target labels. The model inputs
exclude those labels and include road type, length, speed, elevation, slope,
and segment location. Missing elevation values are retained for imputation in
the training pipeline. The default output is
`data\processed\davao_training.gpkg`.

The labels describe intersection with the supplied hazard polygons; they do
not predict when a flood will happen. The 100-year flood layer has different
source coverage from the 5- and 25-year layers, so results must be evaluated
per scenario and reported with that limitation.

## Train and evaluate

Train one Random Forest classifier per flood scenario:

```powershell
conda run -n floodnet-ml python scripts/train_models.py
```

The evaluation holds out 5 km geographic blocks rather than randomly splitting
nearby road segments. Metrics and trained models are written to `reports\` and
`models\`. Use the spatial-holdout scores—not training scores—as the first
estimate of how well the model generalizes to unseen parts of Metro Davao. The
saved models are then refitted on all Metro Davao segments for map display.

## Generate map predictions

```powershell
conda run -n floodnet-ml python scripts/predict_map.py
```

This writes scenario-specific model probabilities and road geometry to
`data\processed\davao_predictions.gpkg`.

## Run the website

```powershell
conda run -n floodnet-ml uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>. Zoom in to level 13 or closer to load roads,
choose a return-period scenario, and click a road for its model-estimated
exposure score. The map uses OpenStreetMap tiles and needs an internet
connection for the basemap and Leaflet library.

The map is a student-project visualization, not an operational flood forecast
or a source of emergency guidance. Estimated scores describe similarity to the
provided scenario labels; they do not give a chance or date of future flooding.

## Publish on GitHub and Render

The website can be deployed from GitHub using the included Dockerfile and
`render.yaml`. The prediction GeoPackage is about 54 MB and is needed by the web
app, so it is included in Git. The raw source data, training GeoPackage, and
large model files are not needed to run the deployed map and are excluded.

1. Create a new, empty GitHub repository. Do not initialize it with a README.
2. In PowerShell, open this folder and push the project:

   ```powershell
   Set-Location C:\Users\Administrator\Documents\floodnet\floodnet-ml
   git init
   git add .
   git status --short
   git commit -m "Prepare FloodNet Davao web app"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/floodnet-davao.git
   git push -u origin main
   ```

   Replace `YOUR-USERNAME` with your GitHub username. Review `git status` before
   committing: `models/` and `data/processed/davao_training.gpkg` should not be
   listed, while `data/processed/davao_predictions.gpkg` should be listed.
3. In Render, choose **New → Blueprint**, connect the GitHub repository, and
   deploy the `render.yaml` blueprint. Render builds the Docker image and
   provides a website URL when the deployment finishes.
4. Open that URL and test the scenario selector and map. The map needs an
   internet connection for OpenStreetMap tiles and the Leaflet library.

The free Render service may sleep while idle; its first request after a quiet
period can take roughly 50 seconds to wake up. This blueprint uses the public
repository URL, so future commits might need a manual deploy from the Render
dashboard.

The prediction file exceeds GitHub's 50 MB warning threshold but is below the
100 MB per-file limit. GitHub may warn when it is committed. Never add the
trained model files; each is over the normal GitHub file limit.

### Can this use Vercel?

Vercel is better suited to the static map interface than to this complete app:
the Python API needs a GIS runtime and reads the 54 MB GeoPackage. The
straightforward deployment is to host the full app on Render. Another option
is Vercel for a separate frontend and Render for its API, but that requires
changing the API URL and enabling cross-origin requests.

### Other hosting options

- **Railway or Fly.io:** can also run the included Dockerfile.
- **Your own Linux server:** install Docker, copy the repository, and run
  `docker compose up -d` or build and start the image directly.
- **GitHub Pages:** serves static files only; it cannot run this Python API.

The map includes OpenStreetMap attribution. Keep the data sources and licensing
notes in the project when publishing it.
