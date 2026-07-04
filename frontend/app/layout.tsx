import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Study Copilot",
  description: "Seu assistente pessoal do Blackboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="gradient-bg min-h-screen antialiased">{children}</body>
    </html>
  );
}
