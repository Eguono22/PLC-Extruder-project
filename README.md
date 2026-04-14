# PLC-Extruder-project

Industrial extruder operation platform that automates the complete extrusion process—from material feeding and barrel heating to melting, mixing, and shaping—while ensuring precise control, safety, and consistent product quality.

---

## System Overview

The platform is managed through the **TwinCon** HMI/SCADA software and communicates with the PLC over a live connection (Visu communication OK / PLC connection OK).

### Feeder & Conveying Subsystems

The system controls up to **9 feeders** that supply material to the extruder and two side feeders:

| Feeder | Actual Flow [kg/h] | Nom. Flow [kg/h] | Weight [kg] | Notes |
|--------|--------------------|-------------------|-------------|-------|
| 1      | 0.0                | 0.0               | 0.0         | Inactive |
| 2      | 74.2               | 74.2              | 22.6        | Active |
| 3      | 45.8               | 45.8              | 12.9        | Active |
| 4      | 0.0                | 0.0               | 0.9         | Inactive |
| 5      | 77.7               | 77.7              | 68.9        | Active |
| 6      | 294.4              | 294.4             | 58.8        | Active |
| 7      | 0.0                | 0.0               | 1.3         | Inactive |
| 8      | 122.9              | 122.9             | 39.0        | Active (Side Feeder 1) |
| 9      | 0.0                | 0.0               | 0.0         | Inactive (Side Feeder 2) |

**Conveying Grinder** operates with two stations (Station 1 and Station 2). Station 2 is active (green).

**Manual Dosing Premix**: Nominal Value 0.00 kg, Actual Value 0.00 kg. Weigher state: *Weigher Empty*.

**Aspiration systems** (Coat/Ext and 7-8-9) are both set to **On**.

---

## Alarm & Fault Log

Alarms are logged with date, time, state, PLC data block tag, stamp code, and a plain-language comment. All listed alarms have been **acknowledged (ACK)**.

| Date     | Time     | State | Tag          | Stamp   | Description                              |
|----------|----------|-------|--------------|---------|------------------------------------------|
| 14/04/26 | 02:20:48 | ACK   | DB9_X31_5    | 33-10A1 | Extruder Heating Zone 5 Current Monitoring |
| 14/04/26 | 02:18:37 | ACK   | DB9_X187_0   | 14-3B1  | Debag. Station 8 Hopper Empty            |
| 14/04/26 | 02:13:27 | ACK   | DB9_X158_0   | 10-3B1  | Debag. Station 3 Hopper Empty            |
| 13/04/26 | 23:43:21 | ACK   | DB9_X175_0   | 12-3B1  | Debag. Station 6 Hopper Empty            |
| 13/04/26 | 22:37:12 | ACK   | DB9_X229_0   | ON      | Grind. Station 2 Hopper Weight Level Low |
| 13/04/26 | 14:40:30 | ACK   | DB9_X77_7    | 20-10A1 | Feeder 7 Fault Spare                     |
| 13/04/26 | 14:40:30 | ACK   | DB9_X74_7    | 20-7A1  | Feeder 4 Fault Spare                     |
| 13/04/26 | 14:40:30 | ACK   | DB9_X71_7    | 20-4A1  | Feeder 1 Fault Spare                     |
| 25/03/26 | 16:30:07 | ACK   | DB9_X246_0   | 42-27B1 | Polybuteen Refill Valve Monitoring Fault |
| 13/03/26 | 06:16:33 | ACK   | DB9_X244_0   | 42-24B1 | Bitum Day B05 Tank Level HH              |

> **Note**: Feeder 1, 4, and 7 faults coincide with those feeders showing 0.0 kg/h actual flow in the overview.

---

## Temperature Monitoring

### Trend View – Zones 1–8

The **Trends** screen plots actual temperature [°C] over time for extruder heating zones 1–8. The chart covers an 8-minute window (approximately 03:06–03:14 on 14/04/26).

| Zone | Approx. Actual Temp [°C] | Colour in trend |
|------|--------------------------|-----------------|
| 1    | ~192                     | Cyan            |
| 2    | ~130 (mid-range)         | White           |
| 3    | ~130 (mid-range)         | Yellow          |
| 4    | ~130 (mid-range)         | Orange          |
| 5    | ~115–120                 | Pink/Magenta    |
| 6    | ~115–120                 | Purple/Blue     |
| 7    | ~115–120                 | Red             |
| 8    | ~14–39 (ambient/cool)    | Green           |

Temperatures are stable throughout the trend window, indicating steady-state production conditions.

---

## Heating Zone Parameters – Zones 12–18

These zones cover the **Divert Valve** (12–15), **Melt Pump** (16), and **Pipe to Coatinghead** (17–18).

| Zone | Area               | Nom. [°C] | Act. [°C] | Output [%] | Recipe [°C] | Warning Min [°C] | Warning Max [°C] |
|------|--------------------|-----------|-----------|------------|-------------|------------------|------------------|
| 12   | Divert Valve       | —         | —         | —          | —           | —                | —                |
| 13   | Divert Valve       | 130       | 157       | 0          | 130         | 100              | 200              |
| 14   | Divert Valve       | 130       | 130       | 1          | 130         | 100              | 200              |
| 15   | Divert Valve       | 130       | 151       | 0          | 130         | 100              | 200              |
| 16   | Melt Pump          | 130       | 161       | 0          | 130         | 100              | 200              |
| 17   | Pipe to Coatinghead| 175       | 177       | 0          | 150         | 120              | 200              |
| 18   | Pipe to Coatinghead| 175       | 175       | 31         | 150         | 120              | 200              |

**Heating state**: On (Zone 12 indicator is green).

**Observations**:
- Zones 13, 15, and 16 show actual temperatures above their nominal setpoints (157 °C, 151 °C, and 161 °C respectively vs. 130 °C nominal). Heater outputs are 0%, meaning no active heating — the zones are retaining residual heat.
- Zone 14 is at exactly the 130 °C setpoint with 1% output.
- Zones 17–18 are near the 175 °C setpoint. Zone 18 is actively heating at 31% output.
- All zones are within their warning limits (min 100 °C / 120 °C, max 200 °C).

---

## Operational Summary (14/04/2026 ~03:15)

- **Active feeders**: 2, 3, 5, 6, 8 — total throughput approximately **615 kg/h** to the extruder and side feeder.
- **Inactive feeders**: 1, 4, 7, 9 — faulted or not in use.
- **Outstanding alarm**: Extruder Heating Zone 5 Current Monitoring (DB9_X31_5, logged 02:20:48, acknowledged).
- **Temperatures**: Steady across all zones; Zones 13/15/16 slightly above setpoint but decreasing passively (0% output).
- **Aspiration**: All aspiration systems running (Coat/Ext On, 7-8-9 On).
