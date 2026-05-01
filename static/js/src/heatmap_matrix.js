import * as d3 from "d3";

export function renderMatrixHeatmap(containerId, matrixData) {

  const container = document.getElementById(containerId);
  if (!container || !matrixData) return;

  container.innerHTML = "";

  const labels = matrixData.labels || [];
  const matrix = matrixData.matrix || [];

  const size = 25;
  const margin = { top: 150, right: 50, bottom: 50, left: 150 };

  const width = labels.length * size;
  const height = labels.length * size;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleBand()
    .domain(labels)
    .range([0, width])
    .padding(0.05);

  const y = d3.scaleBand()
    .domain(labels)
    .range([0, height])
    .padding(0.05);

  const color = d3.scaleSequential(d3.interpolateViridis)
    .domain([0, 1]);

  matrix.forEach((row, i) => {
    row.forEach((val, j) => {
      g.append("rect")
        .attr("x", x(labels[j]))
        .attr("y", y(labels[i]))
        .attr("width", x.bandwidth())
        .attr("height", y.bandwidth())
        .attr("fill", color(val))
        .append("title")
        .text(`${labels[i]} vs ${labels[j]}: ${val.toFixed(3)}`);
    });
  });

  // X labels
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("transform", "rotate(90)")
    .attr("x", 5)
    .attr("y", -2)
    .style("text-anchor", "start");

  // Y labels
  g.append("g")
    .call(d3.axisLeft(y));
}
