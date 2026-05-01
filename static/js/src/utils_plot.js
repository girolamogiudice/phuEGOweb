// ============================================================================
// FILE: static/js/utils_plot.js
// Shared plotting utilities for enrichment visualizations
// ============================================================================
// ---------------------------------------------------------------------------
// Clear an SVG safely before re-rendering
// ---------------------------------------------------------------------------

export const DB_FULLNAME = {
  'C': 'Cellular Component',
  'P': 'Biological Process',
  'F': 'Molecular Function',
  'K': 'KEGG',
  'R': 'Reactome',
  'RT': 'Reactome Total',
  'B': 'Bioplanet'
};
export function dbKeyToLabel(dbKey) {
  const labels = {
    C: 'Cellular Component',
    P: 'Biological Process',
    F: 'Molecular Function',
    K: 'KEGG',
    R: 'Reactome',
    RT: 'Reactome Total'
  };
  return labels[dbKey] || dbKey;
}
// ---------------------------------------------------------------------------
// Parse numbers including scientific notation strings
// ---------------------------------------------------------------------------
export function parsePossibleSci(value) {
  if (value == null) return NaN;
  if (typeof value === "number") return value;
  const s = String(value).trim();
  if (s === "") return NaN;
  const n = Number(s);
  return isNaN(n) ? parseFloat(s.replace(",", ".")) : n;
}

// ---------------------------------------------------------------------------
// Escape CSV cells properly
// ---------------------------------------------------------------------------
export function escapeCsvCell(s) {
  if (s === null || s === undefined) return '';
  const str = String(s);
  if (str.includes('"') || str.includes(',') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

// ---------------------------------------------------------------------------
// Render gene list as Bootstrap badges (collapsible if long)
// ---------------------------------------------------------------------------
export function makeGeneBadgeList(geneStr) {
  if (!geneStr) return '';
  const genes = String(geneStr).split(/[,;]\s*|\s+/).filter(x => x);
  const preview = genes.slice(0, 4).map(g => `<span class="badge bg-light text-dark me-1 mb-1">${g}</span>`).join(' ');
  const full = genes.map(g => `<span class="badge bg-light text-dark me-1 mb-1">${g}</span>`).join(' ');
  const id = `g-${Math.random().toString(36).slice(2, 9)}`;
  return `
    <div class="gene-cell" data-state="collapsed" data-preview='${JSON.stringify(preview)}' data-full='${JSON.stringify(full)}'>
      <div class="gene-preview">${preview}
        <button type="button" class="btn btn-sm btn-outline-secondary btn-toggle-genes" style="padding:.15rem .4rem; font-size:.8rem;">View All</button>
      </div>
    </div>`;
}


// ---------------------------------------------------------------------------
// Convert numeric p-values to scientific notation
// ---------------------------------------------------------------------------
export function pvalueToSci(s) {
  if (s === null || s === undefined || s === '') return '';
  const num = parseFloat(s);
  if (isNaN(num)) return s;
  return num.toExponential(2);
}

// ---------------------------------------------------------------------------
// Clear an SVG safely (used before re-rendering D3 charts)
// ---------------------------------------------------------------------------
export function clearSVG(svgEl) {
  if (!svgEl) return;
  try {
    const sel = d3.select(svgEl);
    sel.on('.zoom', null);
    sel.selectAll('*').remove();
  } catch (_) {}
  ['width', 'height', 'viewBox', 'preserveAspectRatio', 'transform'].forEach(a => svgEl.removeAttribute(a));
  svgEl.style.width = '';
  svgEl.style.height = '';
  svgEl.style.display = '';
  svgEl.style.margin = '';
  svgEl.style.overflow = '';
}
// ---------------------------------------------------------------------------
// Fully reset and clear an SVG before rendering a new D3 plot
// ---------------------------------------------------------------------------
export function resetSvg(svgEl, { width = 800, height = 600 } = {}) {
  if (!svgEl) return;
  const svg = d3.select(svgEl);
  svg.on('.zoom', null); // remove zoom listeners
  svg.selectAll('*').remove();
  svg
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('display', 'block')
    .style('margin', '0 auto')
    .style('overflow', 'visible')
    .style('font-family', 'sans-serif');
  return svg;
}

// ---------------------------------------------------------------------------
// Normalize an SVG element before plotting
// ---------------------------------------------------------------------------
export function normalizeBeforePlot_test(svgEl, opts = {}) {
  if (!svgEl) return { width: opts.defaultSize || 800, height: opts.defaultSize || 600 };
  const { defaultSize = 800, aspect = 0.6, minHeight = 400 } = opts;
  const sel = d3.select(svgEl);
  sel.on('.zoom', null);
  sel.selectAll('*').remove();

  ['width', 'height', 'viewBox', 'preserveAspectRatio', 'transform'].forEach(a => svgEl.removeAttribute(a));
  const parent = svgEl.parentElement;
  const parentW = parent?.clientWidth || defaultSize;
  const width = Math.max(200, parentW);
  const height = Math.max(minHeight, Math.round(width * aspect));

  sel
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('display', 'block')
    .style('margin', '0 auto')
    .style('max-width', '100%')
    .style('box-sizing', 'border-box')
    .style('overflow', 'visible');

  return { width, height };
}

// ---------------------------------------------------------------------------
// Utility helpers (used in network.js and results_test)
// ---------------------------------------------------------------------------
export const sleep = (ms = 200) => new Promise(r => setTimeout(r, ms));

export async function waitForNonZeroWidth(el, timeoutMs = 8000) {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    const rect = el?.getBoundingClientRect();
    if (rect && rect.width > 0) return true;
    await sleep(100);
  }
  throw new Error('Timeout: element width still zero');
}

// ---------------------------------------------------------------------------
// Generate safe HTML IDs
// ---------------------------------------------------------------------------
export function makeSafeId(str) {
  return String(str)
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-zA-Z0-9_-]/g, '_');
}

// ---------------------------------------------------------------------------
// Prettify a module/network key for tab display
// ---------------------------------------------------------------------------
export function prettifyKey(k) {
  if (!k) return '';
  const s = String(k);
  if (/^\d+$/.test(s)) return `Module ${s}`;
  if (s.toLowerCase().includes('supernodes')) return 'Supernodes Network';
  return s
    .replace(/_increased/i, '')
    .replace(/_decreased/i, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Order keys: supernodes first, then numeric, then alphabetical
// ---------------------------------------------------------------------------
export function getOrderedKeys(obj) {
  if (!obj || typeof obj !== 'object') return [];
  const keys = Object.keys(obj);
  keys.sort((a, b) => {
    const aSuper = a.toLowerCase().includes('supernodes');
    const bSuper = b.toLowerCase().includes('supernodes');
    if (aSuper && !bSuper) return -1;
    if (!aSuper && bSuper) return 1;
    const aNum = parseFloat(a), bNum = parseFloat(b);
    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
  });
  return keys;
}

// ---------------------------------------------------------------------------
// Scroll to top utility
// ---------------------------------------------------------------------------
export function scrollToTop() {
  try { window.scrollTo({ top: 0, behavior: 'smooth' }); }
  catch (_) { window.scrollTo(0, 0); }
}

// ============================================================================
// UNIVERSAL D3 ZOOM + PAN HANDLER
// ============================================================================

/**
 * Enables consistent zoom and pan behavior across all D3 plots.
 *
 * @param {d3.Selection} svg      - Root SVG selection
 * @param {d3.Selection} mainGroup - The <g> element containing axes + plot
 * @param {Object} [opts]          - Optional settings
 * @param {Array} [opts.scaleExtent=[0.5,5]] - Min/max zoom scale
 * @param {boolean} [opts.resetOnDoubleClick=true] - Double-click resets zoom
 */
export function enableZoomAndPan(svg, mainGroup, opts = {}) {
  if (!svg || !mainGroup) return;

  const { scaleExtent = [0.5, 5], resetOnDoubleClick = true } = opts;

  // Define zoom behavior
  const zoom = d3.zoom()
    .scaleExtent(scaleExtent)
    .on("zoom", (event) => {
      mainGroup.attr("transform", event.transform);
    });

  // Apply to SVG
  svg.call(zoom);

  // Optional: reset zoom on double click
  if (resetOnDoubleClick) {
    svg.on("dblclick.zoom", () => {
      svg.transition().duration(350).call(zoom.transform, d3.zoomIdentity);
    });
  }

  return zoom;
}

// ---------------------------------------------------------------------------
// Normalize an SVG element before plotting (universal version)
// - Clears old contents and zooms
// - Expands parent container (avoids clipping / truncation)
// - Computes consistent width & height
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Normalize an SVG element before plotting (universal version)
// ---------------------------------------------------------------------------
export function normalizeBeforePlot(svgEl, opts = {}) {
  if (!svgEl) return { width: opts.defaultSize || 800, height: opts.defaultSize || 600, svg: null };

  const { defaultSize = 800, aspect = 0.6, minHeight = 400 } = opts;
  const sel = d3.select(svgEl);

  // Clear any previous content and zoom handlers
  sel.on('.zoom', null);
  sel.selectAll('*').remove();

  // Remove stale attributes that can interfere with layout
  ['width', 'height', 'viewBox', 'preserveAspectRatio', 'transform'].forEach(a =>
    svgEl.removeAttribute(a)
  );

  // --- Expand container automatically to avoid clipping ---
  const container = svgEl.closest('.plot-container');
  if (container) {
    container.style.overflow = 'visible';
    container.style.maxHeight = 'none';
    container.style.minHeight = '1000px'; // ensures space for Sankey or large heatmaps
  }

  // --- Compute dimensions ---
  const parent = svgEl.parentElement;
  const parentW = parent?.clientWidth || defaultSize;
  const width = Math.max(200, parentW);
  const height = Math.max(minHeight, Math.round(width * aspect));

  // --- Apply consistent SVG styling ---
  sel
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .style('display', 'block')
    .style('margin', '0 auto')
    .style('max-width', '100%')
    .style('box-sizing', 'border-box')
    .style('overflow', 'visible')
    .style('font-family', 'sans-serif');

  // ✅ Return the svg selection as well
  return { width, height, svg: sel };
}



// inside utils_plot.js
export function ensureVisibleContainer(svgEl) {
  // unwrap if it's a D3 selection
  if (svgEl && typeof svgEl.node === "function") {
    svgEl = svgEl.node();
  }
  if (!svgEl || !svgEl.closest) return;

  const parent = svgEl.closest(".box, .container, body");
  if (parent && parent.scrollIntoView) {
    parent.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}


document.addEventListener('click', function (e) {
  const btn = e.target.closest('.btn-toggle-genes');
  if (!btn) return;

  const wrapper = btn.closest('.gene-cell');
  if (!wrapper) return; // 🔐 FIX

  const preview = JSON.parse(wrapper.getAttribute('data-preview') || '""');
  const full = JSON.parse(wrapper.getAttribute('data-full') || '""');
  const state = wrapper.getAttribute('data-state') || 'collapsed';

  const newState = state === 'collapsed' ? 'expanded' : 'collapsed';
  wrapper.setAttribute('data-state', newState);

  const content =
    newState === 'collapsed'
      ? `${preview}
         <button type="button"
           class="btn btn-sm btn-outline-secondary btn-toggle-genes"
           style="padding:.15rem .4rem; font-size:.8rem;">
           View All
         </button>`
      : `${full}
         <button type="button"
           class="btn btn-sm btn-outline-secondary btn-toggle-genes"
           style="padding:.15rem .4rem; font-size:.8rem;">
           Collapse
         </button>`;

  const previewDiv = wrapper.querySelector('.gene-preview');
  if (previewDiv) previewDiv.innerHTML = content; // 🔐 safe
});


// utils_plot.js
export function observeResize(svgEl) {
  const container = svgEl?.closest('.plot-container');
  if (!container || !svgEl) return;

  const resize = () => {
    const bbox = svgEl.getBBox?.();
    if (bbox?.height > 0) {
      container.style.height = (bbox.height + 40) + 'px';
    }
  };

  resize(); // Set immediately

  if (!svgEl._resizeObserver) {
    const observer = new ResizeObserver(() => resize());
    observer.observe(svgEl);
    svgEl._resizeObserver = observer;
  }
}


export function forceCardReflow(svgEl) {
  const container = svgEl.closest(".box mb-5");
  if (container) {
    container.style.height = "auto";           // Let it shrink if needed
    container.style.maxHeight = "none";        // Remove any leftover constraints
    container.style.overflow = "visible";      // Optional: show full content
  }
}
