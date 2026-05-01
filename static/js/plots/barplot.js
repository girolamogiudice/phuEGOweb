/* BARPLOT */
function renderD3Barplot(rows, svg, opts = {}) {
  clearSVG(svg);

  const width = svg.parentElement.clientWidth || 800;
  const data = preprocessEnrichmentData(rows, opts.topN || 20);

  const barHeight = 25;
  const margin = { top: 20, right: 150, bottom: 60, left: 320 };
  const height = Math.max(400, data.length * barHeight + margin.top + margin.bottom);

  svg.innerHTML = '';
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  
  const w = width - margin.left - margin.right;
  const h = height - margin.top - margin.bottom;

  const svgSelection = d3.select(svg);
  
  const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on('zoom', (event) => {
      g.attr('transform', `translate(${margin.left + event.transform.x},${margin.top + event.transform.y}) scale(${event.transform.k})`);
    });
  
  svgSelection.call(zoom);

  const x = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.logp) * 1.1])
    .range([0, w]);

  const y = d3.scaleBand()
    .domain(data.map(d => d.desc || d.term))
    .range([0, h])
    .padding(0.15);

  const color = d3.scaleSequential(d3.interpolateInferno)
    .domain([d3.max(data, d => d.pval), d3.min(data, d => d.pval)]);

  const g = svgSelection.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  g.selectAll('rect')
    .data(data)
    .enter()
    .append('rect')
    .attr('y', d => y(d.desc || d.term))
    .attr('height', y.bandwidth())
    .attr('x', 0)
    .attr('width', d => x(d.logp))
    .attr('fill', d => color(d.pval))
    .append('title')
    .text(d => `${d.desc || d.term}\nP=${d.pval.toExponential(2)}\nGenes=${d.size}`);

  g.append('g').call(d3.axisLeft(y).tickSize(0).tickPadding(6));
  g.append('g')
    .attr('transform', `translate(0,${h})`)
    .call(d3.axisBottom(x).ticks(5))
    .append('text')
    .attr('x', w / 2)
    .attr('y', 40)
    .attr('fill', 'black')
    .style('font-size', '12px')
    .text('-log10(P-value)');

  const legend = g.append('g')
    .attr('transform', `translate(${w + 20}, 0)`);

  legend.append('text')
    .attr('x', 0)
    .attr('y', 0)
    .style('font-size', '12px')
    .style('font-weight', 'bold')
    .text('P-value');

  const legendHeight = 200;
  const legendWidth = 20;

  const gradientId = 'barplot-gradient-' + Math.random().toString(36).slice(2, 9);
  const defs = svg.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'defs'));
  const gradient = d3.select(defs).append('linearGradient')
    .attr('id', gradientId)
    .attr('x1', '0%')
    .attr('y1', '0%')
    .attr('x2', '0%')
    .attr('y2', '100%');

  const numStops = 10;
  for (let i = 0; i <= numStops; i++) {
    const t = i / numStops;
    gradient.append('stop')
      .attr('offset', `${t * 100}%`)
      .attr('stop-color', color(d3.min(data, d => d.pval) + t * (d3.max(data, d => d.pval) - d3.min(data, d => d.pval))));
  }

  legend.append('rect')
    .attr('x', 0)
    .attr('y', 15)
    .attr('width', legendWidth)
    .attr('height', legendHeight)
    .style('fill', `url(#${gradientId})`);

  const legendAxis = d3.axisRight(d3.scaleLinear()
    .domain([d3.min(data, d => d.pval), d3.max(data, d => d.pval)])
    .range([15, legendHeight + 15]))
    .ticks(5)
    .tickFormat(d => d.toExponential(1));

  legend.append('g')
    .attr('transform', `translate(${legendWidth}, 0)`)
    .call(legendAxis);
}
