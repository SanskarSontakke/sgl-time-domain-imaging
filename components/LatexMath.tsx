"use client";

import React, { useMemo } from "react";
import katex from "katex";

interface LatexMathProps {
  math: string;
  block?: boolean;
  className?: string;
}

export default function LatexMath({ math, block = false, className = "" }: LatexMathProps) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(math, {
        displayMode: block,
        throwOnError: false,
      });
    } catch {
      return math;
    }
  }, [math, block]);

  if (block) {
    return (
      <div
        className={`math-block ${className}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  return (
    <span
      className={`math-inline ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
