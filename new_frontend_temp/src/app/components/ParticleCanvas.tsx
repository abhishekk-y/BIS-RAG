import { useEffect, useRef } from "react";

/* ═══ PARTICLE CANVAS ═══ */
export function ParticleCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    let raf: number, t = 0;
    const dpr = window.devicePixelRatio || 1;

    // Symbols and color palette for the animation
    const sym = "⬡◎⊕△□◇●○⬢⏣".split("");
    const pal = ["#ff3d00", "#ff6b35", "#ffb300", "#00e676", "#448aff", "#e040fb", "#ffffff"];

    const resize = () => {
      c.width = c.offsetWidth * dpr;
      c.height = c.offsetHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      t += 0.006;
      const W = c.offsetWidth, H = c.offsetHeight;
      ctx.clearRect(0, 0, W, H);

      const cols = 28, rows = 18, cw = W / cols, ch = H / rows;

      for (let r = 0; r < rows; r++) {
        for (let col = 0; col < cols; col++) {
          const x = col * cw + cw / 2, y = r * ch + ch / 2;

          // Calculate distance from center to create the wave effect
          const dx = (col - cols / 2) / cols, dy = (r - rows / 2) / rows;
          const d = Math.sqrt(dx * dx + dy * dy);

          // Math functions driving the animation
          const w1 = Math.sin(d * 14 - t * 3) * 0.5 + 0.5;
          const w2 = Math.cos(col * 0.25 + t * 2) * Math.sin(r * 0.35 - t * 1.2) * 0.5 + 0.5;
          const a = Math.max(0, w1 * w2 * (1 - d * 1.3));

          if (a < 0.06) continue;

          ctx.font = `${11 + w1 * 5}px "Share Tech Mono", monospace`;
          ctx.fillStyle = pal[(col + r * 3 + ~~(t * 0.8)) % pal.length];
          ctx.globalAlpha = a * 0.85;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(sym[(col * 7 + r * 11 + ~~(t * 2)) % sym.length], x, y);
        }
      }

      // Draw the subtle background glow gradient
      const g = ctx.createRadialGradient(W * 0.5, H * 0.4, 0, W * 0.5, H * 0.4, W * 0.45);
      g.addColorStop(0, "rgba(255,61,0,0.07)");
      g.addColorStop(0.4, "rgba(68,138,255,0.03)");
      g.addColorStop(1, "transparent");

      ctx.globalAlpha = 1;
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);

      raf = requestAnimationFrame(draw);
    };

    draw();

    // Cleanup on unmount
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="absolute inset-0 w-full h-full" />;
}
