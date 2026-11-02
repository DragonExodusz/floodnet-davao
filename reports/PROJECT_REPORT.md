# Machine Learning Classification of Road Flood-Hazard Exposure in Metro Davao

**Course:** [Course name]

**Instructor:** [Instructor name]

**Prepared by:** [Student name(s)]

**Institution:** [School name]
**Submission date:** [Date]

> **Scope note:** This is a report on classifying road exposure to supplied
> flood-hazard scenarios. It is not a weather forecast, a flood-event
> probability estimate, or an emergency-planning product. Fill in the cover
> details and confirm that the instructor accepts this scenario-classification
> problem before submitting.

## Abstract

This project applies supervised machine learning to a geospatial road network
for Metro Davao, Philippines. Each road segment is labeled as exposed or not
exposed according to whether it intersects the supplied Project NOAH flood
hazard polygons for the 5-, 25-, and 100-year return-period scenarios. Three
separate Random Forest classifiers use road type, segment length, speed,
elevation, slope, and location to reproduce those labels. The evaluation uses
5 km geographic blocks to hold out locations, reducing the optimistic scores a
random road-by-road split could produce. On one spatial holdout, the classifiers
achieved F1 scores of 0.651, 0.710, and 0.836 for the 5-, 25-, and 100-year
labels, respectively. The 100-year result is only slightly above the
majority-class F1 baseline of 0.821. These results measure agreement with
existing map-derived labels, not prediction of future flood events. An
interactive web map displays model-estimated exposure scores for road segments
and lets viewers switch between the three scenarios.

## 1. Introduction

### Dataset overview

The project combines a road-network GeoPackage, administrative-boundary
polygons, an elevation raster, and Project NOAH flood-hazard polygons. The
study-area road graph contains 107,697 nodes and 253,758 edge records in its
source GeoPackage. Filtering to edges flagged inside the Metro Davao study
area yields the 199,866 road segments used in the training table.

### Motivation

Flood-hazard maps show areas affected under modeled rainfall scenarios, but it
can be difficult to compare road exposure across locations or return periods.
A road-level classifier provides an introductory machine-learning exercise
and a consistent set of model estimates that can be inspected on an interactive
map. The analysis can help communicate where mapped hazard and transport
infrastructure overlap. It is not a substitute for hydrologic modeling or
validated operational flood forecasts.

### Objective

Build and evaluate three binary classifiers—one each for the available 5-,
25-, and 100-year flood-hazard scenarios—that estimate whether a Metro Davao
road segment has the corresponding map-derived flood-exposure label. Report
classification metrics on spatially held-out road locations and display the
model estimates in an interactive web map.

## 2. Problem Statement

For each road segment inside the available Metro Davao road-network study
area, classify whether its target scenario's flood-exposure label is positive
(1) or negative (0). Predict three targets independently:

- `flood_5yr`: exposure under the supplied 5-year return-period hazard map.
- `flood_25yr`: exposure under the supplied 25-year return-period hazard map.
- `flood_100yr`: exposure under the supplied 100-year return-period hazard map.

The measurable question is: **How accurately can road and elevation attributes
classify the supplied binary labels for road segments in geographic blocks
withheld from training?**

Here, "exposed" means the source road-edge label intersects the corresponding
hazard extent. A negative label means only that the supplied source flag is
false for that scenario. It does not establish that a road is safe from
flooding.

### What this project does not predict

A 5-, 25-, or 100-year return period describes the probability convention of a
design flood event in a given year under the source study's assumptions; it
does **not** mean that the event will occur exactly once every 5, 25, or 100
years, nor that it will occur that many years in the future. This project has
no date-specific rainfall inputs, time series, or observed future flood labels.
It classifies existing scenario-map labels; it does not forecast flood dates,
depth at a specific future time, or the real-world probability of an event.

## 3. Dataset and Exploratory Data Analysis

### 3.1 Sources and geographic scope

The supplied project data are organized under `floodnetData\data`:

| Data | Project file | Source and use |
|---|---|---|
| Road network | `network\davao.gpkg` | Enriched Davao road graph derived from OpenStreetMap (OSM); nodes and edges are stored in separate GeoPackage layers. |
| Administrative boundaries | `boundaries\davao.shp` and companion Shapefile files | City/municipality polygons used to define the study area. |
| Elevation | `elevation\davao.tif` | SRTM-derived digital elevation raster, sampled into the provided enriched road network. |
| Flood hazards | `flood\year_5\davao.shp`, `flood\year_25\davao.shp`, and `flood\year_100\davao.shp` | Project NOAH hazard polygons, with low/medium/high hazard classes represented by `Var` values 1, 2, and 3. |

The flood metadata defines the retained Metro Davao LGUs as Davao City, Tagum
City, Panabo City, Digos City, Carmen, Hagonoy, Santa Cruz, Padada, Malalag,
and Sulop. The boundary file contains an additional Samal polygon, but Samal
has no mainland road-network representation in the extracted connected graph
and does not contribute training edges. Maco is excluded because NOAH flood
data are unavailable; Malita and Santa Maria are excluded because 5- and
25-year labels are unavailable. The 100-year source layer has broader source
coverage than the 5- and 25-year layers; its labels are evaluated separately
and must not be interpreted as a directly comparable future forecast.

The source layers and road geometry use WGS 84 (EPSG:4326). The Davao
administrative-boundary file contains 11 polygons. The road GeoPackage
contains 107,697 nodes and 253,758 edges; 199,866 edges are flagged
`in_metro` and used in this experiment.

### 3.2 Unit of analysis and features

Each row represents one road edge. The training table contains **199,866
records** and has the following model inputs:

| Feature | Type | Meaning/preprocessing |
|---|---|---|
| `highway` | Categorical | OSM road class; encoded with one-hot encoding. The source contains 12 observed classes. |
| `log_length_m` | Numeric | Natural logarithm of `1 + length_m`, reducing the effect of very long road segments. |
| `base_speed_kmh` | Numeric | Road-network base speed in kilometres per hour. |
| `min_elevation` | Numeric | Minimum endpoint elevation for the edge, in metres; 278 values are missing in the study-area edge table. |
| `midpoint_lon`, `midpoint_lat` | Numeric | Road midpoint coordinates. The midpoint is calculated after projecting to the estimated local UTM CRS, then stored in WGS 84. |
| `elevation_range_m` | Numeric | Absolute difference between endpoint elevations, in metres. |
| `slope_percent` | Numeric | Absolute elevation range divided by segment length, multiplied by 100. It is an unsigned grade proxy, not a directional slope. |

The identifiers `u`, `v`, and `key`, the road geometry, and target columns are
retained for joining and mapping but are not model input features. In
particular, the three `flood_*` labels are excluded from the input features
when predicting any of those labels.

### 3.3 Target labels and class balance

The enriched edge layer already contains the Boolean `flood_5yr`,
`flood_25yr`, and `flood_100yr` labels. The extraction metadata describes
these fields as indicators of intersection with the respective hazard
polygons. The training-table builder filters to the Metro Davao study area
and converts each label to 0/1. This is a reproducible, map-derived target,
not an independently observed flood-impact record.

Class counts for the complete 199,866-edge training dataset:

| Target | Exposed (1) | Not exposed (0) | Exposed share |
|---|---:|---:|---:|
| 5-year | 82,072 | 117,794 | 41.06% |
| 25-year | 92,616 | 107,250 | 46.34% |
| 100-year | 135,626 | 64,240 | 67.86% |

The more-positive 100-year label distribution may partly reflect the source
coverage and scenario-map construction. Do not infer a future trend or an
annual probability directly from these proportions.

### 3.4 Data quality and preprocessing needs

- The provided feature table has 278 missing `min_elevation` values among the
  199,866 included edges. Numeric missing values are imputed using the median
  calculated from the training partition.
- Missing categorical `highway` values, if any, are imputed using the most
  frequent training-partition category.
- Categorical highway classes are one-hot encoded. Unknown categories are
  ignored by the encoder rather than causing inference to fail.
- Segment length is transformed to `log1p(length_m)` before model fitting.
- Coordinates are used as model inputs. Spatially grouped validation is used
  because nearby roads have correlated locations and labels.
- No feature scaling is required by the Random Forest. The preprocessing is
  implemented in a scikit-learn `Pipeline` so validation and inference use
  the same transformations.

## 4. Methodology

### 4.1 Data preprocessing

Run `scripts\audit_davao.py` to inspect source files, coordinate systems,
geometry, feature counts, and label coverage. Run
`scripts\build_training_data.py` to:

1. Read the Davao `edges` layer.
2. Keep only segments where `in_metro` is true.
3. Join the edge endpoint elevations from the `nodes` layer using `u` and `v`.
4. Compute a projected geometry midpoint and convert the midpoint back to
   WGS 84.
5. Compute absolute endpoint elevation range and an unsigned slope proxy.
6. Preserve the three source labels as separate binary targets.
7. Write a GeoPackage layer named `road_segments`.

The flood-label columns are **targets**, not predictors. Using a target as a
predictor would leak the answer and invalidate the evaluation.

### 4.2 Model and training/validation

Three independent scikit-learn `RandomForestClassifier` models are trained,
one per target. The configured classifier uses:

- 120 decision trees (`n_estimators=120`)
- Maximum tree depth 18
- Minimum samples per leaf 2
- Balanced subsampling of classes (`class_weight="balanced_subsample"`)
- Fixed random seed 42
- All available CPU cores for training

For context, a `DummyClassifier(strategy="most_frequent")` baseline is
evaluated on the same holdout. This baseline always predicts the most common
training class; it is deliberately simple and does not use road features.

#### Spatial holdout

Road midpoints are projected to UTM zone 51N (EPSG:32651) and assigned to
fixed 5 km by 5 km square blocks. `GroupShuffleSplit` holds out entire blocks,
so no block is in both partitions. The split uses seed 42 and
`test_size=0.20`, which means 20% of the **groups**, not 20% of the rows.
Because road counts vary by block, the realized partition is:

| Partition | Spatial blocks | Road segments |
|---|---:|---:|
| Training/validation fit | 146 | 130,073 |
| Held-out test | 37 | 69,793 |
| Total | 183 | 199,866 |

This is one spatial holdout, not repeated cross-validation. After the reported
holdout metrics are calculated, each saved model is refitted on all 199,866
segments for use by the map. The map-serving models have therefore seen the
whole study-area dataset; the held-out metrics describe the earlier
evaluation-only fit, not the refitted web model.

### 4.3 Evaluation metrics

Because each target is binary, the report uses:

- **Precision:** among segments predicted exposed, the fraction labeled
  exposed.
- **Recall:** among exposed segments in the test set, the fraction found by
  the model.
- **F1-score:** harmonic mean of precision and recall.
- **ROC-AUC:** ranking ability across probability thresholds; 0.5 indicates
  chance-level ranking and 1.0 indicates perfect ranking on this test set.
- **Accuracy:** fraction of all correct class predictions.
- **Balanced accuracy:** average of the recall for each class, useful when
  class proportions differ.
- **Confusion matrix:** reported in `[[TN, FP], [FN, TP]]` order.

This is a classification problem, so regression metrics such as MAE, RMSE,
and R-squared do not apply to the binary target as evaluated here. The
Random Forest `predict_proba` output is a model score/class-vote fraction.
It has **not** been calibrated against real-world flood-event probabilities.

## 5. Results and Discussion

### 5.1 Spatial-holdout results

| Scenario target | Model | Accuracy | Balanced accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---:|---:|---:|---:|---:|---:|
| 5-year | Majority baseline | 0.572 | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 |
| 5-year | Random Forest | 0.728 | 0.711 | 0.724 | 0.591 | 0.651 | 0.822 |
| 25-year | Majority baseline | 0.507 | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 |
| 25-year | Random Forest | 0.748 | 0.746 | 0.821 | 0.625 | 0.710 | 0.851 |
| 100-year | Majority baseline | 0.696 | 0.500 | 0.696 | 1.000 | 0.821 | 0.500 |
| 100-year | Random Forest | 0.766 | 0.707 | 0.816 | 0.857 | 0.836 | 0.775 |

The majority baseline predicts only the most common class. Its zero positive
recall for the 5- and 25-year targets illustrates why accuracy alone is
misleading. The Random Forest improves the tested metrics for all three
targets, with its strongest ROC-AUC on the 25-year target.

The 100-year target is more imbalanced: 69.6% of the held-out records are
positive. The majority baseline therefore obtains F1 = 0.821 despite having
balanced accuracy and ROC-AUC of 0.500. The Random Forest's F1 = 0.836 is
only 0.015 higher, and its ROC-AUC is 0.775. Thus, the 100-year model's
headline F1 should not be presented as strong evidence of useful
discrimination without the baseline, balanced accuracy, and ROC-AUC.

### 5.2 Random Forest confusion matrices

Rows are actual class 0 and class 1; columns are predicted class 0 and class
1.

| Scenario | True negatives | False positives | False negatives | True positives |
|---|---:|---:|---:|---:|
| 5-year | 33,186 | 6,741 | 12,211 | 17,655 |
| 25-year | 30,733 | 4,674 | 12,908 | 21,478 |
| 100-year | 11,828 | 9,398 | 6,963 | 41,604 |

For the 5- and 25-year scenarios, recall of 0.591 and 0.625 means the
classifier misses a substantial share of positive, map-derived test labels.
For 100-year, recall is 0.857, but the high positive prevalence means many
positive predictions are expected even from the naive majority baseline.
These are not safety guarantees and should not be used for emergency
decisions.

### 5.3 Interactive results

The online map presents road segments, scenario selection, zoom/pan controls,
and a click-to-view model score. It uses color bins for display and fetches
roads in the current map bounding box after the user zooms in. The score is
the Random Forest estimate for the selected binary map label; it is **not**
the chance that a flood will occur. Small free hosting instances may sleep
when idle, and the first request can take longer to respond.

## 6. Conclusion, Limitations, and Future Work

### Conclusion

The project demonstrates an end-to-end geospatial classification workflow:
audit source layers, assemble road-level features, train scenario-specific
Random Forest classifiers, evaluate with a spatial holdout and a naive
baseline, and publish map estimates through an interactive website. The
5-year and 25-year classifiers improve meaningfully over the majority
baseline on this one spatial test. The 100-year model's F1 is only modestly
above its majority baseline, so its predictive value is less convincing.

### Limitations

1. **Map-derived, not observed labels.** The targets come from intersection
   flags based on supplied flood polygons. They do not represent independent
   measurements of road flooding, real impacts, or historical flood events.
2. **No time-based prediction.** There are no daily rainfall inputs, event
   timelines, or future climate features. Return periods are scenario
   descriptors, not forecasts of when an event will occur.
3. **One spatial split.** A single 5 km-block holdout cannot fully characterize
   performance across all locations. Blocks are adjacent, so spatial
   autocorrelation across block boundaries can remain. Repeated spatial
   cross-validation and an external geographic test area would give stronger
   evidence.
4. **Scenario data gaps.** The 5-, 25-, and 100-year source layers have
   different coverage. Several LGUs are excluded because labels are missing,
   and Samal is not represented in the connected road dataset.
5. **Proxy features and position.** Elevation and coordinates are imperfect
   predictors of mapped flood exposure. The unsigned endpoint elevation
   difference is a coarse grade proxy, not a hydrologic terrain model.
6. **Model scores are uncalibrated.** The scores shown on the map are not
   calibrated probabilities of actual flooding and should not be interpreted
   as such.
7. **Source accuracy and resolution.** OSM completeness, SRTM elevation
   resolution, geometry matching, and the original hazard-model assumptions
   constrain accuracy.
8. **Operational safety.** This project is a classroom demonstration, not an
   emergency response tool. A low model score must not be taken as evidence a
   road is safe.

### Future work

- Evaluate repeated spatial cross-validation and report score variability.
- Compare against logistic regression and tune decision thresholds based on
  an explicitly chosen objective.
- Add independently observed flood incidents, road closures, rainfall, and
  timestamped environmental data before attempting event forecasting.
- Seek a hydrology-informed independent validation set and calibrate model
  scores if probability interpretation is required.
- Improve map performance with vector tiles or server-side generalization for
  broad zoom levels.

## 7. References

1. Project NOAH, University of the Philippines. *Flood Hazard Maps* dataset
   and source/method notes supplied with the project. Archived source:
   <https://drive.google.com/drive/folders/1ALE4-E9c-4AGjm1fqiPprWHrLUskeY9o>.
   Dataset mirror:
   <https://huggingface.co/datasets/bettergovph/project-noah-hazard-maps>.
   Accessed for this project: [insert date].
2. Geofabrik. *Philippines OpenStreetMap Extract*. The supplied metadata
   records an extract snapshot of 2026-03-27.
   <https://download.geofabrik.de/asia/philippines.html>.
   Accessed for this project: [insert date].
3. OpenStreetMap contributors. *Copyright and Open Database License (ODbL)
   attribution*. <https://www.openstreetmap.org/copyright>.
4. NASA Earthdata. *Shuttle Radar Topography Mission (SRTM)*.
   <https://www.earthdata.nasa.gov/data/instruments/srtm>.
5. Breiman, L. (2001). Random Forests. *Machine Learning*, 45, 5–32.
   <https://doi.org/10.1023/A:1010933404324>.
6. scikit-learn developers. *RandomForestClassifier*.
   <https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html>.
7. scikit-learn developers. *GroupShuffleSplit*.
   <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html>.
8. Philippine Statistics Authority / National Mapping and Resource
   Information Authority (PSA/NAMRIA). Administrative boundary source as
   described in the supplied project boundary metadata. Source release
   recorded there: 2023-11-06.

## 8. Appendix A — Reproduction and User Instructions

### A.1 Online map

**Public map:** <https://floodnet-davao.onrender.com>

**Public source repository:** <https://github.com/DragonExodusz/floodnet-davao>

1. Open the public map link in a modern browser with an internet connection.
2. Select **5-year**, **25-year**, or **100-year return period**.
3. Zoom into the Davao road network. Road segments are loaded at detailed
   zoom levels; at smaller scales the application asks the viewer to zoom in.
4. Pan to another area; the visible map extent determines which segments are
   requested.
5. Click a road segment to view its road type, length, and model-estimated
   exposure score for the selected scenario.
6. Change the scenario selector to compare the same view across map labels.

OpenStreetMap tiles and the Leaflet JavaScript library are loaded from their
public web services. The free hosting tier can sleep after inactivity, so
allow time for the first page load. Online hosting is for project
demonstration only; it is not a safety-critical service.

### A.2 Run the web map locally (fast path)

This runs the existing prediction file; it does not retrain the models. The
public GitHub repository includes the prediction GeoPackage required by the
website.

**Requirements:** Windows PowerShell, Git, and Miniforge/Conda. Internet is
needed for package setup and the basemap.

```powershell
git clone https://github.com/DragonExodusz/floodnet-davao.git
Set-Location floodnet-davao
$conda = "$env:USERPROFILE\miniforge3\Scripts\conda.exe"
& $conda env create -f environment.yml
& $conda run -n floodnet-ml uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. To stop the local server, focus its PowerShell
window and press **Ctrl+C**. If Miniforge is installed in another location,
replace the `$conda` path with that installation's `Scripts\conda.exe`.

### A.3 Reproduce training locally

Training requires the full source data directory alongside the cloned project
folder in this layout:

```text
floodnet\
  floodnet-ml\
  floodnetData\
    data\
      boundaries\
      elevation\
      flood\
      network\
```

The raw `floodnetData` layers are not copied into the GitHub repository. Obtain
them from the project data distribution and keep the directory next to
`floodnet-ml`.

From the `floodnet-ml` project folder, run:

```powershell
$conda = "$env:USERPROFILE\miniforge3\Scripts\conda.exe"
& $conda run -n floodnet-ml python scripts\audit_davao.py
& $conda run -n floodnet-ml python scripts\build_training_data.py
& $conda run -n floodnet-ml python scripts\train_models.py
& $conda run -n floodnet-ml python scripts\predict_map.py
& $conda run -n floodnet-ml uvicorn app:app --host 127.0.0.1 --port 8000
```

The builder creates `data\processed\davao_training.gpkg`. The trainer writes
the evaluation metrics to `reports\davao_model_metrics.json` and refits the
saved models in `models\` on all study-area data. The prediction script writes
`data\processed\davao_predictions.gpkg`, which the local web server reads.
Review the metric report before comparing a retrained result with this
report: library versions or changed input data can change scores.

### A.4 Deploy or update the hosted site

The repository is connected to a Render Blueprint, and the current public
site is already hosted at <https://floodnet-davao.onrender.com>.

- The GitHub repository is the source of the code and deployment
  configuration.
- To update the hosted version, push a commit to the `main` branch, then open
  the Render dashboard and trigger **Manual Deploy** if Render does not
  automatically deploy the public-repository update.
- Check the deploy log for a successful build, then verify the site and
  `/api/health`.
- The website image includes `data\processed\davao_predictions.gpkg`; it does
  not need the training data or serialized model files at runtime.
- The hosted service cannot retrain the models. To publish new model
  predictions, regenerate the prediction GeoPackage, commit the updated file
  if it remains under GitHub's file-size limits (or move it to appropriate
  external object storage), and deploy the update.

### A.5 Project files

| Path | Purpose |
|---|---|
| `scripts\audit_davao.py` | Inspect source file schemas, CRS, bounds, and label coverage. |
| `scripts\build_training_data.py` | Build the road-segment training GeoPackage. |
| `scripts\train_models.py` | Fit/evaluate the baseline and scenario Random Forests; save metrics and final models. |
| `scripts\predict_map.py` | Generate scenario score columns and mapped road geometries. |
| `app.py` | FastAPI endpoints and static web app serving. |
| `web\` | Interactive Leaflet map user interface. |
| `data\processed\davao_training.gpkg` | Generated training data; not committed to the public repository. |
| `data\processed\davao_predictions.gpkg` | Web-serving road geometry and model scores; committed for deployment. |
| `reports\davao_model_metrics.json` | Machine-readable evaluation metrics. |
| `Dockerfile`, `render.yaml` | Container and Render hosting configuration. |

## Appendix B — Confusion Matrices

Confusion matrices for the majority baseline, in `[[TN, FP], [FN, TP]]`
order:

| Scenario | Matrix |
|---|---|
| 5-year | `[[39,927, 0], [29,866, 0]]` |
| 25-year | `[[35,407, 0], [34,386, 0]]` |
| 100-year | `[[0, 21,226], [0, 48,567]]` |

Machine-readable full results, including the Random Forest matrices and
metric precision, are in `reports\davao_model_metrics.json`.
