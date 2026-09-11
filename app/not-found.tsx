import Link from "next";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 text-slate-800 p-4">
      <h1 className="text-4xl font-extrabold text-blue-600 mb-2">404</h1>
      <p className="text-sm text-slate-600 mb-4">Page not found</p>
      <a href="/" className="btn btn-primary text-xs">
        Return to Home
      </a>
    </div>
  );
}
