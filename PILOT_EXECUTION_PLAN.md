# Pilot Execution Plan

## Objective

Turn this repository into a successful first pilot by proving that the operator
app can supervise and command a real PLC-backed extruder interface, not just the
simulation.

## Recommended First Pilot Path

Use `OPC UA + TwinCAT` as the primary commissioning path.

Why this path:

- the repo already includes TwinCAT-oriented tags and mapping guidance in
  `plc/twincat/`
- the app already exposes OPC UA diagnostics and node browsing
- this is the shortest route from software MVP to believable plant integration

Keep `modbus` as a secondary path only if the target PLC cannot expose OPC UA.

## Pilot Success Criteria

The pilot is successful when all of the following are true against a real PLC
target or a PLC test bench that mirrors production tags:

1. The app connects in `opcua` mode and reports healthy connection diagnostics.
2. The operator can start, stop, reset, and emergency-stop the machine from the
   app.
3. The app reads live process values from the PLC:
   zone temperatures, die temperature, screw RPM, motor current, feeder rate,
   hopper level, pressure, machine state.
4. The operator can apply a recipe from the app and the PLC reflects the updated
   setpoints.
5. At least one alarm path is verified end-to-end:
   PLC condition -> app alarm visibility -> operator acknowledge.
6. Telemetry is persisted for one full pilot session and a production report can
   be exported afterward.

## Two-Week Plan

### Week 1: Integration Readiness

#### Day 1

- Freeze pilot scope to one use case:
  "Run the operator app against TwinCAT over OPC UA."
- Confirm the target PLC or test bench owner.
- Confirm the exact tag prefix and exported symbols.
- Copy `.env.example` to local runtime config and set:
  `EXTRUDER_PLC_MODE=opcua`
  `EXTRUDER_OPCUA_ENDPOINT=...`
  `EXTRUDER_OPCUA_NODE_PREFIX=...`

Deliverable:

- named pilot owner
- named PLC endpoint
- agreed pilot demo scenario

#### Day 2

- Import or validate the TwinCAT tag layout from `plc/twincat/README.md`.
- Verify the PLC exposes the expected `gExtruder*` symbol surface.
- Run `.\.venv\Scripts\python.exe check_opcua_symbols.py` to validate the
  expected TwinCAT node set against the configured endpoint and prefix.
- Use the app's `GET /api/connection` and `GET /api/connection/browse` endpoints
  to confirm browseability.
- Record every missing, renamed, or differently-typed tag.

Deliverable:

- tag gap list with owner for each mismatch

#### Day 3

- Fix the tag surface on the PLC side or adapter config side until the app can
  read stable status values.
- Validate the following live reads:
  `State`, `RunTime_s`, `ScanNumber`, zone temperatures, die temperature,
  pressure, motor RPM, motor current, feeder rate, hopper level.
- Run the operator panel and confirm the dashboard reflects changing values.

Deliverable:

- live read-only commissioning pass complete

#### Day 4

- Validate control writes from the app:
  `Start`, `Stop`, `Reset`, `EmergencyStop`
- Validate recipe writebacks:
  feed rate, screw RPM, barrel zone setpoints, die setpoint
- Confirm command semantics with the PLC engineer:
  pulse vs maintained bits, edge-trigger behavior, reset behavior

Deliverable:

- successful command/write test sheet

#### Day 5

- Exercise at least 3 fault scenarios in a safe environment:
  simulated over-temperature, pressure/alarm summary, e-stop
- Confirm the app shows alarms, connection health, and recovery state clearly.
- Export one production report and one CSV report from the app.
- Review `runtime_logs/` to confirm telemetry persistence quality.

Deliverable:

- end-to-end dry run complete
- issues list prioritized for pilot week

### Week 2: Pilot and Hardening

#### Day 6

- Fix only pilot-blocking issues from Week 1.
- Do not expand scope into new features.
- Add operator notes for startup, stop, and recovery steps.

Deliverable:

- pilot candidate build

#### Day 7

- Run a supervised pilot session with an operator or PLC engineer.
- Capture:
  connection drops, tag mismatches, command failures, confusing UI moments,
  missing alarms, report usefulness.

Deliverable:

- observed pilot findings log

#### Day 8

- Apply the smallest changes needed to remove friction from Day 7.
- Re-run the same pilot script.
- Confirm no regression in simulation mode or report generation.

Deliverable:

- stable pilot rerun

#### Day 9

- Prepare a short acceptance package:
  screenshots, example report, alarm evidence, connection diagnostics,
  known limitations.
- Decide whether the product is ready for:
  broader plant trial, another pilot loop, or protocol fallback to Modbus.

Deliverable:

- go/no-go recommendation

#### Day 10

- Hold a review based on evidence, not opinions.
- Lock the post-pilot roadmap into three buckets:
  must-fix, should-fix, later.

Deliverable:

- post-pilot roadmap

## Daily Pilot Script

Use the same script every day so progress is measurable:

1. Start the app in `opcua` mode.
2. Check `GET /api/health`.
3. Check `GET /api/connection`.
4. Browse the configured node root with `GET /api/connection/browse`.
5. Confirm live status values on `GET /api/status`.
6. Apply an active recipe.
7. Start the machine.
8. Observe trends and alarms.
9. Stop the machine.
10. Export production report and CSV.

## Non-Negotiable Metrics

Track these during the pilot:

- successful connection rate
- time to first healthy connection
- command acceptance rate
- alarm visibility and acknowledge success
- report export success
- number of manual PLC-side interventions needed

## Risks To Watch Closely

- OPC UA symbol names differ from the expected TwinCAT mapping
- command bits behave differently than the adapter expects
- PLC values are available but units/scaling differ
- operators can see data but do not trust or use the panel
- too much time is spent adding features instead of proving one workflow

## What Not To Do Yet

Avoid these until the first pilot is proven:

- adding advanced analytics beyond the current reporting layer
- supporting both `opcua` and `modbus` in the same pilot
- redesigning the frontend
- expanding the recipe system
- adding AI features before operator workflow is validated

## Recommended Immediate Next Actions

1. Commit to `OPC UA + TwinCAT` as the first pilot path.
2. Identify the real PLC endpoint or a TwinCAT test bench this week.
3. Run the Day 1-Day 2 commissioning steps.
4. Treat every tag mismatch as the main backlog until live reads and writes work.

## Assumptions

- the first success target is a pilot, not a full plant deployment
- TwinCAT is the most likely first PLC environment because the repo already
  includes TwinCAT-oriented assets
- the existing Python tests are sufficient for software baseline confidence and
  the main remaining uncertainty is field integration
