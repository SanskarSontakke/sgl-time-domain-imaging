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
  badge = "Demonstration Asset",
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

  // Fullscreen modal specific zoom
  const [modalZoom, setModalZoom] = useState<number>(1);
  const [modalPan, setModalPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isModalDragging, setIsModalDragging] = useState<boolean>(false);
  const [modalDragStart, setModalDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const containerRef = useRef<HTMLDivElement | null>(null);

  // Reset in-card pan when zoom reset
  const handleZoomChange = (newZoom: number) => {
    const clamped = Math.max(1, Math.min(3, Math.round(newZoom * 100) / 100));
    setZoom(clamped);
    if (clamped === 1) {
      setPan({ x: 0, y: 0 });
    }
  };

  const handleModalZoomChange = (newZoom: number) => {
    const clamped = Math.max(1, Math.min(4, Math.round(newZoom * 100) / 100));
    setModalZoom(clamped);
    if (clamped === 1) {
      setModalPan({ x: 0, y: 0 });
    }
  };

  // Keyboard navigation for fullscreen modal
  useEffect(() => {
    if (!isFullscreen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsFullscreen(false);
      } else if (e.key === "+" || e.key === "=") {
        handleModalZoomChange(modalZoom + 0.25);
      } else if (e.key === "-" || e.key === "_") {
        handleModalZoomChange(modalZoom - 0.25);
      } else if (e.key === "0") {
        handleModalZoomChange(1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen, modalZoom]);

  // In-card dragging
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

  // Modal dragging
  const handleModalMouseDown = (e: React.MouseEvent) => {
    if (modalZoom <= 1) return;
    setIsModalDragging(true);
    setModalDragStart({ x: e.clientX - modalPan.x, y: e.clientY - modalPan.y });
  };

  const handleModalMouseMove = (e: React.MouseEvent) => {
    if (!isModalDragging || modalZoom <= 1) return;
    setModalPan({
      x: e.clientX - modalDragStart.x,
      y: e.clientY - modalDragStart.y,
    });
  };

  const handleModalMouseUp = () => {
    setIsModalDragging(false);
  };

  return (
    <>
      <div className={`bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-lg flex flex-col ${className}`}>
        {/* Header Bar */}
        <div className="p-2.5 sm:p-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
            <span className="text-xs font-mono font-bold text-blue-400 truncate max-w-[260px] sm:max-w-md">
              {title}
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {headerControls}

            {src && (
              <a
                href={src}
                download={downloadName || "sgl_simulation.gif"}
                className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded font-mono font-semibold flex items-center gap-1 transition-colors border border-slate-700"
                title="Save 1080p Asset"
              >
                <Download size={11} />
                <span className="hidden sm:inline">Save 1080p</span>
              </a>
            )}

            <button
              onClick={() => {
                setModalZoom(1);
                setModalPan({ x: 0, y: 0 });
                setIsFullscreen(true);
              }}
              className="text-[10px] bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded font-mono font-bold flex items-center gap-1 transition-colors"
              title="Expand Fullscreen 1080p Inspector"
            >
              <Maximize2 size={11} />
              <span className="hidden sm:inline">Inspect HD</span>
            </button>
          </div>
        </div>

        {/* Viewport Area with Zoom & Pan */}
        <div 
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className={`relative w-full ${aspectRatio} bg-black flex items-center justify-center overflow-hidden select-none ${
            zoom > 1 ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default"
          }`}
        >
          {/* Zoomable Content Layer */}
          <div
            style={{
              transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
              transformOrigin: "center center",
              transition: isDragging ? "none" : "transform 0.15s ease-out",
            }}
            className="w-full h-full flex items-center justify-center"
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

          {/* In-Card Floating Zoom Toolbar */}
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
              onClick={() => {
                setModalZoom(1);
                setModalPan({ x: 0, y: 0 });
                setIsFullscreen(true);
              }}
              className="text-blue-400 hover:text-blue-300 p-1 rounded hover:bg-slate-800 transition-colors"
              title="Open Fullscreen Lightbox"
            >
              <Maximize2 size={13} />
            </button>
          </div>

          {/* Pan hint indicator when zoomed */}
          {zoom > 1 && (
            <div className="absolute top-2.5 left-2.5 z-20 bg-slate-900/80 backdrop-blur-md px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 border border-slate-700 flex items-center gap-1 pointer-events-none">
              <Move size={10} className="text-blue-400" />
              <span>Drag to pan</span>
            </div>
          )}
        </div>

        {/* Footer Controls & Caption */}
        {footerControls}

        {desc && (
          <div className="px-3 py-2 bg-slate-950 text-slate-400 text-[10px] sm:text-[11px] border-t border-slate-900 leading-snug">
            {desc}
          </div>
        )}
      </div>

      {/* Cinematic Fullscreen Lightbox Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-[99999] bg-slate-950/95 backdrop-blur-xl flex flex-col animate-fadeIn">
          {/* Top Modal Navigation */}
          <div className="h-14 bg-slate-900/90 border-b border-slate-800 px-4 flex items-center justify-between gap-4 shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <div className="truncate">
                <h3 className="font-bold text-sm text-white font-mono truncate">
                  {title}
                </h3>
                <span className="text-[11px] text-blue-400 font-mono">
                  1080p Full HD Native Inspector • 16:9 Widescreen
                </span>
              </div>
            </div>

            {/* Modal Zoom Controls Toolbar */}
            <div className="flex items-center gap-2 shrink-0">
              <div className="flex items-center bg-slate-800 p-1 rounded-lg border border-slate-700">
                <button
                  type="button"
                  onClick={() => handleModalZoomChange(modalZoom - 0.25)}
                  disabled={modalZoom <= 1}
                  className="p-1.5 text-slate-300 hover:text-white disabled:opacity-30 rounded hover:bg-slate-700 transition-colors"
                  title="Zoom Out (-)"
                >
                  <ZoomOut size={15} />
                </button>

                <button
                  type="button"
                  onClick={() => handleModalZoomChange(1)}
                  className="font-mono text-xs text-slate-200 px-2.5 py-1 rounded hover:bg-slate-700 transition-colors font-bold"
                  title="Reset (100%)"
                >
                  {Math.round(modalZoom * 100)}%
                </button>

                <button
                  type="button"
                  onClick={() => handleModalZoomChange(modalZoom + 0.25)}
                  disabled={modalZoom >= 4}
                  className="p-1.5 text-slate-300 hover:text-white disabled:opacity-30 rounded hover:bg-slate-700 transition-colors"
                  title="Zoom In (+)"
                >
                  <ZoomIn size={15} />
                </button>

                <div className="w-px h-4 bg-slate-700 mx-1" />

                {[1, 1.5, 2].map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => handleModalZoomChange(lvl)}
                    className={`text-[11px] font-mono px-2 py-0.5 rounded transition-colors ${
                      modalZoom === lvl 
                        ? "bg-blue-600 text-white font-bold" 
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {lvl}x
                  </button>
                ))}
              </div>

              {src && (
                <a
                  href={src}
                  download={downloadName || "sgl_simulation_1080p.gif"}
                  className="btn btn-sm btn-primary text-xs flex items-center gap-1.5 px-3 py-1.5"
                  title="Save 1080p Master File"
                >
                  <Download size={13} />
                  <span>Download 1080p</span>
                </a>
              )}

              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                className="p-2 bg-slate-800 hover:bg-red-900/80 text-slate-300 hover:text-white rounded-lg border border-slate-700 transition-colors"
                title="Close Fullscreen (Esc)"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Fullscreen Viewport Area */}
          <div 
            onMouseDown={handleModalMouseDown}
            onMouseMove={handleModalMouseMove}
            onMouseUp={handleModalMouseUp}
            onMouseLeave={handleModalMouseUp}
            className={`flex-1 w-full bg-black relative flex items-center justify-center overflow-hidden p-4 select-none ${
              modalZoom > 1 ? (isModalDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default"
            }`}
          >
            <div
              style={{
                transform: `scale(${modalZoom}) translate(${modalPan.x / modalZoom}px, ${modalPan.y / modalZoom}px)`,
                transformOrigin: "center center",
                transition: isModalDragging ? "none" : "transform 0.15s ease-out",
                maxWidth: "100%",
                maxHeight: "100%",
              }}
              className="w-full h-full flex items-center justify-center"
            >
              {children ? (
                <div className="w-full max-w-6xl aspect-video flex items-center justify-center">
                  {children}
                </div>
              ) : src ? (
                <img
                  src={src}
                  alt={alt || title}
                  className="max-w-full max-h-[88vh] object-contain shadow-2xl rounded-lg pointer-events-none"
                />
              ) : null}
            </div>

            {modalZoom > 1 && (
              <div className="absolute top-4 left-4 z-30 bg-slate-900/90 backdrop-blur-md px-3 py-1 rounded-lg text-xs font-mono text-slate-300 border border-slate-700 flex items-center gap-1.5 pointer-events-none">
                <Move size={13} className="text-blue-400" />
                <span>Click & drag to inspect details across 1080p canvas</span>
              </div>
            )}
          </div>

          {/* Bottom Info Bar in Modal */}
          {desc && (
            <div className="p-3 bg-slate-900/90 border-t border-slate-800 text-xs text-slate-300 text-center font-sans">
              <p className="max-w-4xl mx-auto leading-relaxed">{desc}</p>
            </div>
          )}
        </div>
      )}
    </>
  );
}
