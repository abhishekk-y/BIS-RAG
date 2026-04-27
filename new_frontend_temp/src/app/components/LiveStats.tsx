import { useState, useEffect } from "react";
import { Activity, Cpu, Database, Zap } from "lucide-react";

export function LiveStats() {
  const [stats, setStats] = useState({
    cpuLoad: 0,
    gpuLoad: 0,
    queryLatency: 0,
    cacheHitRate: 0,
    activeQueries: 0,
    vectorDbStatus: "online",
  });

  useEffect(() => {
    const updateStats = () => {
      setStats({
        cpuLoad: Math.floor(Math.random() * 30 + 15), // 15-45%
        gpuLoad: Math.floor(Math.random() * 40 + 30), // 30-70%
        queryLatency: Math.floor(Math.random() * 300 + 400), // 400-700ms
        cacheHitRate: Math.floor(Math.random() * 15 + 82), // 82-97%
        activeQueries: Math.floor(Math.random() * 5 + 2), // 2-7
        vectorDbStatus: Math.random() > 0.95 ? "degraded" : "online",
      });
    };

    updateStats();
    const interval = setInterval(updateStats, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex items-center gap-1">
        <span className="text-[#6a6a6a] text-[10px]">CPU</span>
        <div className="w-6 h-2 bg-[#1a1a1a] rounded-sm overflow-hidden flex items-end">
          <div
            className="w-full bg-gradient-to-t from-cyan-400 to-cyan-500 transition-all duration-500"
            style={{ height: `${stats.cpuLoad}%` }}
          />
        </div>
        <span className="text-white font-mono text-[10px] w-7">{stats.cpuLoad}%</span>
      </div>

      <div className="flex items-center gap-1">
        <span className="text-[#6a6a6a] text-[10px]">GPU</span>
        <div className="w-6 h-2 bg-[#1a1a1a] rounded-sm overflow-hidden flex items-end">
          <div
            className="w-full bg-gradient-to-t from-purple-400 to-purple-500 transition-all duration-500"
            style={{ height: `${stats.gpuLoad}%` }}
          />
        </div>
        <span className="text-white font-mono text-[10px] w-7">{stats.gpuLoad}%</span>
      </div>

      <div className="flex items-center gap-1">
        <span className="text-[#6a6a6a] text-[10px]">Lat</span>
        <span className="text-white font-mono text-[10px]">{stats.queryLatency}ms</span>
      </div>

      <div className="flex items-center gap-1">
        <span
          className={`w-1 h-1 rounded-full ${
            stats.vectorDbStatus === "online" ? "bg-green-400" : "bg-yellow-400"
          } animate-pulse`}
        />
        <span className={`text-[10px] ${stats.vectorDbStatus === "online" ? "text-green-400" : "text-yellow-400"}`}>
          {stats.vectorDbStatus.toUpperCase()}
        </span>
      </div>
    </div>
  );
}
