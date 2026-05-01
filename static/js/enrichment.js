
// ============================================================================
// FILE: static/js/enrichment.js
// Cleaned phuEGO enrichment plotting utilities
// - unified preprocessing
// - stable sizing / container growth
// - preserves legacy exported names for compatibility
// - dotplot uses -log10(p)
// - bubble plot kept as alias for backward compatibility
// - circle plot restores labels + hover interactions
// - module heatmap works with enrichment_heatmap.json grouped by DB
// ============================================================================

/* global d3, d3Sankey */

import {
  normalizeBeforePlot,
  ensureVisibleContainer,
  waitForNonZeroWidth,
  observeResize,
  enablePanZoom
} from './utils_plot.js';

// ---------------------------------------------------------------------------
// Numeric parsing
// ---------------------------------------------------------------------------
export function parsePossibleSci(value) {
  if (value == null || value === '') return NaN;
  if (typeof value === 'number') return value;

  if (typeof value === 'string') {
    const cleaned = value.trim()
      .replace(',', '.')
      .replace(/[^0-9eE.\-+]/g, '');

    const sciMatch = cleaned.match(/^[-+]?\d*\.?\d+(e[-+]?\d+)?$/i);
    if (!sciMatch) return NaN;

    const parsed = Number(cleaned);
    return Number.isNaN(parsed) ? NaN : parsed;
  }

  return NaN;
}

// ---------------------------------------------------------------------------
// Shared preprocessing
// ---------------------------------------------------------------------------
export function preprocessEnrichmentData(rows, topN = 10) {
  if (!Array.isArray(rows)) return [];

  const EPS = 1e-12;

  const parsed = rows.map((r) => {
    const term = r.Id || r.term || '';
    const desc = r.Description || r.Desc || term || '';
    const pvalRaw = r.Pvalue ?? r.pvalue ?? 1;
    const pval = Math.max(parsePossibleSci(pvalRaw), 1e-300);
    const inNet = +r['Proteins in Network'] || +r.inNetwork || 0;
    const total = +r['Starting Proteins'] || +r.total || 0;
    const genesRaw = r.Genes || r.genes || [];

    const genes = typeof genesRaw === 'string'
      ? genesRaw.split(/[,;]\s*/).filter(Boolean)
      : Array.isArray(genesRaw)
        ? genesRaw.filter(Boolean)
        : [];

    return {
      raw: r,
      term,
      desc,
      pval,
      logp: -Math.log10(pval),
      inNetwork: inNet,
      total,
      log2fc: Math.log2((inNet + EPS) / (total + EPS)),
      genes,
      size: genes.length,
    };
  });

  parsed.sort((a, b) => a.pval - b.pval);
  return topN === 'all' ? parsed : parsed.slice(0, topN);
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
function clearSvg(svgEl) {
  if (!svgEl) return null;
  const svg = d3.select(svgEl);
  svg.on('.zoom', null);
  svg.selectAll('*').remove();
  return svg;
}

function setPlotContainerHeight(svgEl, px) {
  const plotContainer = svgEl?.closest('.plot-container');
  if (plotContainer && Number.isFinite(px) && px > 0) {
    plotContainer.style.height = `${Math.ceil(px)}px`;
    plotContainer.style.minHeight = `${Math.ceil(px)}px`;
    plotContainer.style.maxHeight = 'none';
    plotContainer.style.overflow = 'auto';
  }
}

function makeTooltip(sel, textFn) {
  sel.append('title').text(textFn);
}

function trunc(s, n = 48) {
  const x = String(s || '');
  return x.length > n ? `${x.slice(0, n - 1)}…` : x;
}

function getTopN(options, fallback = 20) {
  return options?.topN === 'all' ? 'all' : parseInt(options?.topN ?? fallback, 10);
}

// ---------------------------------------------------------------------------
// Generic zoom / pan behaviour
// ---------------------------------------------------------------------------
function enableZoom(svg, root) {

  const zoom = d3.zoom()
    .scaleExtent([0.5, 8])
    .on("zoom", (event) => {
      root.attr("transform", event.transform)
    })

  svg.call(zoom)

  // double click reset
  svg.on("dblclick.zoom", null)

  svg.on("dblclick", () => {
    svg.transition().duration(300).call(
      zoom.transform,
      d3.zoomIdentity
    )
  })

}


// ---------------------------------------------------------------------------
// BARPLOT
// ---------------------------------------------------------------------------
export function renderD3Barplot(rows, svgEl, options = {}) {
  const data = preprocessEnrichmentData(rows, getTopN(options, 10));
  if (!svgEl) return;
  const maxLabelLength = d3.max(data, d => (d.desc || "").length) || 10;

  const margin = {
    top: 20,
    right: 40,
    bottom: 55,
    left: Math.max(140, Math.min(420, maxLabelLength * 6))
  };

  const innerW = 760;
  const innerH = Math.max(220, data.length * 28);
  const width  = svgEl.parentElement.clientWidth || (innerW + margin.left + margin.right)
  const height = innerH + margin.top + margin.bottom

  const { svg } = normalizeBeforePlot(svgEl, { defaultSize: width, aspect: height / width, minHeight: height });
  clearSvg(svgEl);
  svg
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`);

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append("g").attr("class", "zoom-root");
  
  const g = root.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  
  enablePanZoom(svg, root);

  const x = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.logp) || 1])
    .nice()
    .range([0, innerW]);

  const y = d3.scaleBand()
    .domain(data.map(d => d.desc))
    .range([0, innerH])
    .padding(0.18);

  const color = d3.scaleSequential(d3.interpolateBlues)
    .domain([0, d3.max(data, d => d.logp) || 1]);

  const bars = g.selectAll('.bar')
    .data(data)
    .join('rect')
    .attr('class', 'bar')
    .attr('x', 0)
    .attr('y', d => y(d.desc))
    .attr('width', d => x(d.logp))
    .attr('height', y.bandwidth())
    .attr('fill', d => color(d.logp));

  makeTooltip(bars, d => `${d.desc}\n-log10(p)=${d.logp.toFixed(2)}\nGenes=${d.size}`);

  g.append('g').call(d3.axisLeft(y).tickFormat(d => trunc(d, 52)));
  g.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x));

  svg.append('text')
    .attr('x', margin.left + innerW / 2)
    .attr('y', height - 10)
    .attr('text-anchor', 'middle')
    .style('font-size', '13px')
    .text('-log₁₀(p-value)');

  observeResize(svgEl);
}

// ---------------------------------------------------------------------------
// DOTPLOT (x = -log10(p), y = term)
// ---------------------------------------------------------------------------
export function renderD3Dotplot(rows, svgEl, options = {}) {
  const data = preprocessEnrichmentData(rows, getTopN(options, 20));
  if (!svgEl) return;

  const maxLabelLength = d3.max(data, d => (d.desc || "").length) || 10;
  const margin = {
    top: 20,
    right: 60,
    bottom: 55,
    left: Math.max(160, Math.min(420, maxLabelLength * 6))
  };

  const innerW = 720;
  const innerH = Math.max(240, data.length * 28);
  const width  = svgEl.parentElement.clientWidth || (innerW + margin.left + margin.right)
  const height = innerH + margin.top + margin.bottom

  const { svg } = normalizeBeforePlot(svgEl, { defaultSize: width, aspect: height / width, minHeight: height });
  clearSvg(svgEl);
  svg
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`);

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append("g").attr("class", "zoom-root");
  
  const g = root.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  
  enablePanZoom(svg, root);

  const x = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.logp) || 1])
    .nice()
    .range([0, innerW]);

  const y = d3.scaleBand()
    .domain(data.map(d => d.desc))
    .range([0, innerH])
    .padding(0.25);

  const r = d3.scaleSqrt()
    .domain(d3.extent(data, d => d.size))
    .range([4, 12]);

  const color = d3.scaleSequential(d3.interpolatePlasma)
    .domain(d3.extent(data, d => d.logp).reverse());

  g.append('g').call(d3.axisLeft(y).tickFormat(d => trunc(d, 54)));
  g.append('g')
    .attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x));

  const pts = g.selectAll('circle')
    .data(data)
    .join('circle')
    .attr('cx', d => x(d.logp))
    .attr('cy', d => y(d.desc) + y.bandwidth() / 2)
    .attr('r', d => r(d.size || 1))
    .attr('fill', d => color(d.logp))
    .attr('opacity', 0.9)
    .attr('stroke', '#333')
    .attr('stroke-width', 0.4);

  makeTooltip(pts, d => `${d.desc}\n-log10(p)=${d.logp.toFixed(2)}\nGenes=${d.size}`);

  svg.append('text')
    .attr('x', margin.left + innerW / 2)
    .attr('y', height - 10)
    .attr('text-anchor', 'middle')
    .style('font-size', '13px')
    .text('-log₁₀(p-value)');

  observeResize(svgEl);
}

// ---------------------------------------------------------------------------
// BUBBLE kept as alias for compatibility
// ---------------------------------------------------------------------------
export function renderD3BubblePlot(rows, svgEl, options = {}) {
  return renderD3Dotplot(rows, svgEl, options);
}

// ---------------------------------------------------------------------------
// HEATMAP
// ---------------------------------------------------------------------------

export function renderD3Heatmap(data, svgEl, options = {}) {
  if (!svgEl || !data) return;
  ensureVisibleContainer(svgEl, 800);

  const dbKey = options.dbKey || 'P';
  const section = options.section || "__supernodes__";
  const topN = options?.topN === 'all' ? 'all' : parseInt(options?.topN ?? 20, 10);

  const rows = data?.gene_term?.[section]?.[dbKey] || [];
  if (!rows.length) {
    clearSvg(svgEl);
    return;
  }

  // -----------------------------
  // terms + genes
  // -----------------------------
  let terms = rows.map(r => r.term);
  if (topN !== 'all') terms = terms.slice(0, topN);

  const selectedRows = rows.filter(r => terms.includes(r.term));
  const genes = Array.from(new Set(selectedRows.flatMap(r => r.genes || [])));

  if (!terms.length || !genes.length) {
    clearSvg(svgEl);
    return;
  }

  // -----------------------------
  // lookup
  // -----------------------------
  const termMap = new Map();
  
  selectedRows.forEach(r => {
    const score = r.score
    termMap.set(r.term, {
      genes: new Set(r.genes || []),
      score
    });
  });
  
  // -----------------------------
  // sparse matrix
  // -----------------------------


   const cellData = [];
   
   terms.forEach(term => {
     const entry = termMap.get(term);
     if (!entry) return;
   
     genes.forEach(gene => {
       if (entry.genes.has(gene)) {
         cellData.push({
           term,
           gene,
           value: entry.score   // 👈 now meaningful
         });
       }
     });
   });

  // -----------------------------
  // layout (IMPORTANT: swapped)
  // -----------------------------
  const cellSize = Math.max(8, Math.min(10, 600 / Math.max(terms.length, 1)));

  const maxLabelLength = d3.max(terms, d => d.length) || 10;
  
  const margin = {
    top: 50,
    right: 40,
    left: 160,
    bottom: Math.max(140, Math.min(320, maxLabelLength * 7))
  };


  const innerW = terms.length * cellSize;   // X = terms
  const innerH = genes.length * cellSize;   // Y = genes

  const width = Math.max(
    svgEl.parentElement.clientWidth || 900,
    innerW + margin.left + margin.right
  );

  const EXTRA_AXIS_SPACE = 3;
  
  const height = innerH + margin.top + margin.bottom + EXTRA_AXIS_SPACE;
  const { svg } = normalizeBeforePlot(svgEl, {
    defaultSize: width,
    aspect: height / width,
    minHeight: height
  });

  clearSvg(svgEl);

  svg
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .style("overflow", "visible");

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append('g').attr('class', 'zoom-root');
  const g = root.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  enableZoom(svg, root);

  // -----------------------------
  // scales
  // -----------------------------
  const x = d3.scaleBand()
    .domain(terms)
    .range([0, innerW])
    .padding(0.05);
  
  const y = d3.scaleBand()
    .domain(genes)
    .range([0, innerH])
    .padding(0.05);
  
  // -----------------------------
  // row background (use genes, not data)
  // -----------------------------

  g.selectAll(".col-bg")
    .data(terms)
    .join("rect")
    .attr("class", "col-bg")
    .attr("x", d => x(d))
    .attr("y", 0)
    .attr("width", x.bandwidth())
    .attr("height", innerH)
    .attr("fill", (d, i) => i % 2 === 0 ? "#fafafa" : "#f0f0f0");
  
  g.selectAll(".col-bg")
    .on("mouseenter", function () {
      d3.select(this).attr("fill", "#e6f2ff");
    })
    .on("mouseleave", function (event, d) {
      const i = terms.indexOf(d);
      d3.select(this).attr("fill", i % 2 === 0 ? "#fafafa" : "#f0f0f0");
    });
  
  // -----------------------------
  // viridis color
  // -----------------------------

  const values = cellData.map(d => d.value).sort(d3.ascending);
  
  const minVal = values[0];
  const maxVal = d3.quantile(values, 0.9);  // compress top 10%
  
  const color = d3.scaleSequential(d3.interpolateViridis)
    .domain([minVal, maxVal])
    .clamp(true);
  
  
  // -----------------------------
  // draw heatmap cells
  // -----------------------------
  const rects = g.selectAll(".heat-cell")
    .data(cellData)
    .join("rect")
    .attr("class", "heat-cell")
    .attr("x", d => x(d.term))
    .attr("y", d => y(d.gene))
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("fill", d => color(d.value))
    .attr("stroke", "#d0d0d0")
    .attr("stroke-width", 0.3);
  
  makeTooltip(rects, d => `${d.term} → ${d.gene}`);
  
  // -----------------------------
  // axes
  // -----------------------------
  g.append("g")
    .attr("transform", `translate(0,${innerH + EXTRA_AXIS_SPACE})`)
    .call(d3.axisBottom(x).tickSize(0))
    .selectAll("text")
    .attr("transform", "rotate(-90)")
    .attr("dy", "0em")
    .attr("dx", "-0.2em")
    .style("text-anchor", "end")
    .style("font-size", "6px");
  
  g.append("g")
    .call(d3.axisLeft(y).tickSize(0))
    .selectAll("text")
    .style("font-size", "7px");
  
  observeResize(svgEl);
  
  
  // -----------------------------
  // VIRIDIS LEGEND
  // -----------------------------
  const legendWidth = 140;
  const legendHeight = 10;
  
  const legendX = margin.left;
  const legendY = 20;
  
  const legendScale = d3.scaleLinear()
    .domain([1, maxVal])
    .range([0, legendWidth]);
  
  const legendAxis = d3.axisBottom(legendScale)
    .ticks(4)
    .tickSize(3);
  
  // gradient
  const defs = svg.append("defs");
  
  const gradient = defs.append("linearGradient")
    .attr("id", "viridis-gradient")
    .attr("x1", "0%")
    .attr("x2", "100%");
  
  d3.range(0, 1.01, 0.1).forEach(t => {
    gradient.append("stop")
      .attr("offset", `${t * 100}%`)
      .attr("stop-color", d3.interpolateViridis(t));
  });
  
  // bar
  svg.append("rect")
    .attr("x", legendX)
    .attr("y", legendY)
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .style("fill", "url(#viridis-gradient)");
  
  // axis
  svg.append("g")
    .attr("transform", `translate(${legendX}, ${legendY + legendHeight})`)
    .call(legendAxis)
    .selectAll("text")
    .style("font-size", "8px");
  
  // label
  svg.append("text")
    .attr("x", legendX)
    .attr("y", legendY - 5)
    .style("font-size", "9px")
    .text("Term size");
    
}

// ---------------------------------------------------------------------------
// TRUE slope chart: starting proteins -> proteins in network
// ---------------------------------------------------------------------------
export function renderD3SlopeChart(rows, svgEl, options = {}) {
  const data = preprocessEnrichmentData(rows, getTopN(options, 20));
  if (!svgEl || !data.length) return;
const maxLabelLength = d3.max(data, d => (d.desc || "").length) || 10;

const margin = {
  top: 20,
  right: 40,
  bottom: 55,
  left: Math.max(140, Math.min(420, maxLabelLength * 6))
};
  const innerW = 760;
  const innerH = Math.max(260, data.length * 26);
const width  = svgEl.parentElement.clientWidth || (innerW + margin.left + margin.right)
const height = innerH + margin.top + margin.bottom

  const { svg } = normalizeBeforePlot(svgEl, {
    defaultSize: width,
    aspect: height / width,
    minHeight: height
  });

  clearSvg(svgEl);
  svg
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`);

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append("g").attr("class", "zoom-root");
  
  const g = root.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  
  enablePanZoom(svg, root);

  const xMax = d3.max(data, d => Math.max(d.total, d.inNetwork)) || 1;

  const x = d3.scaleLinear()
    .domain([0, xMax])
    .nice()
    .range([0, innerW]);

  const y = d3.scaleBand()
    .domain(data.map(d => d.desc))
    .range([0, innerH])
    .padding(0.35);

  const color = d3.scaleSequential(d3.interpolateBlues)
    .domain([0, d3.max(data, d => d.logp) || 1]);

  g.append("g").call(d3.axisLeft(y).tickFormat(d => trunc(d, 52)));

  g.append("g")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x));

  g.selectAll(".lolli-line")
    .data(data)
    .join("line")
    .attr("class", "lolli-line")
    .attr("x1", d => x(d.total))
    .attr("x2", d => x(d.inNetwork))
    .attr("y1", d => y(d.desc) + y.bandwidth() / 2)
    .attr("y2", d => y(d.desc) + y.bandwidth() / 2)
    .attr("stroke", "#bdbdbd")
    .attr("stroke-width", 2);

  g.selectAll(".start-dot")
    .data(data)
    .join("circle")
    .attr("class", "start-dot")
    .attr("cx", d => x(d.total))
    .attr("cy", d => y(d.desc) + y.bandwidth() / 2)
    .attr("r", 4)
    .attr("fill", "#777");


  const endDots = g.selectAll(".end-dot")
    .data(data)
    .join("circle")
    .attr("class", "end-dot")
    .attr("cx", d => x(d.inNetwork))
    .attr("cy", d => y(d.desc) + y.bandwidth() / 2)
    .attr("r", 6)
    .attr("fill", d => color(d.logp))
    .attr("stroke", "#222")
    .attr("stroke-width", 0.5);

  makeTooltip(endDots, d =>
    `${d.desc}\nStarting=${d.total}\nIn network=${d.inNetwork}\n-log10(p)=${d.logp.toFixed(2)}`
  );

  svg.append("text")
    .attr("x", margin.left + innerW / 2)
    .attr("y", height - 8)
    .attr("text-anchor", "middle")
    .style("font-size", "13px")
    .text("Protein count");

  observeResize(svgEl);
}

// ---------------------------------------------------------------------------
// SANKEY
// ---------------------------------------------------------------------------
export async function renderD3Sankey(rows, svgEl, options = {}) {
  if (!svgEl) return;
  ensureVisibleContainer(svgEl);

  const svg = clearSvg(svgEl);

  const container = svgEl.parentElement;
  if (container) {
    try {
      await waitForNonZeroWidth(container, 3000);
    } catch (_) {}
  }

  let data = preprocessEnrichmentData(rows, getTopN(options, 20));
  if (!data.length) return;
  data = data.sort((a, b) => a.pval - b.pval);

const baseWidth = container?.clientWidth || 1000
const margin = { top: 40, right: 260, bottom: 40, left: 260 };

  const nodes = [];
  const links = [];
  const nodeByName = new Map();

  data.forEach((t, i) => {
    const node = {
      id: `t_${i}`,
      name: t.desc,
      type: 'term',
      idx: i,
      count: t.genes.length,
    };
    nodes.push(node);
    nodeByName.set(t.desc, node);
  });

  const geneMap = new Map();
  data.forEach((t) => {
    const termNode = nodeByName.get(t.desc);
    t.genes.forEach((gene) => {
      let geneNode = geneMap.get(gene);
      if (!geneNode) {
        geneNode = { id: `g_${gene}`, name: gene, type: 'gene', count: 0 };
        geneMap.set(gene, geneNode);
        nodes.push(geneNode);
      }
      geneNode.count += 1;
      links.push({ source: termNode.id, target: geneNode.id, value: 1, termIdx: termNode.idx });
    });
  });

  const sortedTerms = nodes.filter(n => n.type === 'term');
  const sortedGenes = nodes.filter(n => n.type === 'gene').sort((a, b) => b.count - a.count);
  const colorTerm = d3.scaleSequential(d3.interpolateRainbow).domain([0, sortedTerms.length - 1]);

  const fixedGeneHeight = 12;
  const termScale = d3.scaleLinear()
    .domain([1, d3.max(sortedTerms, t => t.count) || 1])
    .range([fixedGeneHeight, 80]);

  let yTerm = margin.top;
  sortedTerms.forEach((t) => {
    const h = termScale(t.count);
    t.x0 = margin.left;
    t.x1 = t.x0 + 25;
    t.y0 = yTerm;
    t.y1 = yTerm + h;
    yTerm += h + 10;
  });

  let yGene = margin.top;
  sortedGenes.forEach((g) => {
    g.x0 = baseWidth - margin.right - 25;
    g.x1 = g.x0 + 25;
    g.y0 = yGene;
    g.y1 = yGene + fixedGeneHeight;
    yGene += fixedGeneHeight;
  });

  const totalHeight = Math.max(yTerm, yGene) + margin.bottom;
  svg
    .attr('width', baseWidth)
    .attr('height', totalHeight)
    .attr('viewBox', `0 0 ${baseWidth} ${totalHeight}`)
    .style('overflow', 'visible');

  setPlotContainerHeight(svgEl, totalHeight + 20);

const root = svg.append("g").attr("class","zoom-root")
const gInner = root.append('g').attr('class','sankey-inner')

enableZoom(svg, root)

  const linkPath = (d) => {
    const src = nodes.find(n => n.id === d.source);
    const tgt = nodes.find(n => n.id === d.target);
    const x0 = src.x1;
    const x1 = tgt.x0;
    const y0 = (src.y0 + src.y1) / 2;
    const y1 = (tgt.y0 + tgt.y1) / 2;
    const xi = d3.interpolateNumber(x0, x1);
    return `M${x0},${y0}C${xi(0.4)},${y0} ${xi(0.6)},${y1} ${x1},${y1}`;
  };

  const linkSel = gInner.append('g')
    .attr('fill', 'none')
    .selectAll('path')
    .data(links)
    .join('path')
    .attr('d', linkPath)
    .attr('stroke', d => colorTerm(d.termIdx))
    .attr('stroke-width', 2.2)
    .attr('stroke-opacity', 0.4);

  const node = gInner.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('transform', d => `translate(${d.x0},${d.y0})`);

  node.append('rect')
    .attr('height', d => d.type === 'gene' ? fixedGeneHeight : d.y1 - d.y0)
    .attr('width', d => d.x1 - d.x0)
    .attr('fill', d => d.type === 'term' ? colorTerm(d.idx) : '#bdbdbd')
    .attr('stroke', '#222');

  node.append('text')
    .attr('x', d => d.type === 'term' ? -6 : (d.x1 - d.x0) + 4)
    .attr('y', d => d.type === 'gene' ? fixedGeneHeight / 2 : (d.y1 - d.y0) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.type === 'term' ? 'end' : 'start')
    .attr('font-size', 12)
    .text(d => trunc(d.name, 34));

node.on('mouseover', (ev, d) => {
  if (d.type === 'term') {
    const termColor = colorTerm(d.idx);

    linkSel
      .attr('stroke', l => l.source === d.id ? termColor : '#ddd')
      .style('opacity', l => l.source === d.id ? 0.9 : 0.05);

    node.selectAll('rect')
      .attr('fill', n => {
        if (n.type === 'gene') {
          const connected = links.some(l => l.source === d.id && l.target === n.id);
          return connected ? termColor : '#bdbdbd';
        }
        return n.type === 'term'
          ? (n.id === d.id ? termColor : '#d9d9d9')
          : '#bdbdbd';
      });

  } else {
    const connectedLinks = links.filter(l => l.target === d.id);
    const connectedTermIds = new Set(connectedLinks.map(l => l.source));

    linkSel
      .attr('stroke', l => l.target === d.id ? colorTerm(l.termIdx) : '#ddd')
      .style('opacity', l => l.target === d.id ? 0.9 : 0.05);

    node.selectAll('rect')
      .attr('fill', n => {
        if (n.type === 'term' && connectedTermIds.has(n.id)) {
          const idx = nodes.find(x => x.id === n.id)?.idx ?? 0;
          return colorTerm(idx);
        }
        if (n.type === 'gene') {
          return n.id === d.id ? '#999' : '#bdbdbd';
        }
        return '#d9d9d9';
      });
  }
}).on('mouseout', () => {
  linkSel
    .attr('stroke', d => colorTerm(d.termIdx))
    .style('opacity', 0.4);

  node.selectAll('rect')
    .attr('fill', n => n.type === 'term'
      ? colorTerm(n.idx)
      : '#bdbdbd');
});

  observeResize(svgEl);
}

// ---------------------------------------------------------------------------
// CIRCLE / CIRCOS style plot with labels + hover
// ---------------------------------------------------------------------------
export function renderD3CirclePlot(rows, svgEl, options = {}) {
  if (!svgEl) return;
  ensureVisibleContainer(svgEl, 800);

  const data = preprocessEnrichmentData(rows, getTopN(options, 15));
  const termNames = data.map(d => d.desc || d.term);
  const geneSet = new Set();
  data.forEach(d => d.genes.forEach(g => geneSet.add(g)));
  const genes = Array.from(geneSet);
  const all = termNames.concat(genes);
  const n = all.length;
  if (!n) return;

const width  = svgEl.parentElement.clientWidth || 820
const height = width
  const innerR = Math.min(width, height) * 0.33;
  const outerR = innerR * 1.12;

  const mat = Array.from({ length: n }, () => Array(n).fill(0));
  data.forEach((t, i) => {
    t.genes.forEach(g => {
      const j = termNames.length + genes.indexOf(g);
      if (j >= termNames.length) {
        mat[i][j] = 1;
        mat[j][i] = 1;
      }
    });
  });

  const svg = clearSvg(svgEl);
  svg
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `${-width / 2} ${-height / 2} ${width} ${height}`)
    .style('overflow', 'visible');

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append('g').attr('class', 'zoom-root');
  const g = root.append('g');

  const zoom = d3.zoom()
    .scaleExtent([0.6, 6])
    .on('zoom', ev => root.attr('transform', ev.transform));
  svg.call(zoom);

  const rainbow = d3.scaleSequential(d3.interpolateRainbow).domain([0, Math.max(termNames.length - 1, 1)]);
  const geneColor = '#bdbdbd';

  const chord = d3.chord().padAngle(0.02).sortSubgroups(d3.descending)(mat);
  const arc = d3.arc().innerRadius(innerR).outerRadius(outerR);
  const ribbon = d3.ribbon().radius(innerR - 1);

  const groupsG = g.append('g');
  const ribsG = g.append('g');

  const groups = groupsG.selectAll('g.group')
    .data(chord.groups)
    .join('g')
    .attr('class', 'group');

  groups.append('path')
    .attr('d', arc)
    .attr('fill', d => d.index < termNames.length ? rainbow(d.index) : geneColor)
    .attr('stroke', d => d3.rgb(d.index < termNames.length ? rainbow(d.index) : geneColor).darker());

  groups.append('title').text(d => {
    const nm = all[d.index];
    if (d.index < termNames.length) {
      const t = data[d.index];
      return `${t.desc}\nP=${t.pval.toExponential(2)}\nGenes=${t.size}`;
    }
    return `Gene: ${nm}`;
  });

  groups.append('text')
    .attr('dy', '0.35em')
    .attr('transform', d => {
      d.angle = (d.startAngle + d.endAngle) / 2;
      const angle = d.angle * 180 / Math.PI - 90;
      const rotate = d.angle > Math.PI ? 'rotate(180)' : '';
      return `rotate(${angle}) translate(${outerR + 6}) ${rotate}`;
    })
    .attr('text-anchor', d => d.angle > Math.PI ? 'end' : 'start')
    .style('font-size', d => d.index < termNames.length ? '9px' : '8px')
    .style('fill', d => d.index < termNames.length ? '#222' : '#666')
    .text(d => all[d.index]);

  const ribs = ribsG.selectAll('path')
    .data(chord)
    .join('path')
    .attr('d', ribbon)
    .attr('fill', d => d.source.index < termNames.length ? rainbow(d.source.index) : geneColor)
    .attr('stroke', d => d3.rgb(d.source.index < termNames.length ? rainbow(d.source.index) : geneColor).darker())
    .attr('opacity', 0.85);

  ribs.append('title').text(d => `${all[d.source.index]} ↔ ${all[d.target.index]}`);

  groups.on('mouseover', (ev, d) => {
    const idx = d.index;
    if (idx < termNames.length) {
      const termColor = rainbow(idx);
      ribs.transition()
        .style('opacity', r => r.source.index === idx || r.target.index === idx ? 1 : 0.08)
        .attr('fill', r => (r.source.index === idx || r.target.index === idx)
          ? termColor
          : (r.source.index < termNames.length ? rainbow(r.source.index) : geneColor));

      groups.selectAll('path').transition()
        .style('opacity', g2 => g2.index === idx || (g2.index >= termNames.length && mat[idx][g2.index] === 1) ? 1 : 0.25)
        .attr('fill', g2 => {
          if (g2.index === idx) return termColor;
          if (g2.index >= termNames.length && mat[idx][g2.index] === 1) return termColor;
          return g2.index < termNames.length ? rainbow(g2.index) : geneColor;
        });
    } else {
  const connectedTermIdx = [];

  for (let i = 0; i < termNames.length; i++) {
    if (mat[i][idx] === 1) connectedTermIdx.push(i);
  }

  ribs.transition()
    .style("opacity", r => r.source.index === idx || r.target.index === idx ? 1 : 0.08);

  groups.selectAll("path").transition()
    .style("opacity", g =>
      g.index === idx || connectedTermIdx.includes(g.index) ? 1 : 0.25
    );
}
  });

  groups.on('mouseout', () => {
    ribs.transition()
      .style('opacity', 0.85)
      .attr('fill', d => d.source.index < termNames.length ? rainbow(d.source.index) : geneColor);

    groups.selectAll('path').transition()
      .style('opacity', 1)
      .attr('fill', d => d.index < termNames.length ? rainbow(d.index) : geneColor);
  });

  observeResize(svgEl);
}

// ---------------------------------------------------------------------------
// MODULE HEATMAP from enrichment_heatmap.json grouped by DB
// accepted data shape:
// {
//   C: { term1: ["Module 1", "Module 2"], ... },
//   P: { ... }
// }
// options: { dbKey, topN }
// ---------------------------------------------------------------------------
export function renderD3ModuleHeatmap(heatmapData, svgEl, options = {}) {
  if (!svgEl || !heatmapData) return;
  ensureVisibleContainer(svgEl, 800);

  const dbKey = options.dbKey || options.category || "C";
  const topN = getTopN(options, 20);

  // 🔥 SUPPORT BOTH FORMATS
  let raw = {};

  // NEW FORMAT
  if (heatmapData?.databases?.[dbKey]?.terms) {
    heatmapData.databases[dbKey].terms.forEach(d => {
      raw[d.description] = d.modules || [];
    });
  }

  // OLD FORMAT (fallback)
  else if (heatmapData?.[dbKey]) {
    raw = heatmapData[dbKey];
  }

  const entries = Object.entries(raw);
  if (!entries.length) {
    console.warn("No entries for db:", dbKey);
    clearSvg(svgEl);
    return;
  }

  // -----------------------------
  // Terms
  // -----------------------------
  let terms = entries
    .sort(([, a], [, b]) => (b?.length || 0) - (a?.length || 0))
    .slice(0, topN === "all" ? 9999 : topN)
    .map(([term]) => term);

  // -----------------------------
  // Modules
  // -----------------------------
  const allModules = Object.values(raw).flat();

  let modules = Array.from(new Set(allModules)).sort((a, b) => {
    const na = parseInt(String(a).replace(/\D+/g, ""), 10) || 0;
    const nb = parseInt(String(b).replace(/\D+/g, ""), 10) || 0;
    return na - nb;
  });

  const MAX_TERMS = 1000;
  const MAX_MODULES = 80;

  if (terms.length > MAX_TERMS) terms = terms.slice(0, MAX_TERMS);
  if (modules.length > MAX_MODULES) modules = modules.slice(0, MAX_MODULES);

  if (!terms.length || !modules.length) {
    clearSvg(svgEl);
    return;
  }

  const moduleSet = new Set(modules);

  // -----------------------------
  // Sparse matrix + VALUE
  // -----------------------------
  const cellData = [];

  terms.forEach(t => {
    const mods = raw[t] || [];
    const value = mods.length   // 👈 module_count equivalent

    mods.forEach(m => {
      if (moduleSet.has(m)) {
        cellData.push({
          term: t,
          module: m,
          value
        });
      }
    });
  });

  if (!cellData.length) {
    console.warn("No cellData generated");
    clearSvg(svgEl);
    return;
  }

  // -----------------------------
  // Layout
  // -----------------------------
  const cellSize = Math.max(18, Math.min(28, 900 / Math.max(modules.length, 1)));

  const longestTerm = d3.max(terms, d => String(d).length) || 0;
  const longestModule = d3.max(modules, d => String(d).length) || 0;
  const margin = {
    top: 24,
    right: 48,
    bottom: Math.max(120, Math.min(260, 42 + longestModule * 6)),
    left: Math.max(260, Math.min(620, 28 + longestTerm * 6.5))
  };

  let innerW = modules.length * cellSize;
  const innerH = terms.length * cellSize;

  const MAX_WIDTH = 1400;
  const scale = Math.min(1, MAX_WIDTH / innerW);
  innerW *= scale;

  const width = Math.max(
    svgEl.parentElement.clientWidth || 900,
    innerW + margin.left + margin.right
  );

  const height = innerH + margin.top + margin.bottom;
  const viewportWidth = svgEl.parentElement?.clientWidth || 900;

  const { svg } = normalizeBeforePlot(svgEl, {
    defaultSize: width,
    aspect: height / width,
    minHeight: height
  });

  clearSvg(svgEl);

  svg
    .attr("width", viewportWidth)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .style("overflow", "hidden")
    .style("cursor", "grab")
    .style("touch-action", "none");

  setPlotContainerHeight(svgEl, height + 20);

  const root = svg.append("g")
    .attr("class", "zoom-root");

  const g = root.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  enableZoom(svg, root);

  const x = d3.scaleBand()
    .domain(modules)
    .range([0, innerW])
    .padding(0.05);

  const y = d3.scaleBand()
    .domain(terms)
    .range([0, innerH])
    .padding(0.05);

  // -----------------------------
  // VIRIDIS COLOR
  // -----------------------------
  const values = cellData.map(d => d.value);
  const minVal = d3.min(values) || 0;
  const maxVal = d3.max(values) || 1;

  const color = d3.scaleSequential(d3.interpolateViridis)
    .domain(minVal === maxVal ? [minVal, minVal + 1] : [minVal, maxVal]);

  // -----------------------------
  // Draw cells
  // -----------------------------
  const rects = g.selectAll("rect")
    .data(cellData)
    .join("rect")
    .attr("x", d => x(d.module))
    .attr("y", d => y(d.term))
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("fill", d => color(d.value))
    .attr("stroke", "#d0d0d0")
    .attr("stroke-width", 0.5);

  makeTooltip(rects, d => `${d.term} → ${d.module} (${d.value})`);

  // -----------------------------
  // Axes
  // -----------------------------
  g.append("g")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .selectAll("text")
    .attr("transform", "rotate(-55)")
    .style("text-anchor", "end")
    .style("font-size", "11px");

  g.append("g")
    .call(d3.axisLeft(y).tickSize(0))
    .selectAll("text")
    .style("font-size", "10px")
    .each(function() {
      const text = d3.select(this);
      text.text(trunc(text.text(), 90));
    });

  observeResize(svgEl);
}




// ---------------------------------------------------------------------------
// MODULE SIMILARITY CLUSTERMAP
// modules x modules similarity
// with dendrogram + experiment strip
// ---------------------------------------------------------------------------
export function renderD3ModuleSimilarityHeatmap(data, svgEl){

  if(!svgEl || !data) return

  const labels = data.labels || []
  const matrix = data.matrix || []
  if(!labels.length) return

  // ------------------------------------------------
  // parse experiment + module
  // ------------------------------------------------

  function parse(l){
    const m = String(l).match(/(.+?)_Module\s*(\d+)/)
    return m
      ? {full:l,exp:m[1],mod:`M${m[2]}`}
      : {full:l,exp:"unknown",mod:l}
  }

  const meta = labels.map(parse)
  const experiments = [...new Set(meta.map(d=>d.exp))]

  const expColor = d3.scaleOrdinal()
    .domain(experiments)
    .range(d3.schemeTableau10)

  // ------------------------------------------------
  // hierarchical clustering (average linkage)
  // ------------------------------------------------

  function cluster(mat){

    let clusters = labels.map((_,i)=>[i])
    const merges=[]

    const dist=(a,b)=>{
      let s=0,c=0
      a.forEach(i=>b.forEach(j=>{
        s += 1-mat[i][j]
        c++
      }))
      return s/c
    }

    while(clusters.length>1){

      let best=[0,1]
      let bestD=Infinity

      for(let i=0;i<clusters.length;i++){
        for(let j=i+1;j<clusters.length;j++){

          const d = dist(clusters[i],clusters[j])
          if(d<bestD){
            bestD=d
            best=[i,j]
          }
        }
      }

      const merged=[...clusters[best[0]],...clusters[best[1]]]

      merges.push({
        left:clusters[best[0]],
        right:clusters[best[1]],
        height:bestD
      })

      clusters.splice(best[1],1)
      clusters.splice(best[0],1)
      clusters.push(merged)

    }

    return {order:clusters[0], merges}

  }

  const clustering = cluster(matrix)
  const order = clustering.order
  const merges = clustering.merges

  const labelsO = order.map(i=>labels[i])
  const metaO   = order.map(i=>meta[i])
  const matO    = order.map(i=>order.map(j=>matrix[i][j]))

  // ------------------------------------------------
  // layout
  // ------------------------------------------------

const containerWidth = svgEl.parentElement.clientWidth || 1050

const usableWidth = containerWidth - 250   // margins + legend

const cell = Math.max(
  16,
  Math.min(
    42,
    Math.floor(usableWidth / labels.length)
  )
)
const dendroH = Math.max(90, cell * 4)
  const margin={
    top:dendroH+150,
    left:120,
    right:140,
    bottom:160
  }

  const inner = labels.length*cell

  const width = Math.max(
    svgEl.parentElement.clientWidth || 900,
    inner + margin.left + margin.right
  )

  const height = inner + margin.top + margin.bottom

  const svg = d3.select(svgEl)
  svg.selectAll("*").remove()

  svg
   .attr("width",width)
   .attr("height",height)
   .attr("viewBox",`0 0 ${width} ${height}`)

  const g = svg.append("g")
    .attr("transform",`translate(${margin.left},${margin.top})`)

  const x = d3.scaleBand().domain(labelsO).range([0,inner])
  const y = d3.scaleBand().domain(labelsO).range([0,inner])

  const color = d3.scaleSequential(d3.interpolateViridis)
    .domain([0,1])

  // ------------------------------------------------
  // heatmap cells
  // ------------------------------------------------

  const cells=[]

  labelsO.forEach((a,i)=>{
    labelsO.forEach((b,j)=>{
      cells.push({x:a,y:b,v:matO[i][j]})
    })
  })

  g.selectAll("rect.cell")
   .data(cells)
   .enter()
   .append("rect")
   .attr("x",d=>x(d.x))
   .attr("y",d=>y(d.y))
   .attr("width",cell)
   .attr("height",cell)
   .attr("fill",d=>color(d.v))

  // numbers inside cells

g.selectAll("text.cell")
  .data(cells)
  .enter()
  .append("text")
  .attr("x", d => x(d.x) + cell / 2)
  .attr("y", d => y(d.y) + cell / 2)
  .attr("text-anchor", "middle")
  .attr("dominant-baseline", "middle")
  .attr("font-size", Math.max(6, cell * 0.4))   // adaptive size
  .attr("font-weight", "600")
  .attr("fill", d => d.v > 0.55 ? "#111" : "#fff")
  .text(d => cell < 18 ? "" : d.v.toFixed(2))
  // ------------------------------------------------
  // experiment color strips
  // ------------------------------------------------

  g.selectAll(".row-exp")
   .data(metaO)
   .enter()
   .append("rect")
   .attr("x",-18)
   .attr("y",d=>y(d.full))
   .attr("width",10)
   .attr("height",cell)
   .attr("fill",d=>expColor(d.exp))


  // ------------------------------------------------
  // axes
  // ------------------------------------------------

  g.append("g")
   .attr("transform",`translate(0,${inner})`)
   .call(d3.axisBottom(x).tickSize(0))
   .selectAll("text")
   .attr("transform","rotate(-60)")
   .style("text-anchor","end")
   .style("font-size","11px")
   .text(d=>parse(d).mod)

  g.append("g")
   .call(d3.axisLeft(y).tickSize(0))
   .selectAll("text")
   .attr("dx","-20")
   .style("font-size","8px")
   .text(d=>parse(d).mod)

  // ------------------------------------------------
  // dendrogram (top)
  // ------------------------------------------------

  const dendro = svg.append("g")
    .attr("transform",`translate(${margin.left},${margin.top-dendroH})`)

  const scale = d3.scaleLinear()
    .domain([0,d3.max(merges,d=>d.height)])
    .range([dendroH,0])

  const nodePos = new Map()

  order.forEach((idx,i)=>{
    nodePos.set(idx,{
      x:x(labels[idx])+cell/2,
      y:dendroH
    })
  })

  merges.forEach(m=>{

    const lx=d3.mean(m.left.map(i=>nodePos.get(i).x))
    const rx=d3.mean(m.right.map(i=>nodePos.get(i).x))

    const y1=nodePos.get(m.left[0]).y
    const y2=nodePos.get(m.right[0]).y

    const y=scale(m.height)

    dendro.append("line")
      .attr("x1",lx).attr("x2",lx)
      .attr("y1",y1).attr("y2",y)
      .attr("stroke","#333")

    dendro.append("line")
      .attr("x1",rx).attr("x2",rx)
      .attr("y1",y2).attr("y2",y)
      .attr("stroke","#333")

    dendro.append("line")
      .attr("x1",lx).attr("x2",rx)
      .attr("y1",y).attr("y2",y)
      .attr("stroke","#333")

    const merged=[...m.left,...m.right]

    merged.forEach(i=>{
      nodePos.set(i,{x:(lx+rx)/2,y:y})
    })

  })
  // ------------------------------------------------
  // LEGEND (CLEAN VERSION - ONLY ONCE)
  // ------------------------------------------------
  
  // layout config
  const legendCols = experiments.length > 9 ? 4 : 3;
  const itemHeight = 18;
  
  // dynamic width based on text length
  const maxLen = d3.max(experiments, d => d.length) || 10;
  const itemWidth = Math.max(120, Math.min(260, maxLen * 7));
  
  const legendRows = Math.ceil(experiments.length / legendCols);
  
  // 🔥 IMPORTANT: extend EXISTING margin (do NOT redeclare it)
  margin.top += legendRows * itemHeight + 10;
  
  // draw legend
  const legend = svg.append("g")
    .attr("transform", `translate(${margin.left}, 10)`);
  
  experiments.forEach((exp, i) => {
  
    const col = i % legendCols;
    const row = Math.floor(i / legendCols);
  
    const x = col * itemWidth;
    const y = row * itemHeight;
  
    legend.append("rect")
      .attr("x", x)
      .attr("y", y)
      .attr("width", 12)
      .attr("height", 12)
      .attr("fill", expColor(exp));
  
    legend.append("text")
      .attr("x", x + 18)
      .attr("y", y + 10)
      .style("font-size", "12px")
      .text(exp);
  });



}
