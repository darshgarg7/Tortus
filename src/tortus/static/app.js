const state = {
  graph: { nodes: [], edges: [] },
  byId: new Map(),
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
      const source = state.byId.get(edge.source || edge.fromNode);
      const target = state.byId.get(edge.target || edge.toNode);
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
  const wanted = new Set(["tortus_torus", "bounded_agentic", "vector_only", "hybrid_dense_bm25"]);
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
    const response = await fetch("/graphql", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: `query($q: String!) {
          answer(query: $q) {
            answer
            confidence
            warnings
            budget {
              elapsedMs
              nodesVisited
              hopsTaken
              portalHops
              shardFanout
              shardCrossings
              tokensEstimated
              truncated
            }
            reasoningPath { fromNode toNode edgeType weight }
            evidence { uri start end text }
          }
        }`,
        variables: { q: query },
      }),
    });
    const payload = await response.json();
    const result = payload.data.answer;
    renderAnswer(result);
    renderTorus(result.reasoningPath);
  } finally {
    button.disabled = false;
    button.textContent = "Run";
  }
}

function renderAnswer(result) {
  document.getElementById("warnings").textContent = result.warnings.join(" ");
  document.getElementById("answer").textContent = result.answer;
  document.getElementById("budget").innerHTML = [
    ["confidence", formatNumber(result.confidence)],
    ["nodes", result.budget.nodesVisited],
    ["hops", result.budget.hopsTaken],
    ["portals", result.budget.portalHops],
    ["fanout", result.budget.shardFanout],
    ["cross", result.budget.shardCrossings],
    ["tokens", result.budget.tokensEstimated],
    ["ms", formatNumber(result.budget.elapsedMs, 1)],
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

  document.getElementById("path-table").innerHTML = result.reasoningPath
    .slice(0, 18)
    .map(
      (hop) => `
        <tr>
          <td>${escapeHtml(shortId(hop.fromNode))}</td>
          <td>${escapeHtml(shortId(hop.toNode))}</td>
          <td>${escapeHtml(hop.edgeType)}</td>
          <td>${formatNumber(hop.weight)}</td>
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
}

function shortId(nodeId) {
  return nodeId.replace("concept:", "");
}

document.getElementById("run-query").addEventListener("click", runQuery);
document.getElementById("query-input").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runQuery();
  }
});

loadDashboard().then(() => {
  if (new URLSearchParams(window.location.search).has("demo")) {
    window.setTimeout(runQuery, 450);
  }
});
