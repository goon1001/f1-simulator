---
title: "Local Podman and Splunk Enterprise"
linkTitle: "Podman and Splunk"
weight: 25
type: "docs"
---

This repository includes a tested Apple Silicon path from the native ARM64 v6.0.5 collector to an existing Splunk Enterprise 10.2.2 Podman container. It creates a dedicated index and HEC input, then deploys three Dashboard Studio views.

v6.0.5 is still described as field-testing software. Prove playback, UDP reception and Final Classification before using it at an event.

## Architecture

```text
F1 25 or bundled playback
  -> UDP 20777-20780
  -> f1-2025 collector (native ARM64, persistent /data)
  -> private f1-telemetry Podman network
  -> splunk-dev:8088 (dedicated HEC token)
  -> data_drivers_f1_2025
  -> F1 Driver Telemetry dashboards
```

The collector UI is bound to `127.0.0.1:8501`. UDP is bound to the Mac so a racing rig on the trusted LAN can send telemetry. Splunk Web, HEC and management remain bound to loopback.

## Prerequisites

- Podman is already installed and has a `podman-machine-default` machine.
- The existing Splunk container is named `splunk-dev`.
- Its runtime configuration is at `~/.splunk-podman/.env`.
- Python 3, `curl`, `tar`, `uuidgen` and OpenSSL are available.

No additional local software is installed by this workflow.

## Start the collector

```sh
cp podman/.env.example podman/.env
./podman/f1ctl start
./podman/f1ctl status
```

The runtime uses the v6.0.5 ARM64 child manifest by digest, drops all capabilities, enables `no-new-privileges`, uses a read-only root filesystem and persists `/data` in `f1-v6-data`.

Useful operations:

```sh
./podman/f1ctl logs
./podman/f1ctl restart
./podman/f1ctl stop
```

Stopping retains collector configuration, queues, results and recordings.

## Configure Splunk

Generate the dashboards, deploy the app, create the index and dedicated HEC input, then configure the collector:

```sh
python3 scripts/build_splunk_views.py
./scripts/setup_local_splunk.sh
```

Runtime credentials are never written to the repository:

- The existing Splunk password is read from `~/.splunk-podman/.env`.
- A dedicated F1 HEC token is generated in `~/.f1-simulator/local.env` with mode `0600`.
- The collector stores its destination token in the named `/data` volume.
- `.env`, local Splunk configuration, recordings and generated packages are ignored.

The local Splunk HEC endpoint uses its generated certificate. The setup enables the collector's local-only unverified-certificate compatibility option because the certificate is not trusted by the collector and its name does not match `splunk-dev`. Do not copy that exception to a remote or production endpoint. Install a trusted certificate there instead.

## Prove ingestion with playback

1. Open `http://127.0.0.1:8501`.
2. Open **Recordings → Playback**.
3. Choose either bundled Austria recording.
4. Choose Rig 1, enter a driver name and select **Start playback**.
5. Let the approximately four-minute replay reach Final Classification.
6. Confirm HEC is Connected and its queue returns to zero.

Playback events have `data_mode=playback`. A completed attempt emits `SessionCompleted`; delivery is at least once, so leaderboard SPL deduplicates by `record_id`.

The verified v6 packet sourcetypes include `CarTelemetryData`, `LapData`, `MotionData`, `CarStatusData`, `SessionHistoryData`, `FinalClassificationData` and `SessionCompleted`. Collector health uses `SplunkData` and `CollectorHealth`.

## Open the dashboards

- `http://127.0.0.1:8000/app/f1_driver_telemetry/f1_live_telemetry`
- `http://127.0.0.1:8000/app/f1_driver_telemetry/f1_lap_comparison`
- `http://127.0.0.1:8000/app/f1_driver_telemetry/f1_results_health`

Each view has a time range and a Live, Playback or combined data-mode filter.

## Connect a live F1 25 rig

Find the Mac's LAN address and configure F1 25:

- UDP Telemetry: On
- UDP Broadcast Mode: Off
- UDP IP Address: the Mac's LAN address
- UDP Port: `20777` for Rig 1
- UDP Send Rate: 10 Hz
- UDP Format: 2025
- Your Telemetry: Restricted

In the collector, confirm **Listener · On**, enter the driver and select **Ready** before the first starting light. Run through Final Classification. A valid live result has `data_mode=live`.

The local tests prove UDP reaches the collector through both loopback and the Mac's LAN address. A separate rig still requires a pre-event network and host-firewall test on the actual LAN.

## Validate

```sh
python3 scripts/verify_local.py
python3 scripts/validate_dashboard_spl.py
./scripts/smoke_test.sh
```

The checks validate app structure, Dashboard Studio JSON/XML, canvas bounds, image pinning, secret hygiene, all dashboard SPL, deployed view metadata, collector health and indexed F1 events.

## Upgrade and rollback

Do not replace the pinned image during an active attempt. Finish assigned races, confirm the HEC queue is empty, stop gracefully and retain `f1-v6-data`.

Before adopting a newer release:

1. Resolve and review its ARM64 manifest digest.
2. Update both `podman/compose.yaml` and `podman/f1ctl`.
3. Run both bundled playbacks.
4. Re-run every validation command.
5. Test UDP from the real rig.

Rollback by restoring the previous image digest and restarting. Reusing `f1-v6-data` preserves collector state; do not delete the volume.

## Troubleshooting

- `splunk-dev was not found`: start or restore the existing Podman Splunk instance.
- HEC retries: verify the private `f1-telemetry` network, token, index and `https://splunk-dev:8088`.
- Empty dashboard: use Playback mode, a time range containing the replay and confirm `data_drivers_f1_2025` has events.
- No live UDP: test the Mac LAN address and UDP `20777`; do not use `localhost` from another computer.
- No completed result: the driver must be Ready before STLG 1 and the game must reach Final Classification.
