# F1 Driver Telemetry

Splunk Enterprise app for events emitted by the v6 F1 2025 collector.

## Views

- `f1_live_telemetry`: speed, RPM, lap, controls, tyre temperature, G force, ERS and fuel.
- `f1_lap_comparison`: best lap, top speed, lap pace, position and driver results.
- `f1_results_health`: event volume, freshness, completed attempts, HEC delivery and sourcetype coverage.

## Data contract

- Index: `data_drivers_f1_2025`
- Source: `f1_2025`
- Modes: `data_mode=live|playback`
- Identity: `attempt_id`, `record_id`, `player_name`, `rig_id`
- Results: `sourcetype=SessionCompleted`
- Delivery health: `sourcetype=CollectorHealth`

Delivery is at least once. Searches over completed attempts must deduplicate by `record_id`.

Generate the views with `python3 scripts/build_splunk_views.py` from the repository root. Deploy with `scripts/setup_local_splunk.sh`.
