import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KubanFy 2 | Tu universo musical",
  description: "Tu cultura. Tu sonido. Tu lugar. Descubre música de Cuba y del mundo.",
  viewport: "width=device-width, initial-scale=1, viewport-fit=cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body>{children}</body></html>;
}
