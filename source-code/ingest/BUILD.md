# Building ingest function images (vastde / Paketo)

## OpenTelemetry: do not pin in `requirements.txt`

`vast-buildpack` installs `vast_runtime`, which pulls **OpenTelemetry 1.42+** and `opentelemetry-processor-baggage` 0.63+ into the **cpython** layer.

Paketo **prepends** your `pip install` layer to `PYTHONPATH`:

```text
/layers/paketo-buildpacks_pip-install/packages/...   ← searched first
/layers/paketo-buildpacks_cpython/cpython/...        ← vast_runtime + OTEL 1.42
```

If `requirements.txt` pins `opentelemetry-sdk==1.38` (or any version **older** than runtime), Python loads the **old SDK from pip-install** while `processor-baggage` comes from runtime → `ImportError: ReadWriteLogRecord`.

**Fix:** Remove all `opentelemetry-*` lines from `requirements.txt`. `from opentelemetry import trace` in handlers still works via the runtime layer.

## Clear build cache after OTEL / requirements changes

Your build log showed `Requirement already satisfied: opentelemetry-api==1.38.0` from **cache**, even after editing requirements.

Rebuild **without** reusing the pip-install cache, for example:

```bash
# If using pack directly:
pack build <image> --path . --clear-cache

# Or delete cached volumes (name from build log), e.g.:
# pack-cache-library_vss-video-segmenter_latest-*.build
```

Then redeploy the new image to DataEngine.

## Verify build log

After `pip install`, you should **not** see `opentelemetry-api==1.38` (or any pinned OTEL) from `requirements.txt`.

During **VAST Buildpack** install you should see runtime OTEL, e.g.:

```text
opentelemetry-api ... (1.42.x)
opentelemetry-processor-baggage ... (0.63.x)
```
