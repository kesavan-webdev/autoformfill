import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "W-9 Autofill",
  description: "Upload a W-9 PDF and review the extracted fields.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
