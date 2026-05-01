//=================
// FILE: static/js/src/network.js (Sigma v3)
// - supernodes graphs: hulls + click-to-expand neighbors
// - NON-supernodes graphs: simple rendering
// ============================================================================

import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { bindWebGLLayer, createContoursProgram } from "@sigma/layer-webgl";
import { sleep, waitForNonZeroWidth } from "./utils_plot.js";
import { NodeCircleProgram } from "sigma/rendering";
import { highlightGenesInGraph } from "./highlighting.js";

export const instances = {};

const COLOR_PALETTE = [
  ["rgba(100,150,255,0.18)", "rgba(100,150,255,0.85)"],
  ["rgba(255,120,160,0.18)", "rgba(255,120,160,0.85)"],
  ["rgba(150,220,120,0.18)", "rgba(150,220,120,0.85)"],
  ["rgba(200,150,255,0.18)", "rgba(200,150,255,0.85)"],
  ["rgba(255,200,100,0.18)", "rgba(255,200,100,0.85)"],
  ["rgba(100,220,220,0.18)", "rgba(100,220,220,0.85)"],
  ["rgba(255,150,150,0.18)", "rgba(255,150,150,0.85)"],
  ["rgba(180,130,255,0.18)", "rgba(180,130,255,0.85)"],
  ["rgba(120,200,140,0.18)", "rgba(120,200,140,0.85)"],
  ["rgba(255,180,120,0.18)", "rgba(255,180,120,0.85)"],
  ["rgba(140,180,255,0.18)", "rgba(140,180,255,0.85)"],
  ["rgba(255,140,200,0.18)", "rgba(255,140,200,0.85)"],
  ["rgba(200,220,140,0.18)", "rgba(200,220,140,0.85)"],
  ["rgba(220,160,255,0.18)", "rgba(220,160,255,0.85)"],
  ["rgba(160,240,200,0.18)", "rgba(160,240,200,0.85)"],
  ["rgba(255,210,150,0.18)", "rgba(255,210,150,0.85)"],
  ["rgba(180,150,220,0.18)", "rgba(180,150,220,0.85)"],
  ["rgba(140,200,180,0.18)", "rgba(140,200,180,0.85)"],
  ["rgba(255,170,170,0.18)", "rgba(255,170,170,0.85)"],
  ["rgba(190,210,255,0.18)", "rgba(190,210,255,0.85)"],
];

function rgbToHex(rgb) {
  if (!rgb) return "#999999";
  if (rgb.startsWith("#")) return rgb;
  const m = String(rgb).match(/\d+/g);
  if (!m) return "#999999";
  return "#" + m.slice(0, 3).map(x => parseInt(x, 10).toString(16).padStart(2, "0")).join("");
}

function setAlpha(rgba, alpha) {
  const m = rgba.match(/rgba?\(([^)]+)\)/);
  if (!m) return rgba;

  const parts = m[1].split(",").map(x => x.trim());
  const [r, g, b] = parts;

  return `rgba(${r},${g},${b},${alpha})`;
}

export function countActiveWebGLContexts() {
  return Array.from(document.querySelectorAll("canvas")).reduce((acc, c) => {
    try {
      const gl = c.getContext("webgl2") || c.getContext("webgl") || c.getContext("experimental-webgl");
      return acc + (gl ? 1 : 0);
    } catch {
      return acc;
    }
  }, 0);
}

export async function ensureWebGLCapacity(limit = 6, waitMs = 120) {
  // Count by tracked instances (reliable), not by canvas sniffing (unreliable)
  while (Object.keys(instances).length >= limit) {
    const keys = Object.keys(instances);
    if (!keys.length) break;
    keys.sort((a, b) => instances[a].createdAt - instances[b].createdAt);
    disposeInstance(keys[0]);
    await sleep(waitMs);
  }
}

export function disposeInstance(instanceKey) {
  const inst = instances[instanceKey];
  if (!inst) return;

  try {
    inst.cleanupHulls?.();
    inst.unbindDrag?.();
    inst.layoutState?.stopFn?.();
    inst.sigma?.kill();
  } catch {}

  delete instances[instanceKey];
}

export function enableSigmaNodeDragging(sigma, graph) {
  let dragging = false;
  let draggedNode = null;

  sigma.on("downNode", ({ node }) => {
    dragging = true;
    draggedNode = node;
    sigma.getCamera().disable();
  });

  const captor = sigma.getMouseCaptor();

  const onMove = (e) => {
    if (!dragging || !draggedNode) return;
    const pos = sigma.viewportToGraph(e);
    graph.setNodeAttribute(draggedNode, "x", pos.x);
    graph.setNodeAttribute(draggedNode, "y", pos.y);
  };

  const onUp = () => {
    dragging = false;
    draggedNode = null;
    sigma.getCamera().enable();
  };

  captor.on("mousemovebody", onMove);
  captor.on("mouseup", onUp);
  document.addEventListener("mouseup", onUp);

  return () => {
    captor.removeListener("mousemovebody", onMove);
    captor.removeListener("mouseup", onUp);
    document.removeEventListener("mouseup", onUp);
  };
}

export function runForceAtlasProgressively(graph, sigma, settings, maxIterations) {
  let running = true;
  let iter = 0;

  const step = () => {
    if (!running) return;
    forceAtlas2.assign(graph, { iterations: 1, settings });
    iter++;
    if (iter < maxIterations) requestAnimationFrame(step);
  };

  requestAnimationFrame(step);
  return () => (running = false);
}

/* ------------------------------
   Helpers for hull grouping / neighbors
------------------------------ */
function getModuleList(attrs) {
  // primary (your current contract)
  if (Array.isArray(attrs.superList) && attrs.superList.length) return attrs.superList;

  // fallbacks (defensive)
  if (Array.isArray(attrs.modules) && attrs.modules.length) return attrs.modules;
  if (typeof attrs.module === "string" && attrs.module) return [attrs.module];
  if (typeof attrs.module_id === "string" && attrs.module_id) return [attrs.module_id];
  if (typeof attrs.cluster === "string" && attrs.cluster) return [attrs.cluster];

  return [];
}


/**
 * WEBGL HULLS
 * - supernodes graphs: build hulls even for hidden nodes (so hulls exist before expansion)
 */
export function __enableHulls(renderer, graph) {
  const groups = {};
  const clusterColorMap = {};

  const cleanups = [];

  // 🔥 GLOBAL COUNTER FOR UNIQUE LAYERS
  if (!window.__hullLayerCounter) {
    window.__hullLayerCounter = 0;
  }

  function rebuildHulls() {

    // cleanup old
    cleanups.forEach(obj => {
      try { obj.cleanup(); } catch {}
    });
    cleanups.length = 0;

    Object.keys(groups).forEach(k => delete groups[k]);

    // group nodes
    graph.forEachNode((node, attrs) => {
      const modules = getModuleList(attrs);
      if (!modules.length) return;
      if (!attrs.visible) return;

      modules.forEach((moduleName, indexInList) => {
        if (!groups[moduleName]) {
          groups[moduleName] = { nodes: [], nodeIndices: {} };
        }
        groups[moduleName].nodes.push(node);
        groups[moduleName].nodeIndices[node] = indexInList;
      });
    });

    let colorIndex = 0;
    const sortedModules = Object.keys(groups).sort();

    sortedModules.forEach(moduleName => {

      const { nodes, nodeIndices } = groups[moduleName];
      if (!nodes.length) return;

      const paletteIndex = colorIndex % COLOR_PALETTE.length;
      const [fillColor, borderColor] = COLOR_PALETTE[paletteIndex];

      clusterColorMap[moduleName] = borderColor;

      const indices = nodes.map(n => nodeIndices[n] ?? 0);
      const avgIndex = indices.reduce((a, b) => a + b, 0) / Math.max(indices.length, 1);

      const baseRadius = Math.min(60, 15 + nodes.length * 1.8);
      const radiusReduction = Math.floor(avgIndex * 25);
      const radius = Math.max(35, baseRadius - radiusReduction);

      try {
        // 🔥 UNIQUE NAME (fixes your crash)
const layerId = `hull-${moduleName}-${window.__hullLayerCounter++}`;

        const cleanup = bindWebGLLayer(
          layerId,
          renderer,
createContoursProgram(nodes, {
  radius,
  border: { thickness: 4.5, color: borderColor },

  // 🔥 REQUIRED: must NOT be empty
  levels: [
    { threshold: 0.5, color: "rgba(0,0,0,0)" }
  ],
})
        );

        cleanups.push({
          moduleName,
          cleanup,
          borderColor
        });

        colorIndex++;

      } catch (err) {
        console.error(`❌ Hull failed for ${moduleName}`, err);
      }
    });

    console.log(`✅ Rebuilt hulls: ${cleanups.length}`);
  }

  rebuildHulls();

  return {
    cleanup: () => cleanups.forEach(obj => obj.cleanup()),
    colorMap: clusterColorMap,
    rebuild: rebuildHulls,
    cleanups
  };
}


function placeTooltip(tooltip, x, y) {
  const pad = 12;
  const ttRect = tooltip.getBoundingClientRect();

  let left = x + pad;
  let top = y + pad;

  if (left + ttRect.width > window.innerWidth - 8) {
    left = x - ttRect.width - pad;
  }

  if (top + ttRect.height > window.innerHeight - 8) {
    top = y - ttRect.height - pad;
  }

  left = Math.max(8, left);
  top = Math.max(8, top);

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

export function fadeHulls(containerId, activeModule = null){

  const inst = instances[containerId];
  if (!inst || !inst.hullsResult) return;

  const { cleanups } = inst.hullsResult;

  // remove old hulls
  inst.cleanupHulls?.();

  const graph = inst.graph;
  const sigma = inst.sigma;

  const newCleanups = [];

  cleanups.forEach(({ moduleName, borderColor }) => {

    const isActive = !activeModule || moduleName === activeModule;

    const alpha = isActive ? 0.85 : 0.08;   // 🔥 fade level

    const fadedColor = setAlpha(borderColor, alpha);

    const nodes = [];

    graph.forEachNode((n, attrs) => {
      const list = attrs.superList || [];
      if (list.includes(moduleName) && attrs.visible) {
        nodes.push(n);
      }
    });

    if (!nodes.length) return;

  const radius = Math.max(35, 15 + nodes.length * 1.5);

const cleanup = bindWebGLLayer(
  `hull-${moduleName}`,
  sigma,
  createContoursProgram(nodes, {
    radius,
    border: { thickness: 4.5, color: fadedColor },
    levels: [
      { threshold: 0.5, color: "rgba(0,0,0,0)" }
    ],
  })
);

    newCleanups.push({ moduleName, cleanup, borderColor });

  });

  inst.cleanupHulls = () => newCleanups.forEach(o => o.cleanup());
  inst.hullsResult.cleanups = newCleanups;

  sigma.refresh();
}

export function refreshHulls(containerId) {
  const inst = instances[containerId];
  if (!inst || !inst.isSupernodes) return;

  try {
    inst.cleanupHulls?.();
  } catch {}

  const hullsResult = __enableHulls(inst.sigma, inst.graph, { includeHidden: true });
  inst.cleanupHulls = hullsResult.cleanup;
  inst.clusterColorMap = hullsResult.colorMap;
  inst.hullsResult = hullsResult;

  inst.sigma.refresh();
}


export async function initOneGraph_safe({ containerId, graphData, containerOverride = null }) {
// 🔥 ALWAYS dispose previous instance (safe + predictable)
if (instances[containerId]) {
  disposeInstance(containerId);
}

  await ensureWebGLCapacity();

  const wrapper = document.getElementById(containerId);
  const container = containerOverride || wrapper?.querySelector(".net-container") || wrapper;

  if (!container) return;

  if (getComputedStyle(container).position === "static") {
    container.style.position = "relative";
  }

  try {
    await waitForNonZeroWidth(container, 8000);
  } catch {}

  const graph = new Graph({ multi: true });
  const isSupernodes = containerId.toLowerCase().includes("supernodes");

  // ============================
  // NODES
  // ============================
  graphData.nodes?.forEach((n) => {
    const color = String(n.color || "").trim().toLowerCase();
    const isPurple = color === "purple";
    const baseVisible = isSupernodes ? isPurple : true;

    graph.addNode(n.id, {
      ...n,
      x: n.x ?? (Math.random() - 0.5) * 50,
      y: n.y ?? (Math.random() - 0.5) * 50,
      size: baseVisible ? (n.size ?? 7) : 0.0001,
      label: baseVisible ? (n.label ?? n.id) : "",
      label_base: n.label ?? n.id,
      visible: baseVisible,
      baseVisible: baseVisible,
      expanded: false,
      isPurple: isPurple,
    });
  });

  const hasCoordinates =
    graphData.nodes &&
    graphData.nodes.length > 0 &&
    graphData.nodes.every(n => typeof n.x === "number" && typeof n.y === "number");

  // ============================
  // EDGES
  // ============================
  graphData.edges?.forEach((e, i) => {
    try {
      if (!graph.hasNode(e.source) || !graph.hasNode(e.target)) return;

      const w = Number(e.weight ?? e.w ?? 1.0);
      const safeW = Number.isFinite(w) ? w : 1;

      const scaled = Number(e.weight_scaled ?? Math.log1p(safeW));
      const norm = Number.isFinite(Number(e.weight_norm)) ? Number(e.weight_norm) : 0;

      const alpha = Math.max(0.3, Math.min(0.8, scaled / 2));
      const size = Math.max(1.2, 1 + 3 * scaled);

      graph.addEdgeWithKey(
        e.id ?? `e-${i}-${e.source}-${e.target}`,
        e.source,
        e.target,
        {
          weight: safeW,
          weight_scaled: scaled,
          weight_norm: norm,
          size,
          color: `rgba(40,40,40,${alpha})`,
          hidden: false,
        }
      );
    } catch (err) {
      console.warn(`Failed to add edge ${e.source} -> ${e.target}:`, err.message);
    }
  });

  // ============================
  // SIGMA
  // ============================
  const sigma = new Sigma(graph, container, {
    renderLabels: true,
    labelRenderedSizeThreshold: 0,
    allowInvalidContainer: true,
    defaultLabelSize: 12,
    minCameraRatio: 0.1,
    maxCameraRatio: 20,
    forceLabels: true,
    defaultLabelColor: "#000",
    labelFont: "Arial",
    labelDensity: 1000,
    defaultEdgeColor: "#999",
    renderEdgeLabels: false,
    nodeProgramClasses: { circle: NodeCircleProgram },
  });

  // ============================
  // REDUCERS
  // ============================
  sigma.setSetting("nodeReducer", (node, attrs) => {
    if (!graph.getNodeAttribute(node, "visible")) {
      return { ...attrs, hidden: true, size: 0.0001, label: "" };
    }

    if (attrs.highlighted) {
      return {
        ...attrs,
        color: "#ff0000",
        size: Math.max(attrs.size * 1.6, 8),
        zIndex: 20
      };
    }

    return attrs;
  });

  sigma.setSetting("edgeReducer", (edge, attrs) => {
    const s = graph.source(edge);
    const t = graph.target(edge);

    const sourceVisible = graph.getNodeAttribute(s, "visible");
    const targetVisible = graph.getNodeAttribute(t, "visible");

    if (attrs.hidden === true) {
      return { ...attrs, hidden: true, size: 0.0001 };
    }

    if (!(sourceVisible && targetVisible)) {
      return { ...attrs, hidden: true, size: 0.0001 };
    }

    return {
      ...attrs,
      hidden: false,
      size: attrs.size ?? 1.5,
      color: attrs.color || "#999",
    };
  });

  // ============================
  // TOOLTIP
  // ============================
  const tooltip = document.getElementById("ot-tooltip");

  sigma.on("enterNode", ({ node, event }) => {
    const attrs = graph.getNodeAttributes(node);

    if (tooltip) {
      tooltip.innerHTML = `<b>${attrs.label}</b>`;
      tooltip.style.display = "block";
      placeTooltip(tooltip, event.x, event.y);
    }

    graph.setNodeAttribute(node, "highlighted", true);
    sigma.refresh();
  });

  sigma.on("leaveNode", ({ node }) => {
    if (tooltip) {
      tooltip.style.display = "none";
    }
    graph.setNodeAttribute(node, "highlighted", false);
    sigma.refresh();
  });

  sigma.getMouseCaptor().on("mousemovebody", (e) => {
    if (!tooltip || tooltip.style.display === "none") return;
    placeTooltip(tooltip, e.x, e.y);
  });

  // ============================
  // CLICK → show OT panel
  // ============================
  sigma.on("clickNode", ({ node }) => {
    const attrs = graph.getNodeAttributes(node);

    if (attrs.ot) {
      renderOTPanel(containerId, attrs);
    }
  });

  // ============================
  // DOUBLE CLICK → expand ONLY for supernodes
  // ============================
  if (isSupernodes) {
    sigma.on("doubleClickNode", (e) => {
      try { e.event?.preventSigmaDefault?.(); } catch {}
      try { e.event?.original?.preventDefault?.(); } catch {}
      try { e.event?.original?.stopPropagation?.(); } catch {}
  
      expandNode(graph, e.node);
      refreshHulls(containerId);
      sigma.refresh();
    });
  }

  const unbindDrag = enableSigmaNodeDragging(sigma, graph);

  // ============================
  // LAYOUT
  // ============================
  if (!hasCoordinates && isSupernodes) {
    forceAtlas2.assign(graph, {
      iterations: 80,
      settings: {
        linLogMode: true,
        outboundAttractionDistribution: true,
        adjustSizes: true,
        gravity: 0.02,
        scalingRatio: 2,
        slowDown: 10,
      }
    });
  }

  sigma.refresh();

  // ============================
  // STORE INSTANCE
  // ============================
  instances[containerId] = {
    graph,
    sigma,
    createdAt: Date.now(),
    isSupernodes,
    cleanupHulls: null,
    clusterColorMap: {},
    unbindDrag,
    layoutState: { stopFn: null },
  };

  sigma.on("clickStage", () => {
    const wrapper = document.getElementById(containerId);
    const panel = wrapper?.querySelector(".ot-panel");
    const content = wrapper?.querySelector(".ot-content");
  
    if (panel) panel.classList.remove("is-open");
    if (content) content.innerHTML = "Click a node";
  });

  // ============================
  // HULLS
  // ============================
  if (isSupernodes) {
    await new Promise(r => requestAnimationFrame(r));
    await new Promise(r => requestAnimationFrame(r));

    const hullsResult = __enableHulls(sigma, graph);

    instances[containerId].cleanupHulls = hullsResult.cleanup;
    instances[containerId].clusterColorMap = hullsResult.colorMap;
    instances[containerId].hullsResult = hullsResult;

    sigma.refresh();
  }

  console.log(`✅ Graph initialized: ${graph.order} nodes, ${graph.size} edges`);
}

export function getSupernodeClusters(graph, colorMap = {}) {
  const clusters = new Map();

  graph.forEachNode((node, attrs) => {
    const modules = getModuleList(attrs);
    if (!modules.length) return;

    modules.forEach(clusterId => {
      if (!clusters.has(clusterId)) {
        clusters.set(clusterId, {
          id: clusterId,
          count: 0,
          color: colorMap[clusterId] || attrs.color || "#999",
        });
      }
      clusters.get(clusterId).count++;
    });
  });

  return [...clusters.values()].sort((a, b) => a.id.localeCompare(b.id));
}

export function revealNode(graph, nodeId, { size = 6, keepLabel = true } = {}) {
  if (!graph.hasNode(nodeId)) return;

  graph.setNodeAttribute(nodeId, "visible", true);
  graph.setNodeAttribute(nodeId, "size", size);

  if (keepLabel) {
    graph.setNodeAttribute(
      nodeId,
      "label",
      graph.getNodeAttribute(nodeId, "label_base")
    );
  }
}

export function expandNode(graph, node) {
  const isPurple = graph.getNodeAttribute(node, "isPurple");
  if (!isPurple) return;

  const expanded = graph.getNodeAttribute(node, "expanded");

  if (!expanded) {
    const neighbors = graph.neighbors(node);

    neighbors.forEach(n => {
      if (!graph.hasNode(n)) return;
      if (graph.getNodeAttribute(n, "isPurple")) return;

      revealNode(graph, n, { size: 6 });
    });

    graph.setNodeAttribute(node, "expanded", true);

  } else {
    const neighbors = graph.neighbors(node);

    neighbors.forEach(n => {
      if (!graph.hasNode(n)) return;
      if (graph.getNodeAttribute(n, "isPurple")) return;

      graph.setNodeAttribute(n, "visible", false);
      graph.setNodeAttribute(n, "size", 0);
      graph.setNodeAttribute(n, "label", "");
    });

    graph.setNodeAttribute(node, "expanded", false);
  }

  console.log("Toggle node:", node);
}

export function expandCollapseAllSupernodes(instanceKey, expand = true) {
  const inst = instances[instanceKey];
  if (!inst || !inst.isSupernodes) {
    console.warn("❌ Not a supernodes instance:", instanceKey);
    return;
  }

  const graph = inst.graph;

  graph.forEachNode((node, attrs) => {
    if (attrs.isPurple) {
      graph.setNodeAttribute(node, "visible", true);
      graph.setNodeAttribute(node, "size", 7);
      graph.setNodeAttribute(node, "label", graph.getNodeAttribute(node, "label_base"));
      graph.setNodeAttribute(node, "expanded", expand);

      const neighbors = graph.neighbors(node);

      neighbors.forEach((nid) => {
        if (!graph.hasNode(nid)) return;
        if (graph.getNodeAttribute(nid, "isPurple")) return;

        if (expand) {
          graph.setNodeAttribute(nid, "visible", true);
          graph.setNodeAttribute(nid, "size", 10);
          graph.setNodeAttribute(nid, "label", graph.getNodeAttribute(nid, "label_base"));
        } else {
          graph.setNodeAttribute(nid, "visible", false);
          graph.setNodeAttribute(nid, "size", 0);
          graph.setNodeAttribute(nid, "label", "");
          graph.setNodeAttribute(nid, "expanded", false);
        }
      });
    } else if (!expand) {
      graph.setNodeAttribute(node, "visible", false);
      graph.setNodeAttribute(node, "size", 0);
      graph.setNodeAttribute(node, "label", "");
      graph.setNodeAttribute(node, "expanded", false);
    }
  });

  refreshHulls(instanceKey);
  inst.sigma.refresh();
}

function renderOTPanel(containerId, data) {
  const wrapper = document.getElementById(containerId);
  if (!wrapper) return;

  const panel = wrapper.querySelector(".ot-panel");
  const content = wrapper.querySelector(".ot-content");
  const closeBtn = wrapper.querySelector(".ot-panel-close");

  if (!panel || !content) return;

  const ot = data.ot || {};

  let html = `
    <h4><b>${data.label}</b></h4>
    <div><b>Uniprot:</b> ${data.id}</div>
    <div><b>Module:</b> ${data.module || "-"}</div>
    <div><b>Max Phase:</b> ${ot.max_phase ?? "-"}</div>
    <hr/>
  `;

  if (ot.drugs && ot.drugs.length > 0) {
    html += `
      <h5><b>Drugs</b></h5>
      <table class="table is-fullwidth is-striped is-small">
        <thead>
          <tr><th>Name</th><th>ChEMBL</th><th>Phase</th></tr>
        </thead>
        <tbody>
          ${ot.drugs.map(d => `
            <tr>
              <td>${d.name ?? "-"}</td>
              <td>${d.chembl_id ?? "-"}</td>
              <td>${d.phase ?? "-"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } else {
    html += `<div class="muted">No drugs available</div>`;
  }

  if (ot.top_diseases && ot.top_diseases.length > 0) {
    html += `
      <h5><b>Top Diseases</b></h5>
      <table class="table is-fullwidth is-striped is-small">
        <thead>
          <tr><th>Disease</th><th>Score</th></tr>
        </thead>
        <tbody>
          ${ot.top_diseases.slice(0, 10).map(d => `
            <tr>
              <td>${typeof d === "string" ? d : (d.name || d.disease || "-")}</td>
              <td>${typeof d === "string" ? "-" : (d.score != null ? Number(d.score).toFixed(3) : "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } else {
    html += `<div class="muted">No disease data</div>`;
  }

  content.innerHTML = html;
  panel.classList.add("is-open");

  if (closeBtn && !closeBtn.dataset.bound) {
    closeBtn.addEventListener("click", () => {
      panel.classList.remove("is-open");
      content.innerHTML = "Click a node";
    });
    closeBtn.dataset.bound = "1";
  }
}
export function clearHighlights(instanceKey) {
  const inst = instances[instanceKey];
  if (!inst) return;

  const graph = inst.graph;
  inst.activeGeneSet = null;
  inst.activeGeneSetKey = null;

  graph.forEachNode((n, attrs) => {
    graph.setNodeAttribute(n, "highlighted", false);

    if (attrs.isPurple) {
      graph.setNodeAttribute(n, "visible", true);
      graph.setNodeAttribute(n, "size", 7);
      graph.setNodeAttribute(n, "label", attrs.label_base);
      graph.setNodeAttribute(n, "expanded", false);
    } else {
      graph.setNodeAttribute(n, "visible", false);
      graph.setNodeAttribute(n, "size", 0);
      graph.setNodeAttribute(n, "label", "");
      graph.setNodeAttribute(n, "expanded", false);
    }
  });

  graph.forEachEdge(e => {
    graph.setEdgeAttribute(e, "hidden", false);
  });

  if (inst.isSupernodes) {
    refreshHulls(instanceKey);
  }

  inst.sigma.refresh();
}


window.Network = {
  highlightGenesInGraph,
  getSupernodeClusters,
  initOneGraph_safe,
  disposeInstance,
  instances,
  __enableHulls,
  refreshHulls,
  fadeHulls,
  expandNode,
  expandCollapseAllSupernodes,
  clearHighlights,   // 🔥 THIS LINE MUST BE HERE
};
console.log("✅ window.Network includes:", Object.keys(window.Network));
