// ============================================================================
// FILE: static/js/utils_plot.js
// Shared helpers for enrichment tables + D3 plots
// ============================================================================

/* global d3 */

export const DB_FULLNAME = {
  C: "Cellular Component",
  P: "Biological Process",
  F: "Molecular Function",
  K: "KEGG",
  R: "Reactome",
  RT: "Reactome Total",
  B: "Bioplanet"
};

export function enablePanZoom(svg, root) {
  if (!svg || !root) return;

   const zoom = d3.zoom()
     .scaleExtent([0.5, 3])        // 🔽 limit max zoom (was 8)
     .wheelDelta((event) => {
       return -event.deltaY * 0.0001;   // 🔽 reduce zoom speed (default ~0.002)
     })
     .on("zoom", (event) => {
       root.attr("transform", event.transform);
     });

  svg.call(zoom);
}


export function expandCollapseAllSupernodes(containerId, expand=true) {

  const inst = window.Network?.instances?.[containerId];
  if (!inst || !inst.isSupernodes) {
    console.warn("Not a supernode network:", containerId);
    return;
  }

  const graph = inst.graph;

  if (expand) {

    const toShow = new Set();

    graph.forEachNode((node, attrs) => {

      if (!attrs.isPurple) return;

      const neigh = attrs.neigh || [];

      neigh.forEach(n => {
        if (graph.hasNode(n) && !graph.getNodeAttribute(n,"isPurple")) {
          toShow.add(n);
        }
      });

      graph.setNodeAttribute(node,"visible",true);
      graph.setNodeAttribute(node,"expanded",true);
      graph.setNodeAttribute(node,"size",8);
      graph.setNodeAttribute(node,"label",attrs.label_base);

    });

    toShow.forEach(n=>{
      graph.setNodeAttribute(n,"visible",true);
      graph.setNodeAttribute(n,"size",6);
      graph.setNodeAttribute(n,"label",graph.getNodeAttribute(n,"label_base"));
    });

  } else {

    graph.forEachNode((node,attrs)=>{

      if (attrs.isPurple) {

        graph.setNodeAttribute(node,"visible",true);
        graph.setNodeAttribute(node,"expanded",false);
        graph.setNodeAttribute(node,"size",8);
        graph.setNodeAttribute(node,"label",attrs.label_base);

      } else {

        graph.setNodeAttribute(node,"visible",false);
        graph.setNodeAttribute(node,"size",0);
        graph.setNodeAttribute(node,"label","");

      }

    });

  }

  // sync edges
  graph.forEachEdge((edge,attr,source,target)=>{

    const s = graph.getNodeAttribute(source,"visible");
    const t = graph.getNodeAttribute(target,"visible");

    graph.setEdgeAttribute(edge,"hidden", !(s && t));

  });

// ✅ correct hull refresh
if (inst.isSupernodes && window.Network?.__enableHulls) {

  if (inst.cleanupHulls) inst.cleanupHulls();

  const res = window.Network.__enableHulls(inst.sigma, inst.graph);

  inst.cleanupHulls = res.cleanup;
  inst.clusterColorMap = res.colorMap;
}

inst.sigma.refresh();

}
window.expandCollapseAllSupernodes = expandCollapseAllSupernodes;
export function dbKeyToLabel(dbKey) {
  return DB_FULLNAME[dbKey] || dbKey;
}

export function parsePossibleSci(value) {
  if (value == null || value === "") return NaN;
  if (typeof value === "number") return value;

  const s = String(value).trim().replace(",", ".");
  if (!s) return NaN;

  const n = Number(s);
  return Number.isNaN(n) ? parseFloat(s) : n;
}

export function pvalueToSci(value) {
  const n = parsePossibleSci(value);
  if (Number.isNaN(n)) return String(value ?? "");
  return n.toExponential(2);
}

export function escapeCsvCell(value) {
  if (value == null) return "";
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function splitGenes(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (value == null || value === "") return [];
  return String(value)
    .split(/[,\s;]+/)
    .map(s => s.trim())
    .filter(Boolean);
}

export function makeGeneBadgeList(value, previewCount = 6) {
  const genes = splitGenes(value);
  if (!genes.length) return "";

  const preview = genes.slice(0, previewCount);
  const hidden = genes.slice(previewCount);
  const uid = `genes-${Math.random().toString(36).slice(2, 9)}`;

  const previewHtml = preview
    .map(g => `<span class="tag is-light mr-1 mb-1">${g}</span>`)
    .join("");

  const hiddenHtml = hidden
    .map(g => `<span class="tag is-light mr-1 mb-1">${g}</span>`)
    .join("");

  if (!hidden.length) return `<div class="gene-badges">${previewHtml}</div>`;

  return `
    <div class="gene-badges">
      ${previewHtml}
      <span id="${uid}" style="display:none;">${hiddenHtml}</span>
      <button type="button" class="button is-small is-light ml-2 btn-toggle-genes" data-target="${uid}">
        View all (${genes.length})
      </button>
    </div>
  `;
}

export function attachGeneBadgeToggle(root = document) {
  root.addEventListener("click", e => {
    const btn = e.target.closest(".btn-toggle-genes");
    if (!btn) return;

    const target = document.getElementById(btn.dataset.target);
    if (!target) return;

    const hidden = target.style.display === "none" || !target.style.display;
    target.style.display = hidden ? "" : "none";
    btn.textContent = hidden ? "Collapse" : btn.textContent.replace("Collapse", "View all");
    if (!hidden) {
      const total = target.parentElement.querySelectorAll(".tag").length;
      btn.textContent = `View all (${total})`;
    } else {
      btn.textContent = "Collapse";
    }
  }, { once: true });
}

export function sleep(ms = 150) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function waitForNonZeroWidth(el, timeoutMs = 4000) {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    if (el?.getBoundingClientRect?.().width > 0) return true;
    await sleep(50);
  }
  return false;
}

export function clearSVG(svgEl) {
  if (!svgEl) return;
  const svg = d3.select(svgEl);
  svg.on(".zoom", null);
  svg.selectAll("*").remove();

  ["width", "height", "viewBox", "preserveAspectRatio"].forEach(a =>
    svgEl.removeAttribute(a)
  );
}

export function resetSvg(svgEl, { width = 900, height = 560 } = {}) {
  if (!svgEl) return null;
  clearSVG(svgEl);

  const svg = d3.select(svgEl)
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("display", "block")
    .style("margin", "0 auto")
    .style("max-width", "100%")
    .style("overflow", "visible")
    .style("font-family", "sans-serif");

  return svg;
}

export function downloadSVG(svgEl, format = "svg", filename = "plot") {
  if (!svgEl) return;

  const clone = svgEl.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const width = svgEl.viewBox.baseVal.width || svgEl.clientWidth || 800;
  const height = svgEl.viewBox.baseVal.height || svgEl.clientHeight || 600;

  const serializer = new XMLSerializer();
  const svgString = serializer.serializeToString(clone);

  if (format === "svg") {
    const blob = new Blob([svgString], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    return;
  }

  const canvas = document.createElement("canvas");
  canvas.width = width * 2;
  canvas.height = height * 2;
  const ctx = canvas.getContext("2d");
  ctx.scale(2, 2);

  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new Image();

  img.onload = () => {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0);

    if (format === "png") {
      canvas.toBlob(b => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `${filename}.png`;
        a.click();
      });
    }

    URL.revokeObjectURL(url);
  };

  img.src = url;
}

export function normalizeBeforePlot(svgEl, opts = {}) {
  const {
    defaultWidth = 900,
    defaultHeight = 560,
    aspect = null,
    minHeight = 360
  } = opts;

  const parent = svgEl?.parentElement;
  const width = Math.max(420, parent?.clientWidth || defaultWidth);
  const height = Math.max(
    minHeight,
    aspect ? Math.round(width * aspect) : defaultHeight
  );

  const svg = resetSvg(svgEl, { width, height });
  return { svg, width, height };
}

export function ensureVisibleContainer(el) {
  if (!el) return;
  const container = el.closest(".plot-container");
  if (container) {
    container.style.overflow = "auto";
    container.style.maxHeight = "none";
  }
}

export function observeResize(svgEl) {
  const container = svgEl?.closest(".plot-container");
  if (!svgEl || !container || svgEl._resizeObserved) return;

  const ro = new ResizeObserver(() => {
    try {
      const bbox = svgEl.getBBox();
      if (bbox.height > 0) {
        container.style.minHeight = `${Math.ceil(bbox.height + 30)}px`;
      }
    } catch (_) {}
  });

  ro.observe(svgEl);
  svgEl._resizeObserved = true;
}

export function makeSafeId(str) {
  return String(str)
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^a-zA-Z0-9_-]/g, "_");
}

export function getTopNRows(rows, topN = 20) {
  if (!Array.isArray(rows)) return [];
  if (topN === "all") return [...rows];

  return [...rows]
    .sort((a, b) => parsePossibleSci(a.Pvalue) - parsePossibleSci(b.Pvalue))
    .slice(0, topN);
}
