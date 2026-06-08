const state = {
  graph: { nodes: [], edges: [] },
  byId: new Map(),
  lastResult: null,
};

const domainColors = [
  "#67e8f9",
  "#34d399",
  "#f59e0b",
  "#a78bfa",
  "#fb7185",
  "#60a5fa",
  "#f472b6",
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value, digits = 2) {
  return Number(value).toFixed(digits);
}

function colorForDomain(domain) {
  let total = 0;
  for (const char of domain) {
    total += char.charCodeAt(0);
  }
  return domainColors[total % domainColors.length];
}

async function loadDashboard() {
  const [graphResponse, evalResponse] = await Promise.all([
    fetch("/api/graph"),
    fetch("/api/eval-summary"),
  ]);
  state.graph = await graphResponse.json();
  state.byId = new Map(state.graph.nodes.map((node) => [node.id, node]));
  renderTorus([]);
  renderEvalSummary((await evalResponse.json()).strategies);
}

function renderTorus(reasoningPath) {
  const edgeTraces = edgeLineTraces(state.graph.edges, "rgba(148, 163, 184, 0.18)", 1.1);
  const pathTraces = edgeLineTraces(reasoningPath, "#f59e0b", 4);
  const nodeTrace = {
    type: "scatter",
    mode: "markers+text",
    x: state.graph.nodes.map((node) => node.theta),
    y: state.graph.nodes.map((node) => node.phi),
    text: state.graph.nodes.map((node) => node.label),
    textposition: "top center",
    hovertext: state.graph.nodes.map(
      (node) => `${node.label}<br>${node.domain}<br>${node.source}`,
    ),
    hoverinfo: "text",
    marker: {
      color: state.graph.nodes.map((node) => colorForDomain(node.domain)),
      line: { color: "rgba(255,255,255,0.72)", width: 1 },
      size: 13,
      opacity: 0.94,
    },
    textfont: { color: "#dbeafe", size: 10 },
    name: "concepts",
  };

  Plotly.react(
    "torus-chart",
    [...edgeTraces, ...pathTraces, nodeTrace],
    {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(2,6,23,0.35)",
      margin: { t: 18, r: 16, b: 42, l: 48 },
      xaxis: {
        title: "theta",
        gridcolor: "rgba(148,163,184,0.14)",
        zerolinecolor: "rgba(148,163,184,0.22)",
        color: "#cbd5e1",
      },
      yaxis: {
        title: "phi",
        gridcolor: "rgba(148,163,184,0.14)",
        zerolinecolor: "rgba(148,163,184,0.22)",
        color: "#cbd5e1",
      },
      showlegend: false,
      hovermode: "closest",
      annotations: [
        {
          xref: "paper",
          yref: "paper",
          x: 0,
          y: -0.16,
          text: "Axes wrap: left connects to right, top connects to bottom.",
          showarrow: false,
          font: { color: "#94a3b8", size: 12 },
        },
      ],
    },
    { responsive: true, displayModeBar: false },
  );
}

function edgeLineTraces(edges, color, width) {
  return edges
    .map((edge) => {
      const source = state.byId.get(edge.source || edge.fromNode || edge.from_node || edge.from);
      const target = state.byId.get(edge.target || edge.toNode || edge.to_node || edge.to);
      if (!source || !target) {
        return null;
      }
      return {
        type: "scatter",
        mode: "lines",
        x: [source.theta, target.theta],
        y: [source.phi, target.phi],
        line: { color, width },
        hoverinfo: "skip",
      };
    })
    .filter(Boolean);
}

function renderEvalSummary(rows) {
  const wanted = new Set([
    "tortus_torus",
    "bounded_agentic_local",
    "vector_only_local",
    "hybrid_dense_bm25_local",
  ]);
  const cards = rows.filter((row) => wanted.has(row.strategy));
  document.getElementById("eval-cards").innerHTML = cards
    .map(
      (row) => `
        <article class="comparison-card">
          <strong>${formatNumber(row.path)}</strong>
          <span>${escapeHtml(row.strategy)} path</span>
        </article>
      `,
    )
    .join("");

  document.getElementById("eval-table").innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.strategy)}</td>
          <td>${formatNumber(row.pass)}</td>
          <td>${formatNumber(row.source)}</td>
          <td>${formatNumber(row.path)}</td>
          <td>${formatNumber(row.shardFanout, 1)}</td>
        </tr>
      `,
    )
    .join("");
}

async function runQuery() {
  const button = document.getElementById("run-query");
  const query = document.getElementById("query-input").value.trim();
  if (!query) {
    return;
  }
  button.disabled = true;
  button.textContent = "Running";
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const result = await response.json();
    state.lastResult = result;
    renderAnswer(result);
    renderTorus(result.reasoning_path || []);
  } finally {
    button.disabled = false;
    button.textContent = "Run";
  }
}

function renderAnswer(result) {
  document.getElementById("warnings").textContent = result.warnings.join(" ");
  document.getElementById("answer").textContent = result.answer;
  document.getElementById("diagnosis").textContent = result.diagnosis || result.answer;
  document.getElementById("quality-mode").textContent = result.quality_mode || "unknown quality";
  document.getElementById("action-list").innerHTML = (result.recommended_actions || []).length
    ? result.recommended_actions
        .map((action) => `<li>${escapeHtml(action)}</li>`)
        .join("")
    : "<li>No recommended actions were generated.</li>";
  document.getElementById("missing-evidence").textContent = (result.missing_evidence || []).join(
    " ",
  );
  renderSourceHealth(result.source_health || {});
  const budget = result.budget;
  document.getElementById("budget").innerHTML = [
    ["confidence", formatNumber(result.confidence)],
    ["nodes", budget.nodes_visited],
    ["hops", budget.hops_taken],
    ["portals", budget.portal_hops],
    ["fanout", budget.shard_fanout],
    ["cross", budget.shard_crossings],
    ["tokens", budget.tokens_estimated],
    ["candidates", budget.candidates_considered],
    ["pruned", budget.pruned_edges],
    ["support", budget.lexical_support],
    ["ms", formatNumber(budget.elapsed_ms, 1)],
  ]
    .map(
      ([label, value]) => `
        <div class="metric">
          <strong>${escapeHtml(value)}</strong>
          <span>${escapeHtml(label)}</span>
        </div>
      `,
    )
    .join("");

  document.getElementById("path-table").innerHTML = (result.reasoning_path || [])
    .slice(0, 18)
    .map(
      (hop) => `
        <tr>
          <td>${escapeHtml(shortId(hop.from_node))}</td>
          <td>${escapeHtml(shortId(hop.to_node))}</td>
          <td>${escapeHtml(hop.edge_type)}</td>
          <td>${formatNumber(hop.weight)}</td>
          <td>${formatNumber(hop.score)}</td>
          <td>${escapeHtml((hop.matched_terms || []).join(", "))}</td>
          <td>${escapeHtml(hop.reason || "")}</td>
        </tr>
      `,
    )
    .join("");

  document.getElementById("evidence-list").innerHTML = result.evidence
    .slice(0, 8)
    .map(
      (span) => `
        <article class="evidence-card">
          <strong>${escapeHtml(span.uri)} · ${span.start}-${span.end}</strong>
          <p>${escapeHtml(span.text)}</p>
        </article>
      `,
    )
    .join("");
  renderTrace(result.trace || {});
}

function renderSourceHealth(health) {
  const sourceTypes = Object.entries(health.source_types || {})
    .map(([key, value]) => `${key}:${value}`)
    .join(", ");
  document.getElementById("source-health").innerHTML = [
    ["quality", formatNumber(health.quality_score || 0)],
    ["docs", health.documents || 0],
    ["chunks", health.chunks || 0],
    ["unsupported", health.unsupported_sources || 0],
    ["empty", health.empty_documents || 0],
    ["duplicates", health.duplicate_documents || 0],
    ["types", sourceTypes || "unknown"],
    ["warnings", (health.warnings || []).length],
  ]
    .map(
      ([label, value]) => `
        <div class="metric compact">
          <strong>${escapeHtml(value)}</strong>
          <span>${escapeHtml(label)}</span>
        </div>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  renderSeedHits(trace.seed_hits || []);
  renderPortalDecisions(trace.portal_decisions || []);
  renderPrunedCandidates();
  renderClaims(trace.answer_claims || [], trace.unsupported_claims || []);
  renderScoreComponents((trace.selected_hops || [])[0]);
}

function renderSeedHits(hits) {
  document.getElementById("seed-table").innerHTML = hits.length
    ? hits
    .slice(0, 12)
    .map(
      (hit) => `
        <tr>
          <td>${escapeHtml(shortId(hit.node_id))}</td>
          <td>${formatNumber(hit.score)}</td>
          <td>${escapeHtml((hit.matched_terms || []).join(", "))}</td>
          <td>${escapeHtml(scoreComponentText(hit.score_components))}</td>
        </tr>
      `,
    )
    .join("")
    : '<tr><td colspan="4" class="muted">No seed hits were returned.</td></tr>';
}

function renderPortalDecisions(decisions) {
  document.getElementById("portal-table").innerHTML = decisions.length
    ? decisions
    .slice(0, 16)
    .map(
      (decision) => `
        <tr>
          <td>${escapeHtml(decision.selected ? "selected" : "pruned")}</td>
          <td>${escapeHtml(shortId(decision.from_node))}</td>
          <td>${escapeHtml(shortId(decision.to_node))}</td>
          <td>${formatNumber(decision.score)}</td>
          <td>${escapeHtml(decision.reason)}</td>
        </tr>
      `,
    )
    .join("")
    : '<tr><td colspan="5" class="muted">No portal decisions were recorded.</td></tr>';
}

function renderPrunedCandidates() {
  if (!state.lastResult) {
    return;
  }
  const trace = state.lastResult.trace || {};
  const edgeFilter = document.getElementById("edge-filter").value;
  const sourceFilter = document.getElementById("source-filter").value.trim().toLowerCase();
  const minScore = Number(document.getElementById("score-filter").value || 0);
  const portalOnly = document.getElementById("portal-only").checked;
  const prunedOnly = document.getElementById("pruned-only").checked;
  const candidates = (trace.pruned_candidates || []).filter((candidate) => {
    if (prunedOnly && !candidate.reason) {
      return false;
    }
    if (edgeFilter && candidate.edge_type !== edgeFilter) {
      return false;
    }
    if (portalOnly && candidate.edge_type !== "portal") {
      return false;
    }
    if (Number(candidate.score) < minScore) {
      return false;
    }
    if (sourceFilter) {
      const text = `${candidate.from_node} ${candidate.to_node} ${candidate.reason}`.toLowerCase();
      return text.includes(sourceFilter);
    }
    return true;
  });
  document.getElementById("pruned-table").innerHTML = candidates.length
    ? candidates
    .slice(0, 24)
    .map(
      (candidate) => `
        <tr>
          <td>${escapeHtml(shortId(candidate.from_node))}</td>
          <td>${escapeHtml(shortId(candidate.to_node))}</td>
          <td>${escapeHtml(candidate.edge_type)}</td>
          <td>${formatNumber(candidate.score)}</td>
          <td>${escapeHtml((candidate.matched_terms || []).join(", "))}</td>
          <td>${escapeHtml(candidate.reason)}</td>
        </tr>
      `,
    )
    .join("")
    : '<tr><td colspan="6" class="muted">No pruned candidates match the active filters.</td></tr>';
}

function renderClaims(claims, unsupportedClaims) {
  document.getElementById("claim-list").innerHTML = claims.length
    ? claims
    .map(
      (claim) => `
        <article class="claim-card ${claim.supported ? "supported" : "unsupported"}">
          <strong>${escapeHtml(claim.supported ? "supported" : "weak support")}</strong>
          <p>${escapeHtml(claim.text)}</p>
          <small>${escapeHtml((claim.evidence_uris || []).join(", "))}</small>
        </article>
      `,
    )
    .join("")
    : '<p class="muted">No claims were generated.</p>';
  document.getElementById("unsupported-list").innerHTML = unsupportedClaims.length
    ? unsupportedClaims
        .map((claim) => `<li>${escapeHtml(claim.text)}</li>`)
        .join("")
    : "<li>No unsupported claims detected.</li>";
}

function renderScoreComponents(hop) {
  document.getElementById("score-components").innerHTML = hop
    ? Object.entries(hop.score_components || {})
        .map(
          ([key, value]) => `
            <div class="metric compact">
              <strong>${formatNumber(value)}</strong>
              <span>${escapeHtml(key)}</span>
            </div>
          `,
        )
        .join("")
    : '<p class="muted">Run a query to inspect hop score components.</p>';
}

function scoreComponentText(components) {
  return Object.entries(components || {})
    .map(([key, value]) => `${key}=${formatNumber(value)}`)
    .join(", ");
}

function shortId(nodeId) {
  return String(nodeId || "").replace("concept:", "");
}

document.getElementById("run-query").addEventListener("click", runQuery);
document.getElementById("query-input").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runQuery();
  }
});
for (const id of ["edge-filter", "source-filter", "score-filter", "portal-only", "pruned-only"]) {
  document.getElementById(id).addEventListener("input", renderPrunedCandidates);
}

loadDashboard().then(() => {
  if (new URLSearchParams(window.location.search).has("demo")) {
    window.setTimeout(runQuery, 450);
  }
});
