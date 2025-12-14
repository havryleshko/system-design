"use client";

import { useEffect, useState } from "react";

type CubeLoaderProps = {
  size?: number;
  color?: string;
};

export default function CubeLoader({ size = 60, color = "var(--accent)" }: CubeLoaderProps) {
  const [phase, setPhase] = useState<0 | 1 | 2 | 3>(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhase((prev) => ((prev + 1) % 4) as 0 | 1 | 2 | 3);
    }, 600);
    return () => clearInterval(interval);
  }, []);

  const cubeSize = size / 2.5;
  const gap = phase === 0 ? 0 : phase === 1 ? cubeSize * 0.3 : cubeSize * 0.5;

  return (
    <div
      className="cube-loader-container"
      style={{
        width: size * 1.5,
        height: size * 1.5,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        className="cube-loader-grid"
        style={{
          display: "grid",
          gridTemplateColumns: phase >= 2 ? "1fr 1fr" : "1fr",
          gridTemplateRows: phase >= 1 ? "1fr 1fr" : "1fr",
          gap: gap,
          transition: "gap 400ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {/* Single cube in phase 0, splits to 2 in phase 1, then 4 in phase 2-3 */}
        <div
          className="cube-cell"
          style={{
            width: cubeSize,
            height: cubeSize,
            background: color,
            borderRadius: 4,
            opacity: 1,
            transform: phase === 3 ? "scale(0.9)" : "scale(1)",
            transition: "transform 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease",
            boxShadow: `0 0 20px ${color}40`,
          }}
        />
        {phase >= 1 && (
          <div
            className="cube-cell"
            style={{
              width: cubeSize,
              height: cubeSize,
              background: color,
              borderRadius: 4,
              opacity: phase >= 1 ? 1 : 0,
              transform: phase === 3 ? "scale(0.9)" : "scale(1)",
              transition: "transform 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease",
              boxShadow: `0 0 20px ${color}40`,
            }}
          />
        )}
        {phase >= 2 && (
          <>
            <div
              className="cube-cell"
              style={{
                width: cubeSize,
                height: cubeSize,
                background: color,
                borderRadius: 4,
                opacity: phase >= 2 ? 1 : 0,
                transform: phase === 3 ? "scale(0.9)" : "scale(1)",
                transition: "transform 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease",
                boxShadow: `0 0 20px ${color}40`,
              }}
            />
            <div
              className="cube-cell"
              style={{
                width: cubeSize,
                height: cubeSize,
                background: color,
                borderRadius: 4,
                opacity: phase >= 2 ? 1 : 0,
                transform: phase === 3 ? "scale(0.9)" : "scale(1)",
                transition: "transform 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease",
                boxShadow: `0 0 20px ${color}40`,
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}

