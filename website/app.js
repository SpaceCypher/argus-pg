/* ==========================================================================
   ARGUS-PG INTERACTIVE SIMULATOR & TELEMETRY ENGINE
   ========================================================================== */

// 1. Preset Database Workloads for Interactive Sandbox Simulator
const PRESET_WORKLOADS = {
  orders: {
    name: "Multi-Column Filter + Sort",
    table: "orders (50,000 rows)",
    sql: `SELECT id, customer_id, total_cents, status, created_at
FROM orders
WHERE customer_id = 4289 
  AND status = 'pending_settlement'
ORDER BY created_at DESC 
LIMIT 25;`,
    recommendedIndex: "CREATE INDEX CONCURRENTLY idx_orders_cust_status ON orders (customer_id, status, created_at DESC);",
    baseline: {
      type: "Seq Scan",
      cost: "2,418.50",
      executionTime: "18.42 ms",
      sharedHit: "1,240 blocks",
      rowsDiscarded: "49,975 rows (99.95%)",
      planLine: "- Seq Scan on orders (cost=0.00..2418.50 rows=25 width=64)"
    },
    optimized: {
      type: "Index Scan",
      cost: "4.82",
      executionTime: "0.19 ms",
      sharedHit: "4 blocks",
      rowsDiscarded: "0 rows (0%)",
      planLine: "+ Index Scan using idx_orders_cust_status on orders (cost=0.42..4.82 rows=25 width=64)"
    },
    speedup: "96.9x",
    reductionPct: "99.8%",
    status: "PASS_VERIFIED"
  },
  users: {
    name: "Unique Email & Auth Lookup",
    table: "users (100,000 rows)",
    sql: `SELECT id, email, full_name, role, password_hash
FROM users
WHERE email = 'dev.architect@enterprise.io';`,
    recommendedIndex: "CREATE INDEX CONCURRENTLY idx_users_email ON users (email);",
    baseline: {
      type: "Seq Scan",
      cost: "4.46",
      executionTime: "367.42 ms",
      sharedHit: "2,890 blocks",
      rowsDiscarded: "99,999 rows (99.99%)",
      planLine: "- Seq Scan on users (cost=0.00..4.46 rows=1 width=146)"
    },
    optimized: {
      type: "Index Scan",
      cost: "0.05",
      executionTime: "4.45 ms",
      sharedHit: "3 blocks",
      rowsDiscarded: "0 rows (0%)",
      planLine: "+ Index Scan using idx_users_email on users (cost=0.00..0.05 rows=1 width=146)"
    },
    speedup: "82.3x",
    reductionPct: "98.8%",
    status: "PASS_VERIFIED"
  },
  jsonb: {
    name: "JSONB Event Telemetry",
    table: "audit_logs (250,000 rows)",
    sql: `SELECT event_id, recorded_at, metadata
FROM audit_logs
WHERE metadata->>'action' = 'stripe_payment_failed'
  AND (metadata->>'amount_cents')::int > 50000;`,
    recommendedIndex: "CREATE INDEX CONCURRENTLY idx_audit_action_amt ON audit_logs ((metadata->>'action'), ((metadata->>'amount_cents')::int));",
    baseline: {
      type: "Seq Scan",
      cost: "8,920.00",
      executionTime: "412.10 ms",
      sharedHit: "6,400 blocks",
      rowsDiscarded: "249,820 rows (99.93%)",
      planLine: "- Seq Scan on audit_logs (cost=0.00..8920.00 rows=180 width=210)"
    },
    optimized: {
      type: "Bitmap Index Scan",
      cost: "14.20",
      executionTime: "2.15 ms",
      sharedHit: "12 blocks",
      rowsDiscarded: "0 rows (0%)",
      planLine: "+ Bitmap Index Scan on idx_audit_action_amt (cost=0.00..14.20 rows=180 width=210)"
    },
    speedup: "191.6x",
    reductionPct: "99.8%",
    status: "PASS_VERIFIED"
  }
};

let currentPresetKey = 'orders';
let isSimulating = false;

// 2. Initialize DOM elements and Listeners
document.addEventListener('DOMContentLoaded', () => {
  initTelemetryCanvas();
  initPresetTabs();
  initSimulatorButton();
  initClipboardButtons();
  loadPreset(currentPresetKey);
});

// 3. Preset Tab Handlers
function initPresetTabs() {
  const tabs = document.querySelectorAll('.query-preset-tabs .tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      if (isSimulating) return;
      const target = tab.getAttribute('data-preset');
      if (target && PRESET_WORKLOADS[target]) {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentPresetKey = target;
        loadPreset(target);
      }
    });
  });
}

function loadPreset(key) {
  const preset = PRESET_WORKLOADS[key];
  if (!preset) return;

  const sqlEditor = document.getElementById('lab-sql-display');
  if (sqlEditor) sqlEditor.textContent = preset.sql;

  const tableLabel = document.getElementById('lab-target-table');
  if (tableLabel) tableLabel.textContent = `Target: ${preset.table}`;

  // Reset steps
  resetSteps();

  // Populate Proof Panel with initial ready state
  updateProofResults(preset);
}

function resetSteps() {
  const stepCards = document.querySelectorAll('.stepper-pipeline .step-card');
  stepCards.forEach((card, index) => {
    card.classList.remove('active', 'done');
    const indicator = card.querySelector('.step-indicator');
    if (indicator) indicator.textContent = (index + 1).toString();
  });
}

// 4. Sandbox Simulation Engine
function initSimulatorButton() {
  const runBtn = document.getElementById('btn-run-sandbox');
  if (!runBtn) return;

  runBtn.addEventListener('click', async () => {
    if (isSimulating) return;
    isSimulating = true;
    runBtn.disabled = true;
    runBtn.innerHTML = `<svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg> Sandbox Executing...`;

    const stepCards = document.querySelectorAll('.stepper-pipeline .step-card');
    const preset = PRESET_WORKLOADS[currentPresetKey];

    // Step 1: Introspect Catalog
    await activateStep(stepCards[0], 400);

    // Step 2: Spawn Ephemeral Docker Twin
    await activateStep(stepCards[1], 500);

    // Step 3: Hydrate 50k Synthetic Rows
    await activateStep(stepCards[2], 600);

    // Step 4: Run Baseline EXPLAIN ANALYZE vs Candidate Index
    await activateStep(stepCards[3], 700);

    // Step 5: Verification Gate Passed
    await activateStep(stepCards[4], 300);

    // Update Result Panel with Verified Data
    updateProofResults(preset, true);
    showToast(`✓ Sandbox verified ${preset.speedup} speedup for ${preset.name}!`);

    runBtn.disabled = false;
    runBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Sandbox Experiment`;
    isSimulating = false;
  });
}

function activateStep(card, delayMs) {
  return new Promise((resolve) => {
    card.classList.add('active');
    setTimeout(() => {
      card.classList.remove('active');
      card.classList.add('done');
      const indicator = card.querySelector('.step-indicator');
      if (indicator) indicator.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
      resolve();
    }, delayMs);
  });
}

function updateProofResults(preset, isLiveRun = false) {
  const speedupNumber = document.getElementById('proof-speedup-num');
  const reductionBadge = document.getElementById('proof-reduction-badge');
  const diffDel = document.getElementById('proof-diff-del');
  const diffAdd = document.getElementById('proof-diff-add');
  const ddlSnippet = document.getElementById('proof-ddl-snippet');

  const baselineTime = document.getElementById('val-baseline-time');
  const optimizedTime = document.getElementById('val-optimized-time');
  const baselineCost = document.getElementById('val-baseline-cost');
  const optimizedCost = document.getElementById('val-optimized-cost');
  const rowsFiltered = document.getElementById('val-rows-filtered');
  const bufferHits = document.getElementById('val-buffer-hits');

  if (speedupNumber) speedupNumber.textContent = preset.speedup;
  if (reductionBadge) reductionBadge.textContent = `${preset.reductionPct} Cost Reduction`;
  if (diffDel) diffDel.textContent = preset.baseline.planLine;
  if (diffAdd) diffAdd.textContent = preset.optimized.planLine;
  if (ddlSnippet) ddlSnippet.textContent = preset.recommendedIndex;

  if (baselineTime) baselineTime.textContent = preset.baseline.executionTime;
  if (optimizedTime) optimizedTime.textContent = preset.optimized.executionTime;
  if (baselineCost) baselineCost.textContent = preset.baseline.cost;
  if (optimizedCost) optimizedCost.textContent = preset.optimized.cost;
  if (rowsFiltered) rowsFiltered.textContent = preset.baseline.rowsDiscarded;
  if (bufferHits) bufferHits.textContent = `${preset.baseline.sharedHit} → ${preset.optimized.sharedHit}`;
}

// 5. Toast Notification System
function showToast(message) {
  let toast = document.getElementById('system-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'system-toast';
    toast.className = 'toast-notice';
    document.body.appendChild(toast);
  }
  toast.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> <span>${message}</span>`;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3500);
}

// 6. Clipboard Copy Engine
function initClipboardButtons() {
  document.querySelectorAll('[data-copy-target]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const targetId = btn.getAttribute('data-copy-target');
      const textToCopy = btn.getAttribute('data-copy-text') || (document.getElementById(targetId)?.textContent ?? "");
      
      if (!textToCopy) return;

      try {
        await navigator.clipboard.writeText(textToCopy.trim());
        showToast(`Copied to clipboard: "${textToCopy.slice(0, 32)}..."`);
      } catch (err) {
        console.error('Clipboard copy failed:', err);
      }
    });
  });
}

// 7. Background Canvas: Query AST Particle Network
function initTelemetryCanvas() {
  const canvas = document.getElementById('telemetry-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const nodes = [];
  const nodeCount = Math.min(Math.floor((width * height) / 30000), 45);

  for (let i = 0; i < nodeCount; i++) {
    nodes.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      radius: Math.random() * 2 + 1,
      color: Math.random() > 0.6 ? '#6366F1' : (Math.random() > 0.5 ? '#22D3EE' : '#10B981')
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);

    // Draw connecting edges
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 140) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.strokeStyle = `rgba(99, 102, 241, ${0.12 * (1 - dist / 140)})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    // Update and draw nodes
    for (const node of nodes) {
      node.x += node.vx;
      node.y += node.vy;

      if (node.x < 0 || node.x > width) node.vx *= -1;
      if (node.y < 0 || node.y > height) node.vy *= -1;

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.shadowBlur = 8;
      ctx.shadowColor = node.color;
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    requestAnimationFrame(render);
  }

  render();
}
