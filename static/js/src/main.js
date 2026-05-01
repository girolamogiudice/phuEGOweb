// main.js

import * as Network from "./network.js";
import { highlightGenesInGraph } from "./highlighting.js";
import { renderMatrixHeatmap } from "./heatmap_matrix.js";

// Extend and expose
window.Network = {
  ...Network,
  highlightGenesInGraph
};
window.renderMatrixHeatmap = renderMatrixHeatmap;

console.log("✅ Final window.Network:", Object.keys(window.Network));
