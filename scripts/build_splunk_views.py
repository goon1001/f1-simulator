#!/usr/bin/env python3
"""Generate the F1 Dashboard Studio v2 views from tested v6 collector fields."""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "splunk/f1_driver_telemetry/default/data/ui/views"
INDEX = "index=data_drivers_f1_2025 source=f1_2025"
TIME = {"earliest": "$global_time.earliest$", "latest": "$global_time.latest$"}


def search(query: str) -> dict:
    return {
        "type": "ds.search",
        "options": {"query": query, "queryParameters": TIME},
    }


def markdown(text: str) -> dict:
    return {
        "type": "splunk.markdown",
        "options": {"markdown": text, "backgroundColor": "transparent"},
    }


def single(data_source: str, color: str) -> dict:
    return {
        "type": "splunk.singlevalue",
        "dataSources": {"primary": data_source},
        "options": {
            "majorColor": color,
            "backgroundColor": "transparent",
            "sparklineDisplay": "off",
            "trendDisplay": "off",
        },
    }


def chart(kind: str, data_source: str) -> dict:
    return {
        "type": f"splunk.{kind}",
        "dataSources": {"primary": data_source},
        "options": {"backgroundColor": "transparent"},
    }


def block(item: str, x: int, y: int, w: int, h: int) -> dict:
    return {"item": item, "type": "block", "position": {"x": x, "y": y, "w": w, "h": h}}


def common(title: str, subtitle: str) -> tuple[dict, dict, list[dict]]:
    visualizations = {
        "viz_header": markdown(f"# {title}\n{subtitle}"),
        "viz_nav": markdown(
            "[LIVE TELEMETRY](/app/f1_driver_telemetry/f1_live_telemetry) &nbsp; | &nbsp; "
            "[LAP COMPARISON](/app/f1_driver_telemetry/f1_lap_comparison) &nbsp; | &nbsp; "
            "[RESULTS & HEALTH](/app/f1_driver_telemetry/f1_results_health)"
        ),
    }
    inputs = {
        "input_time": {
            "type": "input.timerange",
            "title": "Time range",
            "options": {"token": "global_time", "defaultValue": "-24h,now"},
        },
        "input_mode": {
            "type": "input.dropdown",
            "title": "Data mode",
            "options": {
                "token": "tok_mode",
                "defaultValue": "*",
                "items": [
                    {"label": "Live + playback", "value": "*"},
                    {"label": "Live only", "value": "live"},
                    {"label": "Playback only", "value": "playback"},
                ],
            },
        },
    }
    structure = [block("viz_header", 24, 20, 960, 80), block("viz_nav", 1000, 34, 416, 54)]
    return visualizations, inputs, structure


def write_view(
    name: str,
    title: str,
    description: str,
    data_sources: dict,
    visualizations: dict,
    inputs: dict,
    structure: list[dict],
    height: int,
) -> None:
    definition = {
        "title": title,
        "description": description,
        "dataSources": data_sources,
        "defaults": {},
        "visualizations": visualizations,
        "inputs": inputs,
        "layout": {
            "type": "absolute",
            "options": {
                "width": 1440,
                "height": height,
                "display": "auto-scale",
                "backgroundColor": "#0B0F14",
            },
            "structure": structure,
            "globalInputs": ["input_time", "input_mode"],
        },
    }
    xml = (
        '<dashboard version="2" theme="dark">\n'
        f"  <label>{escape(title)}</label>\n"
        f"  <description>{escape(description)}</description>\n"
        "  <definition><![CDATA[\n"
        f"{json.dumps(definition, indent=2)}\n"
        "  ]]></definition>\n"
        "</dashboard>\n"
    )
    VIEWS.mkdir(parents=True, exist_ok=True)
    (VIEWS / f"{name}.xml").write_text(xml)


def live_view() -> None:
    title = "F1 Driver Telemetry — Live"
    visualizations, inputs, structure = common(
        title, "F1 25 · v6 collector · 10 Hz driver telemetry"
    )
    data_sources = {
        "ds_driver": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| stats latest(player_name) as value"
        ),
        "ds_speed": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| stats latest(speed) as value"
        ),
        "ds_rpm": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| stats latest(engine_rpm) as value"
        ),
        "ds_lap": search(
            f"{INDEX} sourcetype=LapData data_mode=$tok_mode$ "
            "| stats latest(current_lap_num) as value"
        ),
        "ds_speed_trace": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            '| timechart span=1s avg(speed) as "Speed (km/h)"'
        ),
        "ds_controls": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| eval throttle_pct=round(throttle*100,1), brake_pct=round(brake*100,1) "
            '| timechart span=1s avg(throttle_pct) as "Throttle %" avg(brake_pct) as "Brake %"'
        ),
        "ds_tyre_temperature": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| eval front_temp=round((tyres_surface_temperature_fl+tyres_surface_temperature_fr)/2,1), "
            "rear_temp=round((tyres_surface_temperature_rl+tyres_surface_temperature_rr)/2,1) "
            '| timechart span=2s avg(front_temp) as "Front tyres °C" avg(rear_temp) as "Rear tyres °C"'
        ),
        "ds_gforce": search(
            f"{INDEX} sourcetype=MotionData data_mode=$tok_mode$ "
            '| timechart span=1s avg(g_force_lateral) as "Lateral G" '
            'avg(g_force_longitudinal) as "Longitudinal G"'
        ),
        "ds_status": search(
            f"{INDEX} sourcetype=CarStatusData data_mode=$tok_mode$ "
            "| stats latest(player_name) as Driver latest(rig_name) as Rig "
            "latest(ers_store_energy) as ERS_J latest(fuel_in_tank) as Fuel_kg "
            "latest(fuel_remaining_laps) as Fuel_laps latest(tyres_age_laps) as Tyre_age "
            "latest(drs_allowed) as DRS_allowed latest(engine_power_ice) as ICE_W "
            "| eval \"ERS %\"=round(ERS_J/4000000*100,1), \"Fuel kg\"=round(Fuel_kg,2), "
            "\"Fuel laps\"=round(Fuel_laps,2), \"ICE kW\"=round(ICE_W/1000,1) "
            '| table Driver Rig "ERS %" "Fuel kg" "Fuel laps" Tyre_age DRS_allowed "ICE kW"'
        ),
    }
    visualizations.update(
        {
            "viz_driver": single("ds_driver", "#FF8000"),
            "viz_speed": single("ds_speed", "#47C7FC"),
            "viz_rpm": single("ds_rpm", "#F5C451"),
            "viz_lap": single("ds_lap", "#8BE28B"),
            "viz_speed_trace": chart("line", "ds_speed_trace"),
            "viz_controls": chart("area", "ds_controls"),
            "viz_tyre_temperature": chart("line", "ds_tyre_temperature"),
            "viz_gforce": chart("line", "ds_gforce"),
            "viz_status": chart("table", "ds_status"),
        }
    )
    structure += [
        block("viz_driver", 24, 120, 330, 130),
        block("viz_speed", 378, 120, 330, 130),
        block("viz_rpm", 732, 120, 330, 130),
        block("viz_lap", 1086, 120, 330, 130),
        block("viz_speed_trace", 24, 276, 686, 280),
        block("viz_controls", 734, 276, 682, 280),
        block("viz_tyre_temperature", 24, 580, 686, 270),
        block("viz_gforce", 734, 580, 682, 270),
        block("viz_status", 24, 874, 1392, 210),
    ]
    write_view(
        "f1_live_telemetry",
        title,
        "Current speed, controls, tyre temperatures, G force, ERS and fuel.",
        data_sources,
        visualizations,
        inputs,
        structure,
        1110,
    )


def comparison_view() -> None:
    title = "F1 Driver Telemetry — Lap Comparison"
    visualizations, inputs, structure = common(
        title, "Compare attempts, laps, pace, position and control traces"
    )
    data_sources = {
        "ds_best_lap": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ best_lap_time_in_ms>0 "
            "| dedup record_id | stats min(best_lap_time_in_ms) as best_ms "
            "| eval value=round(best_ms/1000,3) | table value"
        ),
        "ds_top_speed": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| stats max(speed) as value"
        ),
        "ds_attempts": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ "
            "| dedup record_id | stats dc(attempt_id) as value"
        ),
        "ds_lap_times": search(
            f"{INDEX} sourcetype=LapData data_mode=$tok_mode$ last_lap_time_in_ms>0 "
            "| stats latest(last_lap_time_in_ms) as lap_ms by attempt_id player_name current_lap_num "
            "| eval Lap=current_lap_num-1, lap_seconds=round(lap_ms/1000,3) "
            "| chart min(lap_seconds) over Lap by player_name"
        ),
        "ds_position": search(
            f"{INDEX} sourcetype=LapData data_mode=$tok_mode$ "
            '| timechart span=2s latest(car_position) as Position by player_name'
        ),
        "ds_speed_distance": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| fields attempt_id frame_identifier player_name speed "
            "| join type=inner attempt_id frame_identifier [ search "
            f"{INDEX} sourcetype=LapData data_mode=$tok_mode$ "
            "| fields attempt_id frame_identifier lap_distance ] "
            "| bin lap_distance span=100 "
            "| chart avg(speed) over lap_distance by player_name"
        ),
        "ds_results": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ best_lap_time_in_ms>0 "
            "| dedup record_id | eval \"Best lap (s)\"=round(best_lap_time_in_ms/1000,3), "
            "\"Race time (s)\"=round(total_race_time,3) "
            "| sort 0 best_lap_time_in_ms "
            '| table player_name data_mode rig_name position grid_position "Best lap (s)" '
            '"Race time (s)" num_laps num_penalties'
        ),
    }
    visualizations.update(
        {
            "viz_best_lap": single("ds_best_lap", "#FF8000"),
            "viz_top_speed": single("ds_top_speed", "#47C7FC"),
            "viz_attempts": single("ds_attempts", "#8BE28B"),
            "viz_lap_times": chart("column", "ds_lap_times"),
            "viz_position": chart("line", "ds_position"),
            "viz_speed_distance": chart("line", "ds_speed_distance"),
            "viz_results": chart("table", "ds_results"),
        }
    )
    structure += [
        block("viz_best_lap", 24, 120, 440, 130),
        block("viz_top_speed", 500, 120, 440, 130),
        block("viz_attempts", 976, 120, 440, 130),
        block("viz_lap_times", 24, 276, 686, 300),
        block("viz_position", 734, 276, 682, 300),
        block("viz_speed_distance", 24, 600, 1392, 300),
        block("viz_results", 24, 924, 1392, 250),
    ]
    write_view(
        "f1_lap_comparison",
        title,
        "Attempt-level lap, speed and race-result comparison.",
        data_sources,
        visualizations,
        inputs,
        structure,
        1200,
    )


def health_view() -> None:
    title = "F1 Driver Telemetry — Results & Health"
    visualizations, inputs, structure = common(
        title, "Race results, ingestion freshness, delivery queue and packet volume"
    )
    data_sources = {
        "ds_events": search(
            f"{INDEX} data_mode=$tok_mode$ | stats count as value"
        ),
        "ds_freshness": search(
            f"{INDEX} sourcetype=CarTelemetryData data_mode=$tok_mode$ "
            "| stats latest(_time) as last | eval value=round(now()-last,1) | table value"
        ),
        "ds_results_count": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ "
            "| dedup record_id | stats count as value"
        ),
        "ds_best": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ best_lap_time_in_ms>0 "
            "| dedup record_id | stats min(best_lap_time_in_ms) as best "
            "| eval value=round(best/1000,3) | table value"
        ),
        "ds_volume": search(
            f"{INDEX} data_mode=$tok_mode$ "
            "| timechart span=1m count by sourcetype limit=10"
        ),
        "ds_modes": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ "
            "| dedup record_id | stats count by data_mode"
        ),
        "ds_delivery": search(
            f"{INDEX} sourcetype=CollectorHealth destination=hec "
            "| stats latest(enabled) as Enabled latest(http_status) as HTTP "
            "latest(pending_batches) as Pending_batches latest(pending_bytes) as Pending_bytes "
            "latest(oldest_seconds) as Oldest_seconds latest(last_latency_ms) as Last_latency_ms "
            "latest(error_category) as Error by collector_id destination"
        ),
        "ds_health_trend": search(
            f"{INDEX} sourcetype=CollectorHealth destination=hec "
            '| timechart span=1m max(pending_batches) as "Pending batches" '
            'avg(last_latency_ms) as "Delivery latency ms"'
        ),
        "ds_sourcetypes": search(
            f"{INDEX} data_mode=$tok_mode$ "
            "| stats count latest(_time) as latest by sourcetype "
            '| eval Freshness=round(now()-latest,1) | rename count as Events sourcetype as Sourcetype '
            "| sort - Events | table Sourcetype Events Freshness"
        ),
        "ds_results": search(
            f"{INDEX} sourcetype=SessionCompleted data_mode=$tok_mode$ "
            "| dedup record_id | eval \"Best lap (s)\"=round(best_lap_time_in_ms/1000,3), "
            "\"Race time (s)\"=round(total_race_time,3) "
            "| sort 0 best_lap_time_in_ms "
            '| table player_name data_mode custom_event rig_name position grid_position '
            '"Best lap (s)" "Race time (s)" completion_source'
        ),
    }
    visualizations.update(
        {
            "viz_events": single("ds_events", "#47C7FC"),
            "viz_freshness": single("ds_freshness", "#F5C451"),
            "viz_results_count": single("ds_results_count", "#8BE28B"),
            "viz_best": single("ds_best", "#FF8000"),
            "viz_volume": chart("line", "ds_volume"),
            "viz_modes": chart("pie", "ds_modes"),
            "viz_delivery": chart("table", "ds_delivery"),
            "viz_health_trend": chart("line", "ds_health_trend"),
            "viz_sourcetypes": chart("table", "ds_sourcetypes"),
            "viz_results": chart("table", "ds_results"),
        }
    )
    structure += [
        block("viz_events", 24, 120, 330, 130),
        block("viz_freshness", 378, 120, 330, 130),
        block("viz_results_count", 732, 120, 330, 130),
        block("viz_best", 1086, 120, 330, 130),
        block("viz_volume", 24, 276, 916, 290),
        block("viz_modes", 964, 276, 452, 290),
        block("viz_delivery", 24, 590, 686, 230),
        block("viz_health_trend", 734, 590, 682, 230),
        block("viz_sourcetypes", 24, 844, 686, 300),
        block("viz_results", 734, 844, 682, 300),
    ]
    write_view(
        "f1_results_health",
        title,
        "Completed attempts and the collector-to-HEC delivery pipeline.",
        data_sources,
        visualizations,
        inputs,
        structure,
        1170,
    )


def main() -> None:
    live_view()
    comparison_view()
    health_view()
    print(f"Generated 3 views in {VIEWS}")


if __name__ == "__main__":
    main()
