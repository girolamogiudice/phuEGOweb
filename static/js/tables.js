// ============================================================================
// FILE: static/js/tables.js
// DataTables + plot controls for enrichment.json
// Works with:
//   enrichmentData.enrichment["__supernodes__"][DB]
//   enrichmentData.enrichment["Module 1"][DB]
// ============================================================================

import {
  DB_FULLNAME,
  pvalueToSci,
  makeGeneBadgeList,
  escapeCsvCell,
  makeSafeId
} from "./utils_plot.js";

import {
  renderD3Barplot,
  renderD3Dotplot,
  renderD3Heatmap,
  renderD3CirclePlot,
  renderD3Sankey,
  renderD3SlopeChart,
  renderD3ModuleHeatmap,
  renderD3ModuleSimilarityHeatmap   // ADD

} from "./enrichment.js";

const PLOT_RENDERERS = {
  bar: renderD3Barplot,
  dot: renderD3Dotplot,
  heatmap: renderD3Heatmap,
  circle: renderD3CirclePlot,
  sankey: renderD3Sankey,
  slope: renderD3SlopeChart,
  moduleheatmap: renderD3ModuleHeatmap,
  modulesimilarity: renderD3ModuleSimilarityHeatmap   // ADD

};


// ---------------------------------------------------------------------------
// Resize helper for plots
// ---------------------------------------------------------------------------
function autoResizePlot(svgEl) {

  if (!svgEl) return

  const container = svgEl.closest(".plot-container")
  if (!container) return

  const width = container.clientWidth

  if (!width) return

  svgEl.setAttribute("width", width)

}




// ---------------------------------------------------------------------------
// TABLE HTML
// ---------------------------------------------------------------------------
function tableHtml(rows) {
  return `
    <thead>
      <tr>
        <th>ID</th>
        <th>Description</th>
        <th>P-value</th>
        <th>Proteins in Network</th>
        <th>Starting Proteins</th>
        <th>Genes</th>
      </tr>
    </thead>
<tbody>
  ${(rows || []).map((r, idx) => {

    const genesArr = Array.isArray(r.Genes)
      ? r.Genes
      : typeof r.Genes === "string"
        ? r.Genes.split(/[;,]/).map(x => x.trim()).filter(Boolean)
        : Array.isArray(r.genes)
          ? r.genes
          : typeof r.genes === "string"
            ? r.genes.split(/[;,]/).map(x => x.trim()).filter(Boolean)
            : [];

    return `
      <tr data-row-index="${idx}" data-genes="${genesArr.join(",")}" style="user-select:none;">
        <td>${r.Id ?? ""}</td>
        <td>${r.Description ?? ""}</td>
        <td>${pvalueToSci(r.Pvalue)}</td>
        <td>${r["Proteins in Network"] ?? ""}</td>
        <td>${r["Starting Proteins"] ?? ""}</td>
        <td>${makeGeneBadgeList(genesArr)}</td>
      </tr>
    `;
  }).join("")}
</tbody>
  `;
}

// ---------------------------------------------------------------------------
// DATATABLE RENDERER
// ---------------------------------------------------------------------------
export function renderEnrichmentTableWithDataTables(
  container,
  rows,
  { tableId = null, onRowClick = null } = {}
) {
  if (!container) return null;

  const id = tableId || `tbl-${Math.random().toString(36).slice(2, 9)}`;

  container.innerHTML = `<table id="${id}" class="table is-striped is-fullwidth"></table>`;

  const table = container.querySelector("table");
  table.innerHTML = tableHtml(rows || []);

  // ----------------------------
  // DataTables version
  // ----------------------------
  if (window.$ && $.fn?.DataTable) {

    if ($.fn.DataTable.isDataTable(table)) {
      $(table).DataTable().destroy();
    }

    $(table).DataTable({
      pageLength: 10,
      order: [[2, "asc"]],
      scrollX: true,
      destroy: true
    });

    if (onRowClick) {

      $(`#${id} tbody`).off("click", "tr");

      $(`#${id} tbody`).on("click", "tr", function (event) {
        event.preventDefault();
        window.getSelection?.()?.removeAllRanges?.();

        const idx = parseInt(this.dataset.rowIndex, 10);
        const row = rows?.[idx];
        if (!row) return;

        const genesStr = this.dataset.genes || "";
        const genes = genesStr
          .split(/[;,]/)
          .map(x => x.trim())
          .filter(Boolean);

        onRowClick({ ...row, Genes: genes }, event);

      });

    }

  // ----------------------------
  // fallback (no DataTables)
  // ----------------------------
  } else if (onRowClick) {

    table.querySelectorAll("tbody tr").forEach(tr => {

      tr.addEventListener("click", event => {
        event.preventDefault();
        window.getSelection?.()?.removeAllRanges?.();

        const idx = parseInt(tr.dataset.rowIndex, 10);
        const row = rows?.[idx];
        if (!row) return;

        const genesStr = tr.dataset.genes || "";
        const genes = genesStr
          .split(/[;,]/)
          .map(x => x.trim())
          .filter(Boolean);

        onRowClick({ ...row, Genes: genes }, event);

      });

    });

  }

  return table; // optional but nice
}

// ---------------------------------------------------------------------------
// GENERIC DATATABLE (for drugs / diseases)
// ---------------------------------------------------------------------------
export function renderGenericTableWithDataTables(
  container,
  columns,
  rows,
  { tableId = null } = {}
) {
  if (!container) return null;

  const id = tableId || `tbl-${Math.random().toString(36).slice(2, 9)}`;

  // ----------------------------
  // Build header
  // ----------------------------
  const thead = `
    <thead>
      <tr>
        ${columns.map(c => `<th>${c.title}</th>`).join("")}
      </tr>
    </thead>
  `;

  // ----------------------------
  // Build body
  // ----------------------------
  const tbody = `
    <tbody>
      ${(rows || []).map(row => `
        <tr>
          ${columns.map(c => `<td>${row[c.key] ?? ""}</td>`).join("")}
        </tr>
      `).join("")}
    </tbody>
  `;

  container.innerHTML = `<table id="${id}" class="table is-striped is-fullwidth"></table>`;

  const table = container.querySelector("table");
  table.innerHTML = thead + tbody;

  // ----------------------------
  // DataTables
  // ----------------------------
  if (window.$ && $.fn?.DataTable) {

    if ($.fn.DataTable.isDataTable(table)) {
      $(table).DataTable().destroy();
    }

    $(table).DataTable({
      pageLength: 10,
      order: [],
      scrollX: true,
      destroy: true
    });
  }

  return table;
}
// ---------------------------------------------------------------------------
// PLOT CONTAINER
// ---------------------------------------------------------------------------
function makePlotContainer(containerId, allowModuleHeatmap = false) {
  const root = document.createElement("div");
  root.className = "box mt-4";

 root.innerHTML = `
<div class="level is-mobile mb-2">

  <div class="level-left">
    <strong>Summary figures</strong>
  </div>

  <div class="level-right is-flex is-align-items-center" style="gap:.75rem;">

    <label class="is-size-7">Text</label>

    <input class="plot-text-slider"
           type="range"
           min="8"
           max="28"
           step="1"
           value="12"
           style="width:90px">

    <button class="button is-small is-light plot-rotate">
      ↻ Rotate
    </button>

    <div class="select is-small">
      <select class="plot-topn">
        <option value="10">Top 10</option>
        <option value="20" selected>Top 20</option>
        <option value="30">Top 30</option>
        <option value="50">Top 50</option>
        <option value="all">All</option>
      </select>
    </div>

    <div class="dropdown is-right download-dropdown">
      <div class="dropdown-trigger">
        <button class="button is-small is-light"
                type="button"
                aria-haspopup="true"
                aria-controls="${containerId}-download-menu">
          <span>Download</span>
          <span class="icon is-small">▾</span>
        </button>
      </div>

      <div class="dropdown-menu"
           id="${containerId}-download-menu"
           role="menu">

        <div class="dropdown-content">
          <a class="dropdown-item dl-png">PNG</a>
          <a class="dropdown-item dl-svg">SVG</a>
          <a class="dropdown-item dl-pdf">PDF</a>
        </div>

      </div>
    </div>

  </div>

</div>

<div class="buttons are-small mb-3 plot-buttons">
  <button class="button is-link is-light is-active" data-plot="bar">Bar</button>
  <button class="button is-link is-light" data-plot="dot">Dot</button>
  <button class="button is-link is-light" data-plot="heatmap">Heatmap</button>
  <button class="button is-link is-light" data-plot="circle">Circle</button>
  <button class="button is-link is-light" data-plot="sankey">Sankey</button>
  <button class="button is-link is-light" data-plot="slope">Slope</button>
  ${
    allowModuleHeatmap
      ? `<button class="button is-link is-light" data-plot="moduleheatmap">Module heatmap</button>`
      : ""
  }
</div>

<div class="plot-container"
     style="width:100%; overflow:auto; min-height:800px;">

  <div class="plot-viewport" style="display:flex; justify-content:center;">
    <svg id="${containerId}-plot-svg"></svg>
  </div>

</div>
`;


  return root;
}

// ---------------------------------------------------------------------------
// DOWNLOAD HELPERS
// ---------------------------------------------------------------------------
function saveBlob(blob, filename) {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadPlot(svgEl, type, filenameBase = "plot") {
  if (!svgEl) return;

  const serializer = new XMLSerializer();
  const svgString = serializer.serializeToString(svgEl);

  if (type === "svg") {
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    saveBlob(blob, `${filenameBase}.svg`);
    return;
  }

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.onload = () => {


     const MAX_DIM = 2000;
     
     let width = img.width || 1600;
     let height = img.height || 1000;
     
     const scale = Math.min(1, MAX_DIM / Math.max(width, height));
     width *= scale;
     height *= scale;


    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(img, 0, 0, width, height);

    if (type === "png") {
      canvas.toBlob(blob => {
        saveBlob(blob, `${filenameBase}.png`);
        URL.revokeObjectURL(url);
      }, "image/png");
      return;
    }

  };

  img.onerror = () => {
    URL.revokeObjectURL(url);
    console.warn("Could not export plot.");
  };

  img.src = url;
}

// ---------------------------------------------------------------------------
// PLOT RENDERER
// ---------------------------------------------------------------------------
function renderPlot({
  plotType,
  rows,
  svgEl,
  topN,
  heatmapData,
  dbKey
}) {

  const fn = PLOT_RENDERERS[plotType];
  if (!fn || !svgEl) return;

  // -----------------------------
  // Determine number of rows
  // -----------------------------

  let n = 0;

  if (topN === "all") {
    n = rows?.length || 0;
  } else {
    n = Math.min(topN, rows?.length || 0);
  }

  // -----------------------------
  // Better height scaling
  // -----------------------------

  let height = 600;

  if (plotType === "bar" || plotType === "dot")
    height = Math.max(600, n * 34);

  if (plotType === "heatmap")
    height = Math.max(600, n * 38);

  if (plotType === "sankey")
    height = Math.max(600, n * 30);

  if (plotType === "circle")
    height = 750;

  if (plotType === "moduleheatmap")
    height = Math.max(600, n * 36);

  height = Math.min(height, 2000);

  // -----------------------------
  // Force SVG to fill container
  // -----------------------------

// clear previous drawing
svgEl.innerHTML = "";

  // -----------------------------
  // render
  // -----------------------------

  if (plotType === "moduleheatmap") {
    fn(heatmapData, svgEl, { topN, dbKey });
  } else if (plotType === "heatmap") {
    fn(heatmapData, svgEl, { topN, dbKey });
  } else {
    fn(rows, svgEl, { topN });
  }
}

// ---------------------------------------------------------------------------
// PLOT CONTROLS
// ---------------------------------------------------------------------------
function attachPlotControls({
  plotRoot,
  rows,
  heatmapData,
  dbKey,
  filenameBase = "plot"
}) {
  const svgEl = plotRoot.querySelector("svg");
  const topNSel = plotRoot.querySelector(".plot-topn");
  const buttons = [...plotRoot.querySelectorAll("[data-plot]")];
  const textSlider = plotRoot.querySelector(".plot-text-slider")
  let textSize = 12
  const dropdown = plotRoot.querySelector(".download-dropdown");
  const trigger = plotRoot.querySelector(".dropdown-trigger");
  const dlPng = plotRoot.querySelector(".dl-png");
  const dlSvg = plotRoot.querySelector(".dl-svg");
  const dlPdf = plotRoot.querySelector(".dl-pdf");

const rotateBtn = plotRoot.querySelector(".plot-rotate")

let rotated = false

if (rotateBtn) {

  rotateBtn.addEventListener("click", () => {

    const viewport = plotRoot.querySelector(".plot-viewport")
    const container = plotRoot.querySelector(".plot-container")

    rotated = !rotated

    if (!viewport) return

    if (rotated) {

      viewport.style.transform = "rotate(90deg)"
      viewport.style.transformOrigin = "center"

      const svgWidth = svgEl.getAttribute("width")
      const svgHeight = svgEl.getAttribute("height")

      if (container && svgWidth && svgHeight) {
        container.style.height = svgWidth + "px"
      }

    } else {

      viewport.style.transform = "rotate(0deg)"

      const svgHeight = svgEl.getAttribute("height")

      if (container && svgHeight) {
        container.style.height = svgHeight + "px"
      }

    }

  })

}

window.addEventListener("resize", () => {
  autoResizePlot(svgEl)
})

  function getActivePlot() {
    return buttons.find(b => b.classList.contains("is-active"))?.dataset.plot || "bar";
  }


function redraw() {

  const plotType = getActivePlot()
  const topN = topNSel.value === "all" ? "all" : parseInt(topNSel.value, 10)

  renderPlot({ plotType, rows, svgEl, topN, heatmapData, dbKey })

  // adjust width after render
  setTimeout(() => {

    autoResizePlot(svgEl)

    svgEl.querySelectorAll("text").forEach(t => {
      t.style.fontSize = textSize + "px"
    })

  }, 30)

}

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      redraw();
    });
  });

  topNSel.addEventListener("change", redraw);
if (textSlider) {

  textSlider.addEventListener("input", e => {

    textSize = parseInt(e.target.value)

    svgEl.querySelectorAll("text").forEach(t => {
      t.style.fontSize = textSize + "px"
    })

  })

}
  if (trigger && dropdown) {
    trigger.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      dropdown.classList.toggle("is-active");
    });

    document.addEventListener("click", () => {
      dropdown.classList.remove("is-active");
    });
  }

  if (dlPng) {
    dlPng.addEventListener("click", e => {
      e.preventDefault();
      dropdown?.classList.remove("is-active");
      downloadPlot(svgEl, "png", filenameBase);
    });
  }

  if (dlSvg) {
    dlSvg.addEventListener("click", e => {
      e.preventDefault();
      dropdown?.classList.remove("is-active");
      downloadPlot(svgEl, "svg", filenameBase);
    });
  }

  setTimeout(redraw, 50);
}

// ---------------------------------------------------------------------------
// ENRICHMENT PANEL
// ---------------------------------------------------------------------------
export function buildEnrichmentPanel({
  mountEl,
  rows,
  dbKey,
  direction,
  heatmapData = null,
  allowModuleHeatmap = false,
  title = null,
  onRowClick = null,
  onRestoreNetwork = null
}) {
  if (!mountEl) return;

  mountEl.innerHTML = "";

  if (title) {
    const h = document.createElement("h4");
    h.className = "title is-6";
    h.textContent = title;
    mountEl.appendChild(h);
  }




  if (onRowClick) {
    const help = document.createElement("div");
    help.className = "notification is-light py-2 px-3 mb-3";
    help.style.fontSize = "0.85rem";
    help.innerHTML = `
      <div class="level is-mobile mb-0">
        <div class="level-left">
          <span>
            Click an enrichment row to highlight its genes in the network.
            Shift-click a row to isolate that gene set.
          </span>
        </div>
        <div class="level-right">
          <button class="button is-small is-light enrichment-restore-network" type="button">
            Restore network
          </button>
        </div>
      </div>
    `;
    help
      .querySelector(".enrichment-restore-network")
      ?.addEventListener("click", () => onRestoreNetwork?.());
    mountEl.appendChild(help);
  }


  // -----------------------
  // TABLE
  // -----------------------

  const tableWrap = document.createElement("div");
  mountEl.appendChild(tableWrap);

  renderEnrichmentTableWithDataTables(
    tableWrap,
    rows,
    { onRowClick }
  );


  // -----------------------
  // PLOT AREA
  // -----------------------

  const plotId = `plot-${makeSafeId(dbKey)}-${Math.random().toString(36).slice(2,8)}`;
  const plotRoot = makePlotContainer(plotId, allowModuleHeatmap);

  mountEl.appendChild(plotRoot);

  attachPlotControls({
    plotRoot,
    rows,
    heatmapData,
    dbKey,
    filenameBase: plotId
  });
}

// ---------------------------------------------------------------------------
// DB BUTTONS
// ---------------------------------------------------------------------------
export function buildDbButtons({
  mountEl,
  dbKeys,
  activeDb,
  onSelect,
  direction,
  moduleKey
}) {
  if (!mountEl) return;

  mountEl.innerHTML = "";

  const prop = window.getPropagation?.();
  const exp  = window.currentExperiment?.();
  const base = window.APP_BASE;
  const uuid = window.UUID;
  const results = window.getResults?.();
  const paths = results?.directions?.[direction]?.paths;

  function enrichmentDownloadPath(db) {
    if (!paths) return null;

    if (moduleKey === "__supernodes__") {
      if (paths.enrichment_supernodes_dir) {
        return `${paths.enrichment_supernodes_dir}/${db}fisher.txt`;
      }
      return paths.supernodes_dir ? `${paths.supernodes_dir}/enrichment/${db}fisher.txt` : null;
    }

    const moduleId = String(moduleKey || "").match(/\d+/)?.[0];

    if (moduleId && paths.modules?.tables_pattern) {
      const tablesDir = paths.modules.tables_pattern.replace("{id}", moduleId);
      return tablesDir.replace("/tables/modules/", "/modules/") + `/enrichment/${db}fisher.txt`;
    }

    if (moduleId && paths.modules?.graphml_pattern) {
      return paths.modules.graphml_pattern
        .replace("networks/modules_sigma/module_{id}.graphml", `modules/module_${moduleId}/enrichment/${db}fisher.txt`)
        .replace("{id}", moduleId);
    }

    return null;
  }

  dbKeys.forEach(db => {

    const group = document.createElement("div");
    group.className = "field has-addons mr-3 mb-2";

    // -------------------------
    // MAIN DB BUTTON
    // -------------------------

    const btn = document.createElement("button");

    btn.className = `button is-small ${db === activeDb ? "is-primary" : "is-light"}`;
    btn.textContent = DB_FULLNAME[db] || db;

    btn.onclick = () => onSelect(db);

    // -------------------------
    // DOWNLOAD BUTTON
    // -------------------------

    const dl = document.createElement("a");

    dl.className = "button is-small is-light";
    dl.innerHTML = "⬇";

    const dbLabel = (DB_FULLNAME[db] || db).replace(/\s+/g,"_");
    const relativePath = enrichmentDownloadPath(db);

    if (relativePath && base && uuid && exp && prop) {
      dl.href = `${base}/download/${encodeURIComponent(uuid)}/${encodeURIComponent(exp)}/${encodeURIComponent(prop)}/${relativePath}`;
    } else {
      dl.href = "#";
      dl.classList.add("is-static");
      dl.setAttribute("aria-disabled", "true");
    }

    dl.download = `${direction}_${dbLabel}_enrichment.tsv`;

    // -------------------------
    // APPEND
    // -------------------------

    group.appendChild(btn);
    group.appendChild(dl);

    mountEl.appendChild(group);

  });
}
// ---------------------------------------------------------------------------
// MOUNT SUPERNODE / MODULE ENRICHMENT
// ---------------------------------------------------------------------------
export function mountModuleOrSupernodeEnrichment({
  buttonsEl,
  contentEl,
  enrichmentData,
  moduleKey,
  direction,
  heatmapData = null,
  allowModuleHeatmap = false,
  onRowClick = null,
  onRestoreNetwork = null
}) {
  if (!buttonsEl || !contentEl) return;

  const moduleEntry = enrichmentData?.enrichment?.[moduleKey] || {};
  const dbKeys = Object.keys(moduleEntry);

  if (!dbKeys.length) {
    contentEl.innerHTML = `<p class="has-text-grey">No enrichment available.</p>`;
    buttonsEl.innerHTML = "";
    return;
  }

  let activeDb = dbKeys[0];

  function draw(db) {
    activeDb = db;

buildDbButtons({
  mountEl: buttonsEl,
  dbKeys,
  activeDb,
  onSelect: draw,
  direction,
  moduleKey
});

  buildEnrichmentPanel({
    mountEl: contentEl,
    rows: moduleEntry[db] || [],
    dbKey: db,
    direction: direction,
    heatmapData,
    allowModuleHeatmap,
    onRowClick,
    onRestoreNetwork
  });
  }

  draw(activeDb);
}
