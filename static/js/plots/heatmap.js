
/* ROTATED HEATMAP (Genes on Y, Terms on X, X labels at bottom rotated 90°) */
function renderD3Heatmap(rows, svg, opts = {}) {
  clearSVG(svg); // clear old chart

  const container = svg.parentElement;
  const width = container.clientWidth || 1000;
  const data = preprocessEnrichmentData(rows, opts.topN || 20);

  // margins
  const margin = { top: 50, right: 200, bottom: 250, left: 200 };

  // collect all genes
  const allGenes = new Set();
  data.forEach(d => d.genes.forEach(g => allGenes.add(g)));
  const geneList = Array.from(allGenes).sort();

  const nTerms = data.length;
  const nGenes = geneList.length;

  const cellWidth = 25;
  const cellHeight = 15;

  const innerWidth = Math.max(400, nTerms * cellWidth);
  const innerHeight = Math.max(400, nGenes * cellHeight);

  const totalWidth = innerWidth + margin.left + margin.right;
  const totalHeight = innerHeight + margin.top + margin.bottom;

  svg.innerHTML = '';
  svg.setAttribute('width', totalWidth);
  svg.setAttribute('height', totalHeight);

  const svgSelection = d3.select(svg);
  const g = svgSelection.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  // zoom & pan
  const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on('zoom', (event) => {
      g.attr('transform', `translate(${margin.left + event.transform.x},${margin.top + event.transform.y}) scale(${event.transform.k})`);
    });

  svgSelection.call(zoom);

  // scales
  const x = d3.scaleBand()
    .domain(data.map(d => d.desc || d.term))
    .range([0, innerWidth])
    .padding(0.05);

  const y = d3.scaleBand()
    .domain(geneList)
    .range([0, innerHeight])
    .padding(0.05);

  const color = d3.scaleSequential(d3.interpolateBlues)
    .domain([0, 1]);

  // draw cells
  data.forEach(termData => {
    geneList.forEach(gene => {
      if (termData.genes.includes(gene)) {
        g.append('rect')
          .attr('x', x(termData.desc || termData.term))
          .attr('y', y(gene))
          .attr('width', x.bandwidth())
          .attr('height', y.bandwidth())
          .attr('fill', color(0.8))
          .attr('stroke', '#e6e6e6')
          .attr('stroke-width', 0.5)
          .append('title')
          .text(`${termData.desc || termData.term}\nGene: ${gene}\nP=${termData.pval.toExponential(2)}`);
      }
    });
  });

  // y-axis (genes)
  const yAxis = g.append('g')
    .call(d3.axisLeft(y).tickSize(0).tickPadding(4));

  yAxis.selectAll('text')
    .style('font-size', '9px');

  // x-axis (terms, at bottom)
  const xAxis = g.append('g')
    .attr('transform', `translate(0, ${innerHeight})`)
    .call(d3.axisBottom(x).tickSize(0).tickPadding(6));

  xAxis.selectAll('text')
    .attr('transform', 'rotate(90)')
    .attr('x', 10)
    .attr('y', -5)
    .style('text-anchor', 'start')
    .style('font-size', '9px');

  // legend
  const legend = g.append('g')
    .attr('transform', `translate(${innerWidth + 30}, 0)`);

  legend.append('text')
    .attr('x', 0)
    .attr('y', -10)
    .style('font-size', '12px')
    .style('font-weight', 'bold')
    .text('Gene Present');

  legend.append('rect')
    .attr('x', 0)
    .attr('y', 5)
    .attr('width', 20)
    .attr('height', 20)
    .attr('fill', color(0.8))
    .attr('stroke', '#ccc');

  legend.append('text')
    .attr('x', 25)
    .attr('y', 15)
    .attr('dy', '0.35em')
    .style('font-size', '10px')
    .text('Yes');

  // make container scrollable when overflowing
  if (totalWidth > container.clientWidth || totalHeight > container.clientHeight) {
    container.style.overflow = 'auto';
  } else {
    container.style.overflow = 'hidden';
  }
}
