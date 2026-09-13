import type { CSSProperties } from "react";

/** Decorative isometric blocks, unrelated to recorded progress or streaks. */
export function VoxelScene({ compact = false }: { compact?: boolean }) {
  const blocks = [
    [0, 0, 1], [1, 0, 1], [2, 0, 2], [3, 0, 3],
    [0, 1, 1], [1, 1, 2], [2, 1, 3], [3, 1, 4],
    [0, 2, 1], [1, 2, 2], [2, 2, 3], [3, 2, 3],
  ];
  return (
    <div className={"voxel-scene" + (compact ? " voxel-compact" : "")} aria-hidden="true">
      <svg viewBox="0 0 360 240" focusable="false">
        <g className="voxel-grid" fill="none" stroke="currentColor" strokeWidth="1">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <g key={i}>
              <path d={`M${34 + i * 26} ${144 - i * 13} l156 78`} />
              <path d={`M${34 + i * 26} ${144 + i * 13} l156 -78`} />
            </g>
          ))}
        </g>
        {blocks.map(([x, y, height], i) => {
          const px = 140 + (x - y) * 27;
          const py = 130 + (x + y) * 13.5;
          const top = py - height * 24;
          return (
            <g key={i} className="voxel-block" style={{ "--block-index": i } as CSSProperties}>
              <polygon className="voxel-left" points={`${px - 27},${top} ${px},${top + 13.5} ${px},${py + 13.5} ${px - 27},${py}`} />
              <polygon className="voxel-right" points={`${px},${top + 13.5} ${px + 27},${top} ${px + 27},${py} ${px},${py + 13.5}`} />
              <polygon className="voxel-top" points={`${px},${top - 13.5} ${px + 27},${top} ${px},${top + 13.5} ${px - 27},${top}`} />
            </g>
          );
        })}
        <g className="voxel-satellite">
          <polygon fill="#a6edee" points="262,39 277,46.5 262,54 247,46.5" />
          <polygon fill="#5babad" points="247,46.5 262,54 262,70 247,62.5" />
          <polygon fill="#328689" points="262,54 277,46.5 277,62.5 262,70" />
        </g>
        <g className="voxel-spark" fill="currentColor">
          <path d="M78 70h5v5h-5z M83 65h5v5h-5z M83 75h5v5h-5z M88 70h5v5h-5z" />
          <path d="M282 144h4v4h-4z M286 140h4v4h-4z M286 148h4v4h-4z M290 144h4v4h-4z" />
        </g>
      </svg>
    </div>
  );
}
