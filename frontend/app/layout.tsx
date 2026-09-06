import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Evaluation Platform",
  description: "When you change an agent, did it actually get better?",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topnav">
          <Link href="/" className="brand">
            Agent Evaluation Platform
          </Link>
          <nav>
            <Link href="/agents">Agents</Link>
            <Link href="/datasets">Datasets</Link>
            <Link href="/runs/new">New run</Link>
            <Link href="/runs/compare">Compare</Link>
          </nav>
        </header>
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
