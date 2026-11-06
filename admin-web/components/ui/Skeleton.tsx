/** Shimmering placeholder while data loads. Lines stack with the theme's spacing. */
export function Skeleton({ height = 18, width, lines = 1 }: { height?: number; width?: number | string; lines?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="skeleton-stack">
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton" style={{ height, width }} />
      ))}
    </div>
  );
}
