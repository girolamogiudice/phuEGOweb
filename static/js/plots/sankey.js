/* SANKEY DIAGRAM */
import { initSVG, addZoom } from '../utils_plot.js';
function renderD3Sankey(rows, svg, opts = {}) {
  const width = svg.parentElement.clientWidth || 900;
  const data = preprocessEnrichmentData(rows, opts.topN || 20);
  
  // Calculate dynamic height based on number of nodes
  const geneSet = new Set();
  data.forEach(d => d.genes.forEach(g => geneSet.add(g)));
  const totalNodes = data.length + geneSet.size;
  const minHeight = 600;
  const heightPerNode = 25;
  const height = Math.max(minHeight, totalNodes * heightPerNode);

  svg.innerHTML = '';
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.removeAttribute('viewBox'); // Remove any viewBox

  const svgSel = d3.select(svg);

  const nodes = [];
  const links = [];

  const colorScale = d3.scaleSequential(d3.interpolateRainbow)
    .domain([0, data.length]);

  const termMap = new Map();
  const geneMap = new Map();

  // Build nodes and links
  data.forEach((term, i) => {
    const termNode = {
      id: `term_${i}`,
      name: term.desc || term.term,
      type: 'term',
      color: colorScale(i),
      count: term.genes.length
    };
    nodes.push(termNode);
    termMap.set(term.desc || term.term, termNode);

    term.genes.forEach(gene => {
      let geneNode;
      if (!geneMap.has(gene)) {
        geneNode = { id: `gene_${gene}`, name: gene, type: 'gene', count: 0 };
        nodes.push(geneNode);
        geneMap.set(gene, geneNode);
      } else {
        geneNode = geneMap.get(gene);
      }

      geneNode.count += 1;

      links.push({
        source: geneNode.id,
        target: termNode.id,
        value: 1
      });
    });
  });

  const linkValueScale = d3.scaleLinear()
    .domain(d3.extent(links, d => d.value))
    .range([1, 5]);

  links.forEach(l => { l.value = linkValueScale(l.value); });

  const sankey = d3.sankey()
    .nodeId(d => d.id)
    .nodeWidth(20)
    .nodePadding(Math.max(8, Math.min(20, height / totalNodes - 5)))
    .extent([ [1, 1], [width - 1, height - 6] ])
    .nodeSort(null);

  const graph = sankey({
    nodes: nodes.map(d => Object.assign({}, d)),
    links: links.map(d => Object.assign({}, d))
  });

  const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on("zoom", event => g.attr("transform", event.transform));

  svgSel.call(zoom);
  const g = svgSel.append("g");

  const link = g.append("g")
    .attr("fill", "none")
    .attr("stroke-opacity", 0.25)
    .selectAll("path")
    .data(graph.links)
    .join("path")
    .attr("d", d3.sankeyLinkHorizontal())
    .attr("stroke", d => termMap.get(d.target.name)?.color || "#ccc")
    .attr("stroke-width", d => Math.max(1, d.width))
    .append("title")
    .text(d => `${d.source.name} → ${d.target.name}`);

  const node = g.append("g")
    .selectAll("g")
    .data(graph.nodes)
    .join("g")
    .attr("transform", d => `translate(${d.x0},${d.y0})`);

  node.append("rect")
    .attr("height", d => Math.max(3, d.y1 - d.y0))
    .attr("width", d => d.x1 - d.x0)
    .attr("fill", d => d.type === 'term' ? d.color : '#999')
    .attr("stroke", "#000");

  node.append("title")
    .text(d => `${d.name}\nConnections: ${d.count}`);

  node.append("text")
    .attr("x", d => d.x0 < width / 2 ? 6 + (d.x1 - d.x0) : -6)
    .attr("y", d => (d.y1 - d.y0) / 2)
    .attr("dy", "0.35em")
    .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
    .attr("font-size", "10px")
    .text(d => d.name);

  node.on("mouseover", (event, d) => {
    if (d.type === 'term') {
      const termColor = d.color;

      g.selectAll("path").transition().duration(200)
        .style("opacity", l => (l.target.id === d.id ? 1 : 0.05))
        .attr("stroke", l => (l.target.id === d.id ? termColor : "#ccc"));

      g.selectAll("rect").transition().duration(200)
        .attr("fill", n => {
          const connected = graph.links.some(l => l.source.id === n.id && l.target.id === d.id);
          return connected ? termColor : (n.type === 'term' ? n.color : '#999');
        })
        .style("opacity", n => {
          const connected = graph.links.some(l => l.source.id === n.id && l.target.id === d.id);
          return connected ? 1 : 0.2;
        });
    } else if (d.type === 'gene') {
      g.selectAll("path").transition().duration(200)
        .style("opacity", l => (l.source.id === d.id ? 1 : 0.05));

      g.selectAll("rect").transition().duration(200)
        .style("opacity", n => {
          const connected = graph.links.some(l => l.source.id === d.id && l.target.id === n.id);
          return connected || n.id === d.id ? 1 : 0.2;
        });
    }
  });

  node.on("mouseout", () => {
    g.selectAll("path").transition().duration(200)
      .style("opacity", 0.7)
      .attr("stroke", l => termMap.get(l.target.name)?.color || "#ccc");

    g.selectAll("rect").transition().duration(200)
      .attr("fill", n => n.type === 'term' ? n.color : '#999')
      .style("opacity", 1);
  });

  const resetBtn = svgSel.append("g")
    .attr("transform", `translate(${width - 100},${30})`)
    .attr("cursor", "pointer")
    .on("click", () => svgSel.transition().duration(500).call(zoom.transform, d3.zoomIdentity));

  resetBtn.append("rect")
    .attr("width", 80)
    .attr("height", 24)
    .attr("fill", "#f0f0f0")
    .attr("stroke", "#999")
    .attr("rx", 4)
    .attr("ry", 4);

  resetBtn.append("text")
    .attr("x", 40)
    .attr("y", 16)
    .attr("text-anchor", "middle")
    .attr("font-size", 10)
    .text("Reset Zoom");
}
