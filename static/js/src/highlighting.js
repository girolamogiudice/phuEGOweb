import { instances, expandNode } from "./network.js";

export function highlightGenesInGraph(instanceKey, genes) {
  const inst = instances[instanceKey];
  if (!inst) {
    console.warn(`❌ Instance not found: ${instanceKey}`);
    return;
  }

  const graph = inst.graph;

  const currentGeneSet = new Set(
    genes.map(g => String(g).trim().toUpperCase()).filter(Boolean)
  );

  // -------------------------
  // TOGGLE OFF
  // -------------------------
  const prev = inst.activeGeneSet || null;
  const prevGraphKey = inst.activeGeneSetKey || null;
  const sameGraph = prevGraphKey === instanceKey;

  const isSame =
    sameGraph &&
    prev &&
    prev.size === currentGeneSet.size &&
    [...currentGeneSet].every(g => prev.has(g));

 if (isSame) {
  console.log("🔁 Same gene set — toggling off");

  graph.forEachNode((node, attrs) => {
    graph.setNodeAttribute(node, "highlighted", false);

    if (inst.isSupernodes && !attrs.isPurple) {
      graph.setNodeAttribute(node, "visible", false);
      graph.setNodeAttribute(node, "size", 0);
      graph.setNodeAttribute(node, "label", "");
      graph.setNodeAttribute(node, "expanded", false);
    }
  });

  inst.activeGeneSet = null;
  inst.activeGeneSetKey = null;

  inst.sigma.refresh();
  return;
}

  // -------------------------
  // CLEAR PREVIOUS HIGHLIGHTS
  // -------------------------
  graph.forEachNode(node =>
    graph.setNodeAttribute(node, "highlighted", false)
  );

  let matched = 0;

  // -------------------------
  // MAIN MATCHING LOOP
  // -------------------------
  graph.forEachNode((node, attrs) => {
    let hit = false;

    const label = String(attrs.label_base || "").toUpperCase();
    if (currentGeneSet.has(label)) hit = true;

    if (inst.isSupernodes) {
      const neigh = attrs.neigh || [];
      if (!hit && Array.isArray(neigh)) {
        hit = neigh.some(n => {
          if (!graph.hasNode(n)) return false;
          const nLabel = graph.getNodeAttribute(n, "label_base");
          return nLabel && currentGeneSet.has(String(nLabel).toUpperCase());
        });
      }
    }

    if (hit) {
      matched++;

      graph.setNodeAttribute(node, "highlighted", true);

      // 🔥 unified behavior
      if (inst.isSupernodes) {
        expandNode(graph, node);
      }
    }
  });

  if (matched === 0) {
    console.warn("⚠️ No nodes matched genes:", [...currentGeneSet]);
    return;
  }

  inst.activeGeneSet = currentGeneSet;
  inst.activeGeneSetKey = instanceKey;

  console.log(`✅ Highlighted ${matched} node(s)`);
  inst.sigma.refresh();
}
