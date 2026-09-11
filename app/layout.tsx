import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solar Gravitational Lens (SGL) Time-Domain Imaging",
  description:
    "Direct surface recovery of rotating, cloudy exo-Earths using the Solar Gravitational Lens. Complete scientific documentation, interactive simulations, and judge presentation board.",
  authors: [{ name: "Sanskar Sontakke" }],
  keywords: [
    "Solar Gravitational Lens",
    "SGL",
    "Exoplanet Imaging",
    "Time-Domain Inversion",
    "Astrophysics",
    "Direct Imaging",
    "NASA NIAC",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
      </head>
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
        {children}
      </body>
    </html>
  );
}
