"use client";

import { useEffect, useState } from "react";

export default function StatusIndicator() {
  const [isOnline, setIsOnline] = useState(true);
  const [ping, setPing] = useState<number | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const start = Date.now();
        const response = await fetch("/api/health", { method: "HEAD" });
        const end = Date.now();

        setIsOnline(response.ok);
        setPing(end - start);
      } catch {
        setIsOnline(false);
        setPing(null);
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm text-white/60">
      <div className="flex items-center gap-1.5">
        <div
          className={`h-2 w-2 rounded-full ${
            isOnline ? "bg-green-500 animate-pulse" : "bg-red-500"
          }`}
        />
        <span>status: {isOnline ? "online" : "offline"}</span>
      </div>
      {ping !== null && (
        <div className="hidden sm:block">
          <span>ping: {ping}ms</span>
        </div>
      )}
      <div className="hidden sm:block">
        <span>delivery: instant</span>
      </div>
    </div>
  );
}
