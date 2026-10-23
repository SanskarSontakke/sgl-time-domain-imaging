"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { 
  ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2, 
  Download, X, Sparkles, Move, Eye
} from "lucide-react";

interface MediaZoomViewerProps {
  src?: string;
  alt?: string;
  title: string;
  badge?: string;
  desc?: string;
  downloadName?: string;
  children?: React.ReactNode;
  aspectRatio?: string;
  headerControls?: React.ReactNode;
  footerControls?: React.ReactNode;
  className?: string;
}

export default function MediaZoomViewer({
  src,
  alt,
  title,
  badge = "1080p Full HD",
  desc,
  downloadName,
  children,
  aspectRatio = "aspect-video",
  headerControls,
  footerControls,
  className = "",
}: MediaZoomViewerProps) {
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const containerRef = useRef<HTMLDivElement | null>(null);

  // Zoom handler with clamping
  const handleZoomChange = useCallback((newZoom: number) => {
    const clamped = Math.max(1, Math.min(3, Math.round(newZoom * 100) / 100));
    setZoom(clamped);
    if (clamped === 1) {
      setPan({ x: 0, y: 0 });
    }
  }, []);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
        handleZoomChange(1);
      } else if (isFullscreen) {
        if (e.key === "+" || e.key === "=") {
          handleZoomChange(zoom + 0.25);
        } else if (e.key === "-" || e.key === "_") {
          handleZoomChange(zoom - 0.25);
        } else if (e.key === "0") {
          handleZoomChange(1);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen, zoom, handleZoomChange]);

  // Drag-to-pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || zoom <= 1) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Double click toggles zoom between 1x and 1.5x
  const handleDoubleClick = () => {
    if (zoom === 1) {
      handleZoomChange(1.5);
    } else {
      handleZoomChange(1);
    }
  };

  // Wheel zoom handler
  const handleWheel = (e: React.WheelEvent) => {
    if (!isFullscreen && zoom === 1 && Math.abs(e.deltaY) < 10) return;
    if (e.ctrlKey || isFullscreen) {
      e.preventDefault();
      if (e.deltaY < 0) {
        handleZoomChange(zoom + 0.15);
      } else {
        handleZoomChange(zoom - 0.15);
      }
    }
  };

  const toggleFullscreen = () => {
    if (!isFullscreen) {
      setIsFullscreen(true);
      // Try HTML5 Fullscreen API if supported
      if (containerRef.current?.requestFullscreen && !document.fullscreenElement) {
        containerRef.current.requestFullscreen().catch(() => {});
      }
    } else {
      setIsFullscreen(false);
      handleZoomChange(1);
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    }
  };

  // Synchronize with browser native fullscreen change
  useEffect(() => {
    const handleNativeFsChange = () => {
      if (!document.fullscreenElement && isFullscreen) {
        setIsFullscreen(false);
        handleZoomChange(1);
      }
    };
    document.addEventListener("fullscreenchange", handleNativeFsChange);
    return () => document.removeEventListener("fullscreenchange", handleNativeFsChange);
  }, [isFullscreen, handleZoomChange]);

  return (
    <div 
      ref={containerRef}
      className={
        isFullscreen
          ? "fixed inset-0 z-[99999] w-screen h-screen bg-slate-950 flex flex-col animate-fadeIn select-none overflow-hidden"
          : `relative w-full bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-lg flex flex-col ${className}`
      }
    >
      {/* Header Bar */}
      <div className={`p-2.5 sm:p-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2 shrink-0 ${
        isFullscreen ? "h-14 px-4 bg-slate-900/95 backdrop-blur-md" : ""
      }`}>
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <div className="truncate">
            <span className="text-xs sm:text-sm font-mono font-bold text-blue-400 truncate max-w-[260px] sm:max-w-md block">
              {title}
            </span>
            {isFullscreen && (
              <span className="text-[10px] text-slate-400 font-mono hidden sm:block">
                1080p Full HD Native Inspector • Press ESC to exit
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {headerControls}

          {/* Zoom controls in header when in fullscreen */}
          {isFullscreen && (
            <div className="flex items-center bg-slate-800 p-0.5 rounded-lg border border-slate-700">
              <button
                type="button"
                onClick={() => handleZoomChange(zoom - 0.25)}
                disabled={zoom <= 1}
                className="p-1 text-slate-300 hover:text-white disabled:opacity-30 rounded hover:bg-slate-700 transition-colors"
                title="Zoom Out (-)"
              >
                <ZoomOut size={13} />
              </button>

              <button
                type="button"
                onClick={() => handleZoomChange(1)}
                className="font-mono text-[11px] text-slate-200 px-2 py-0.5 rounded hover:bg-slate-700 transition-colors font-bold"
                title="Reset Zoom (100%)"
              >
                {Math.round(zoom * 100)}%
              </button>

              <button
                type="button"
                onClick={() => handleZoomChange(zoom + 0.25)}
                disabled={zoom >= 3}
                className="p-1 text-slate-300 hover:text-white disabled:opacity-30 rounded hover:bg-slate-700 transition-colors"
                title="Zoom In (+)"
              >
                <ZoomIn size={13} />
              </button>

              <div className="w-px h-3 bg-slate-700 mx-0.5" />

              {[1, 1.5, 2].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => handleZoomChange(lvl)}
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                    zoom === lvl 
                      ? "bg-blue-600 text-white font-bold" 
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {lvl}x
                </button>
              ))}
            </div>
          )}

          {src && (
            <a
              href={src}
              download={downloadName || "sgl_simulation_1080p.gif"}
              className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded font-mono font-semibold flex items-center gap-1 transition-colors border border-slate-700"
              title="Save 1080p Master File"
            >
              <Download size={11} />
              <span className="hidden sm:inline">Save 1080p</span>
            </a>
          )}

          {/* Fullscreen Toggle Button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className={`text-[10px] px-2.5 py-1 rounded font-mono font-bold flex items-center gap-1.5 transition-colors ${
              isFullscreen 
                ? "bg-slate-800 hover:bg-red-900/80 text-white border border-slate-700" 
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-xs"
            }`}
            title={isFullscreen ? "Exit Fullscreen (Esc)" : "Expand Fullscreen 1080p Inspector"}
          >
            {isFullscreen ? (
              <>
                <Minimize2 size={12} />
                <span>Exit Fullscreen</span>
              </>
            ) : (
              <>
                <Maximize2 size={12} />
                <span>Inspect HD</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Viewport Area (Single Persistent DOM Node: Canvas & Img Never Unmount!) */}
      <div 
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
        className={
          isFullscreen
            ? `flex-1 w-full relative bg-black flex items-center justify-center overflow-hidden select-none p-3 min-h-0 ${
                zoom > 1 ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default"
              }`
            : `relative w-full ${aspectRatio} bg-black flex items-center justify-center overflow-hidden select-none ${
                zoom > 1 ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default"
              }`
        }
      >
        {/* Zoomable Content Layer */}
        <div
          style={{
            transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.15s ease-out",
          }}
          className="w-full h-full max-w-full max-h-full flex items-center justify-center relative"
        >
          {children ? (
            children
          ) : src ? (
            <img
              src={src}
              alt={alt || title}
              className="w-full h-full object-contain pointer-events-none"
            />
          ) : null}
        </div>

        {/* Floating Zoom Toolbar when in card mode */}
        {!isFullscreen && (
          <div className="absolute bottom-2.5 right-2.5 z-20 flex items-center gap-1 bg-slate-900/90 backdrop-blur-md px-2 py-1 rounded-lg border border-slate-700/80 shadow-md">
            <button
              type="button"
              onClick={() => handleZoomChange(zoom - 0.25)}
              disabled={zoom <= 1}
              className="text-slate-300 hover:text-white disabled:opacity-30 p-1 rounded hover:bg-slate-800 transition-colors"
              title="Zoom Out"
            >
              <ZoomOut size={13} />
            </button>

            <button
              type="button"
              onClick={() => handleZoomChange(1)}
              className="font-mono text-[10px] text-slate-300 hover:text-white px-1.5 py-0.5 rounded hover:bg-slate-800 transition-colors font-semibold"
              title="Reset Zoom (100%)"
            >
              {Math.round(zoom * 100)}%
            </button>

            <button
              type="button"
              onClick={() => handleZoomChange(zoom + 0.25)}
              disabled={zoom >= 3}
              className="text-slate-300 hover:text-white disabled:opacity-30 p-1 rounded hover:bg-slate-800 transition-colors"
              title="Zoom In"
            >
              <ZoomIn size={13} />
            </button>

            <div className="w-px h-3 bg-slate-700 mx-0.5" />

            <button
              type="button"
              onClick={toggleFullscreen}
              className="text-blue-400 hover:text-blue-300 p-1 rounded hover:bg-slate-800 transition-colors"
              title="Open Fullscreen Lightbox"
            >
              <Maximize2 size={13} />
            </button>
          </div>
        )}

        {/* Pan hint indicator when zoomed */}
        {zoom > 1 && (
          <div className="absolute top-3 left-3 z-20 bg-slate-900/90 backdrop-blur-md px-2.5 py-1 rounded-lg text-[10px] font-mono text-slate-300 border border-slate-700 flex items-center gap-1.5 pointer-events-none shadow-md">
            <Move size={11} className="text-blue-400" />
            <span>Drag to pan • Double click to reset</span>
          </div>
        )}
      </div>

      {/* Footer Controls Toolbar */}
      {footerControls && (
        <div className="shrink-0">
          {footerControls}
        </div>
      )}

      {/* Scientific Description Caption Strip */}
      {desc && (
        <div className={`px-3 py-2 bg-slate-950 text-slate-400 text-[10px] sm:text-[11px] border-t border-slate-900 leading-snug shrink-0 ${
          isFullscreen ? "text-center bg-slate-950/95" : ""
        }`}>
          {desc}
        </div>
      )}
    </div>
  );
}
