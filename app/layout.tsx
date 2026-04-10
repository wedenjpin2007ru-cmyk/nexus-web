import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import TopNav from "./components/top-nav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nexus",
  description: "Nexus — доступ к клиенту по подписке и промокодам",
  icons: [{ rel: "icon", url: "/app.ico" }],
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://nexus-web-production-d7a0.up.railway.app",
  ),
  openGraph: {
    title: "Nexus",
    description: "Доступ к клиенту по подписке и промокодам.",
    images: [{ url: "/bg-fallback.png" }],
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ru"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground font-mono selection:bg-white selection:text-black">
        <video
          className="bg-video pointer-events-none fixed inset-0 h-full w-full object-cover"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
        >
          <source src="/fon.mp4" type="video/mp4" />
        </video>
        <div className="site-content flex min-h-full flex-col">
          <TopNav />
          {children}
        </div>
        <div className="pointer-events-none fixed bottom-3 left-4 z-30 text-xs text-white/75">
          @nexus
        </div>
      </body>
    </html>
  );
}
