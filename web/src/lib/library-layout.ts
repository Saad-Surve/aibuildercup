import type { LibraryNode } from "@/lib/creator-library";

/** Move image labels apart, retaining each original PCA anchor for the leader line. */
export function thumbnailLabels(
  nodes: LibraryNode[],
  width: number,
  height: number,
) {
  const tileWidth = height < 500 ? 70 : 92;
  const tileHeight = height < 500 ? 40 : 52;
  const labels = nodes
    .filter((node) => node.modality === "image")
    .map((node) => ({
      id: node.id,
      x: ((8 + (node.x ?? 0.5) * 84) * width) / 100,
      y: ((8 + (node.y ?? 0.5) * 84) * height) / 100,
    }));
  for (let iteration = 0; iteration < 100; iteration++) {
    let collisions = 0;
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const a = labels[i],
          b = labels[j];
        const dx = b.x - a.x,
          dy = b.y - a.y;
        const overlapX = tileWidth + 10 - Math.abs(dx);
        const overlapY = tileHeight + 10 - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;
        collisions++;
        if (overlapX < overlapY) {
          const push = Math.sign(dx || 1) * (overlapX / 2 + 0.1);
          a.x -= push;
          b.x += push;
        } else {
          const push = Math.sign(dy || 1) * (overlapY / 2 + 0.1);
          a.y -= push;
          b.y += push;
        }
      }
    }
    for (const label of labels) {
      label.x = Math.max(
        tileWidth / 2 + 8,
        Math.min(width - tileWidth / 2 - 8, label.x),
      );
      label.y = Math.max(
        tileHeight / 2 + 8,
        Math.min(height - tileHeight / 2 - 40, label.y),
      );
    }
    if (!collisions) break;
  }
  return new Map(
    labels.map((label) => [
      label.id,
      { x: (label.x / width) * 100, y: (label.y / height) * 100 },
    ]),
  );
}
