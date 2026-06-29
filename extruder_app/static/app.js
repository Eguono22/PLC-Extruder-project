const state = {
  refreshTimer: null,
  recipes: [],
  meta: null,
};

function $(id) {
  return document.getElementById(id);
}

function setStatus(message, variant = "neutral") {
  const banner = $("commandStatus");
  banner.textContent = message;
  banner.className = `status-banner ${variant}`;
}

function setCommandButtonsEnabled(automation) {
  document.querySelectorAll("[data-command]").forEach((button) => {
    const endpoint = button.dataset.command;
    let enabled = true;
    if (endpoint === "/api/commands/start") {
      enabled = Boolean(automation.can_start);
    } else if (endpoint === "/api/commands/stop") {
      enabled = Boolean(automation.can_stop);
    } else if (endpoint === "/api/commands/reset") {
      enabled = Boolean(automation.can_reset);
    } else if (endpoint === "/api/commands/acknowledge-alarms") {
      enabled = Boolean(automation.active_alarm_count > 0);
    }
    button.disabled = !enabled;
  });
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (response.ok) {
    return response.json();
  }
  let detail = `Request failed: ${response.status}`;
  try {
    const body = await response.json();
    if (body.detail) {
      detail = body.detail;
    }
  } catch (error) {
    // Ignore JSON parse errors and fall back to status-only messaging.
  }
  throw new Error(detail);
}

function formatNumber(value, digits = 1, suffix = "") {
  const numeric = Number(value ?? 0);
  return `${numeric.toFixed(digits)}${suffix}`;
}

function timeAgo(timestamp) {
  if (!timestamp) {
    return "No recent activity";
  }
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - timestamp));
  if (seconds < 5) {
    return "Just now";
  }
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function setBarWidth(id, value, max) {
  const pct = Math.max(6, Math.min(100, (Number(value || 0) / max) * 100));
  $(id).style.width = `${pct}%`;
}

function fillManualRecipeForm(recipe) {
  if (!recipe) {
    return;
  }
  $("feedRateInput").value = recipe.feed_rate_kg_h;
  $("screwRpmInput").value = recipe.screw_rpm;
  const zones = recipe.zone_setpoints.barrel_c || [];
  $("zone1Input").value = zones[0] ?? 0;
  $("zone2Input").value = zones[1] ?? 0;
  $("zone3Input").value = zones[2] ?? 0;
  $("zone4Input").value = zones[3] ?? 0;
  $("dieInput").value = recipe.zone_setpoints.die_c;
}

function renderZones(machine) {
  const zones = machine.heater.zones || [];
  const zoneCards = zones.map((zone) => `
    <article class="zone-card">
      <span class="zone-name">Zone ${zone.zone}</span>
      <strong class="zone-temp">${formatNumber(zone.temperature_c, 1, "°C")}</strong>
      <div class="data-row"><span>Setpoint</span><strong>${formatNumber(zone.setpoint_c, 0, "°C")}</strong></div>
      <div class="data-row"><span>Output</span><strong>${formatNumber(zone.heater_output_pct, 1, "%")}</strong></div>
      <div class="data-row"><span>Status</span><strong>${zone.at_setpoint ? "At setpoint" : "Ramping"}</strong></div>
    </article>
  `);
  zoneCards.push(`
    <article class="zone-card">
      <span class="zone-name">Die</span>
      <strong class="zone-temp">${formatNumber(machine.die.temperature_c, 1, "°C")}</strong>
      <div class="data-row"><span>Setpoint</span><strong>${formatNumber(machine.die.setpoint_c, 0, "°C")}</strong></div>
      <div class="data-row"><span>Pressure</span><strong>${formatNumber(machine.die.melt_pressure_bar, 1, " bar")}</strong></div>
      <div class="data-row"><span>Throughput</span><strong>${formatNumber(machine.die.throughput_kg_h, 1, " kg/h")}</strong></div>
    </article>
  `);
  $("zoneGrid").innerHTML = zoneCards.join("");
}

function renderAlarms(alarms) {
  if (!alarms.length) {
    $("alarmList").innerHTML = `
      <article class="stack-item alarm-clear">
        <div class="title-row"><strong>No active alarms</strong><span class="caption">Clear</span></div>
        <div class="caption">The line is currently free of active machine alarms.</div>
      </article>
    `;
    return;
  }
  $("alarmList").innerHTML = alarms.map((alarm) => `
    <article class="stack-item alarm-${alarm.severity.toLowerCase()}">
      <div class="title-row"><strong>${alarm.code}</strong><span class="caption">${alarm.severity}</span></div>
      <div>${alarm.message}</div>
      <div class="caption">${alarm.acknowledged ? "Acknowledged" : "New"} • ${new Date(alarm.timestamp * 1000).toLocaleString()}</div>
    </article>
  `).join("");
}

function renderEvents(events) {
  if (!events.length) {
    $("eventList").innerHTML = `
      <article class="stack-item">
        <strong>No recent events</strong>
        <div class="caption">Operator actions and system lifecycle events will appear here.</div>
      </article>
    `;
    return;
  }
  $("eventList").innerHTML = events.slice().reverse().map((event) => `
    <article class="stack-item">
      <div class="title-row"><strong>${event.type.replaceAll("_", " ")}</strong><span class="caption">${timeAgo(event.ts)}</span></div>
      <div class="caption mono">${JSON.stringify(event.payload)}</div>
    </article>
  `).join("");
}

function renderBrowse(items) {
  if (!items.length) {
    $("browseList").innerHTML = `
      <article class="stack-item">
        <strong>No child nodes returned</strong>
        <div class="caption">Check the node id or verify PLC symbol exposure.</div>
      </article>
    `;
    return;
  }
  $("browseList").innerHTML = items.map((item) => `
    <article class="stack-item">
      <div class="title-row"><strong>${item.display_name || item.browse_name}</strong><span class="caption">${item.node_class}</span></div>
      <div class="caption mono">${item.node_id}</div>
    </article>
  `).join("");
}

function renderConnection(connection) {
  const online = Boolean(connection.connected);
  const chip = $("connectionChip");
  chip.textContent = online ? "PLC reachable" : "PLC disconnected";
  chip.className = `status-pill ${online ? "" : "alert"}`.trim();
  $("connectionEndpoint").textContent = connection.endpoint || "Not configured";
  $("connectionPrefix").textContent = connection.node_prefix || "n/a";
  $("connectionPoll").textContent = connection.last_poll_succeeded ? "Successful" : "No successful poll yet";
  $("connectionError").textContent = connection.last_error || "No adapter error";
}

function renderAutomation(automation) {
  $("automationMode").textContent = `${automation.supervisory_mode} mode`;
  $("automationMode").className = `status-pill ${automation.auto_sequence_active ? "" : "neutral"}`.trim();
  $("automationPhase").textContent = automation.lifecycle_phase;
  $("automationReady").textContent = automation.ready_for_start ? "Ready" : "Not ready";
  $("automationPermissives").textContent = automation.permissives_ok ? "Healthy" : "Blocked";
  $("automationLink").textContent = automation.plc_connected ? "Connected" : "Offline";
  $("automationNextAction").textContent = automation.next_operator_action;
  $("automationCommands").textContent = [
    automation.can_start ? "Start" : null,
    automation.can_stop ? "Stop" : null,
    automation.can_reset ? "Reset" : null,
    automation.can_apply_recipe ? "Apply recipe" : null,
  ].filter(Boolean).join(" / ") || "No commands currently available";
  $("automationThermal").textContent = automation.heaters_ready && automation.die_ready
    ? "Barrel and die at setpoint"
    : "Warm-up still in progress";
  $("automationAlarmCount").textContent = `${automation.active_alarm_count}`;
  $("automationNotes").innerHTML = (automation.notes || []).map((note) => `
    <article class="stack-item">
      <div class="caption">${note}</div>
    </article>
  `).join("");
  setCommandButtonsEnabled(automation);
}

function renderOperationMode(operationMode) {
  $("operationModeSelect").value = operationMode.mode;
  $("operationModeSelect").disabled = !operationMode.can_change_mode;
  $("applyModeButton").disabled = !operationMode.can_change_mode;
  $("operationModeChangeState").textContent = operationMode.can_change_mode
    ? "Allowed now"
    : "Only in idle or E-stop";
  $("operationModeNotes").innerHTML = (operationMode.notes || []).map((note) => `
    <article class="stack-item">
      <div class="caption">${note}</div>
    </article>
  `).join("");
}

function renderMachine(machine, analytics, runtime) {
  const stateClass = String(machine.state || "unknown").toLowerCase();
  $("machineState").textContent = machine.state;
  $("machineState").className = `state-chip ${stateClass}`;
  $("plcMode").textContent = machine.plc_mode;
  $("throughputValue").textContent = formatNumber(machine.die.throughput_kg_h, 1, " kg/h");
  $("pressureValue").textContent = formatNumber(machine.die.melt_pressure_bar, 1, " bar");
  $("runtimeValue").textContent = formatNumber(machine.run_time_s, 1, " s");
  $("activeRecipeName").textContent = machine.active_recipe.name;
  $("alarmSummary").textContent = machine.alarms;
  $("rpmValue").textContent = formatNumber(machine.motor.actual_rpm, 1, " rpm");
  $("hopperValue").textContent = formatNumber(machine.feeder.hopper_level_pct, 1, " %");
  $("motorCurrentValue").textContent = formatNumber(machine.motor.current_a, 1, " A");

  $("sampleCount").textContent = analytics.total_samples;
  $("avgThroughput").textContent = formatNumber(analytics.avg_throughput_kg_h, 1, " kg/h");
  $("maxPressure").textContent = formatNumber(analytics.max_pressure_bar, 1, " bar");
  $("avgCurrent").textContent = formatNumber(analytics.avg_motor_current_a, 1, " A");
  $("avgDieTemp").textContent = formatNumber(analytics.avg_die_temp_c, 1, " °C");
  $("eventCount").textContent = runtime.event_count;

  $("runtimeState").textContent = runtime.ready ? "Background poller healthy" : "Background poller warming up";
  $("runtimeState").className = `status-pill ${runtime.ready ? "" : "neutral"}`.trim();
  $("lastRefresh").textContent = `Last sample ${timeAgo(runtime.last_sample_ts)}`;

  setBarWidth("rpmBar", machine.motor.actual_rpm, 250);
  setBarWidth("hopperBar", machine.feeder.hopper_level_pct, 100);
  setBarWidth("currentBar", machine.motor.current_a, 120);
  renderZones(machine);
}

async function loadMeta() {
  state.meta = await fetchJson("/api/meta");
  document.title = state.meta.app_name;
  $("appTitle").textContent = state.meta.app_name;
  $("appEnvironment").textContent = `${state.meta.app_environment} • v${state.meta.app_version}`;
}

async function loadRecipes() {
  state.recipes = await fetchJson("/api/recipes");
  const select = $("recipeSelect");
  select.innerHTML = state.recipes.map((recipe) => `
    <option value="${recipe.recipe_id}">${recipe.name}</option>
  `).join("");
  fillManualRecipeForm(state.recipes[0]);
}

async function applyPresetRecipe() {
  const recipeId = $("recipeSelect").value;
  const recipe = state.recipes.find((item) => item.recipe_id === recipeId);
  if (!recipe) {
    return;
  }
  await fetchJson("/api/recipes/active", {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({recipe_id: recipe.recipe_id}),
  });
  fillManualRecipeForm(recipe);
  setStatus(`Applied preset recipe: ${recipe.name}`, "success");
  await refreshDashboard();
}

async function applyManualRecipe(event) {
  event.preventDefault();
  const payload = {
    recipe_id: "custom-web",
    name: "Web Recipe",
    description: "Operator-defined recipe from the production dashboard",
    feed_rate_kg_h: Number($("feedRateInput").value),
    screw_rpm: Number($("screwRpmInput").value),
    zone_setpoints: {
      barrel_c: [
        Number($("zone1Input").value),
        Number($("zone2Input").value),
        Number($("zone3Input").value),
        Number($("zone4Input").value),
      ],
      die_c: Number($("dieInput").value),
    },
  };
  await fetchJson("/api/recipes/active", {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  setStatus("Applied manual setpoints from the dashboard", "success");
  await refreshDashboard();
}

async function sendCommand(endpoint) {
  const result = await fetchJson(endpoint, {method: "POST"});
  setStatus(result.message, "success");
  await refreshDashboard();
}

async function applyOperationMode() {
  const mode = $("operationModeSelect").value;
  const result = await fetchJson("/api/operation-mode", {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode}),
  });
  setStatus(`Switched supervisory mode to ${result.mode}`, "success");
  await refreshDashboard();
}

async function refreshBrowse() {
  const nodeId = $("browseNodeId").value.trim();
  const url = nodeId
    ? `/api/connection/browse?node_id=${encodeURIComponent(nodeId)}`
    : "/api/connection/browse";
  const items = await fetchJson(url);
  renderBrowse(items);
  setStatus(nodeId ? `Browsed PLC node ${nodeId}` : "Browsed default PLC node", "neutral");
}

async function refreshDashboard() {
  const dashboard = await fetchJson("/api/dashboard");
  renderMachine(dashboard.machine, dashboard.analytics, dashboard.runtime);
  renderAutomation(dashboard.automation);
  renderOperationMode(dashboard.operation_mode);
  renderAlarms(dashboard.alarms);
  renderConnection(dashboard.connection);
  renderEvents(dashboard.events);
}

function bindEvents() {
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await sendCommand(button.dataset.command);
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
  });

  $("applyRecipeButton").addEventListener("click", async () => {
    try {
      await applyPresetRecipe();
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  $("recipeSelect").addEventListener("change", (event) => {
    const recipe = state.recipes.find((item) => item.recipe_id === event.target.value);
    fillManualRecipeForm(recipe);
  });

  $("manualRecipeForm").addEventListener("submit", async (event) => {
    try {
      await applyManualRecipe(event);
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  $("browseButton").addEventListener("click", async () => {
    try {
      await refreshBrowse();
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  $("applyModeButton").addEventListener("click", async () => {
    try {
      await applyOperationMode();
    } catch (error) {
      setStatus(error.message, "error");
    }
  });
}

async function boot() {
  bindEvents();
  await loadMeta();
  await loadRecipes();
  await refreshDashboard();
  await refreshBrowse();
  setStatus("Dashboard connected to extruder services", "success");
  state.refreshTimer = window.setInterval(async () => {
    try {
      await refreshDashboard();
    } catch (error) {
      setStatus(error.message, "error");
    }
  }, state.meta.dashboard_refresh_ms);
}

boot().catch((error) => {
  setStatus(error.message, "error");
});
