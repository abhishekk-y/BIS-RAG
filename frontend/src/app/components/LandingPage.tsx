import { ArrowRight, Database, Search, Zap, Cpu } from "lucide-react";
import { Link } from "react-router";
import { useState, useEffect } from "react";
import { ParticleCanvas } from "./ParticleCanvas";
import { LiveStats } from "./LiveStats";

export default function LandingPage() {
  const [displayedText, setDisplayedText] = useState("");
  const fullText = "Instantly";

  useEffect(() => {
    let index = 0;
    let isDeleting = false;
    let timer: NodeJS.Timeout;

    const animate = () => {
      if (!isDeleting) {
        // Typing
        if (index <= fullText.length) {
          setDisplayedText(fullText.slice(0, index));
          index++;
          timer = setTimeout(animate, 150);
        } else {
          // Wait before starting to delete
          timer = setTimeout(() => {
            isDeleting = true;
            animate();
          }, 2000);
        }
      } else {
        // Deleting
        if (index > 0) {
          index--;
          setDisplayedText(fullText.slice(0, index));
          timer = setTimeout(animate, 100);
        } else {
          // Wait before starting to type again
          timer = setTimeout(() => {
            isDeleting = false;
            animate();
          }, 500);
        }
      }
    };

    animate();

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#0f0f0f] text-white relative overflow-hidden">
      {/* Particle Canvas Background */}
      <ParticleCanvas />

      {/* Unified Header with Stats */}
      <header className="relative z-10 bg-black border-b border-[#3a3a3a]">
        {/* Main Header Row */}
        <div className="flex justify-between items-center px-12 py-2">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-[#d85d20]" />
              <div className="w-2.5 h-2.5 rounded-full bg-[#ff8c42]" />
              <div className="w-2.5 h-2.5 rounded-full bg-[#e8d5c4]" />
            </div>
            <div className="text-base font-semibold tracking-wide text-white">BIS-RAG</div>
            <div className="px-2 py-0.5 bg-[#1a1a1a] border border-[#3a3a3a] rounded text-xs text-[#e8d5c4]">
              v0.1
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Database size={12} className="text-[#ff8c42]" />
              <div className="text-xs">
                <span className="text-white">ChromaDB</span>
                <span className="text-[#6a6a6a] ml-1">BGE-M3 Dense</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Search size={12} className="text-[#ff8c42]" />
              <div className="text-xs">
                <span className="text-white">BM25</span>
                <span className="text-[#6a6a6a] ml-1">Sparse Index</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Zap size={12} className="text-[#ff8c42]" />
              <div className="text-xs">
                <span className="text-white">CrossEncoder</span>
                <span className="text-[#6a6a6a] ml-1">MS-MARCO v2</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Cpu size={12} className="text-[#ff8c42]" />
              <div className="text-xs">
                <span className="text-white">Groq LPU</span>
                <span className="text-[#6a6a6a] ml-1">Llama 3.3 70B</span>
              </div>
            </div>

            {/* Divider */}
            <div className="h-4 w-px bg-[#3a3a3a]"></div>

            {/* Minimal Live Stats */}
            <LiveStats />

            {/* Divider */}
            <div className="h-4 w-px bg-[#3a3a3a]"></div>

            <Link
              to="/dashboard"
              className="text-sm text-[#e8d5c4] hover:text-[#ff8c42] transition-colors flex items-center gap-2"
            >
              Open Dashboard <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="relative z-10 flex flex-col justify-center min-h-[calc(100vh-90px)] px-12 max-w-7xl mx-auto">
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#3a3a3a] rounded-full text-xs text-[#ff8c42] font-medium">
            <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full animate-pulse" />
            AI-Powered Standard Discovery
          </div>
        </div>

        <h1 className="text-7xl font-bold mb-6 leading-[1.1] min-h-[300px]" style={{ fontFamily: "'VT323', monospace" }}>
          <span className="block text-white">Find BIS</span>
          <span className="block text-white">Standards</span>
          <span className="block text-[#ff8c42]">
            {displayedText}
            <span className="animate-pulse">|</span>
          </span>
        </h1>

        <p className="text-[#e8d5c4] text-lg mb-10 max-w-2xl leading-relaxed">
          Hybrid RAG engine searching <span className="text-[#ff8c42] font-semibold">548</span> Indian Standards across{" "}
          <span className="text-[#ff8c42] font-semibold">27</span> building material categories.
          Sub-second retrieval with <span className="text-white font-semibold">zero</span> hallucinations.
        </p>

        <div className="flex gap-4 mb-16">
          <Link
            to="/dashboard"
            className="px-8 py-3 bg-[#ff8c42] hover:bg-[#d85d20] text-black text-sm font-semibold rounded-lg transition-colors shadow-lg shadow-[#ff8c42]/20"
          >
            Get Started
          </Link>
          <button className="px-8 py-3 border-2 border-[#3a3a3a] hover:border-[#ff8c42] text-[#e8d5c4] hover:text-[#ff8c42] text-sm font-semibold rounded-lg transition-colors">
            View Demo
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-6 max-w-4xl">
          <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-xl p-5 hover:border-[#ff8c42]/30 transition-colors">
            <div className="text-xs text-[#e8d5c4] mb-1.5 font-medium">Standards</div>
            <div className="text-3xl font-bold text-[#ff8c42]" style={{ fontFamily: "'VT323', monospace" }}>548</div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-xl p-5 hover:border-[#ff8c42]/30 transition-colors">
            <div className="text-xs text-[#e8d5c4] mb-1.5 font-medium">Chunks</div>
            <div className="text-3xl font-bold text-[#ff8c42]" style={{ fontFamily: "'VT323', monospace" }}>2,638</div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-xl p-5 hover:border-[#ff8c42]/30 transition-colors">
            <div className="text-xs text-[#e8d5c4] mb-1.5 font-medium">Latency</div>
            <div className="text-3xl font-bold text-white" style={{ fontFamily: "'VT323', monospace" }}>&lt; 1s</div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-xl p-5 hover:border-[#ff8c42]/30 transition-colors">
            <div className="text-xs text-[#e8d5c4] mb-1.5 font-medium">Hallucination</div>
            <div className="text-3xl font-bold text-white" style={{ fontFamily: "'VT323', monospace" }}>Zero</div>
          </div>
        </div>
      </main>
    </div>
  );
}
