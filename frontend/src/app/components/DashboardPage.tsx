import { Search, Home, Send, Database, Zap, Cpu } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { Link } from "react-router";
import { LiveStats } from "./LiveStats";
import ReactMarkdown from "react-markdown";

export default function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string; standards?: any[]; isZeroResults?: boolean }>>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<any>(null);
  const [isPlainEnglish, setIsPlainEnglish] = useState(false);
  const [displayedText, setDisplayedText] = useState("");
  const [searchHistory, setSearchHistory] = useState<Array<{ query: string; timestamp: string }>>([
    { query: "Portland cement grades", timestamp: "2 min ago" },
    { query: "Steel reinforcement bars", timestamp: "5 min ago" },
    { query: "Concrete aggregates", timestamp: "12 min ago" },
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fullText = "What are you building?";

  // Typing animation effect with delete and rewrite
  useEffect(() => {
    if (messages.length === 0) {
      let index = 0;
      let isDeleting = false;
      let timer: NodeJS.Timeout;

      const animate = () => {
        if (!isDeleting) {
          // Typing
          if (index <= fullText.length) {
            setDisplayedText(fullText.slice(0, index));
            index++;
            timer = setTimeout(animate, 100);
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
            timer = setTimeout(animate, 50);
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
    }
  }, [messages.length]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSearching]);

  const examples = [
    {
      category: "Cement",
      title: "33 Grade Ordinary Portland Cement",
    },
    {
      category: "Aggregates",
      title: "Coarse and fine aggregates for concrete",
    },
    {
      category: "Pipes",
      title: "Precast concrete pipes for water mains",
    },
    {
      category: "Cement",
      title: "Portland slag cement manufacturing",
    },
    {
      category: "Roofing",
      title: "Asbestos cement sheets for roofing",
    },
    {
      category: "Blocks",
      title: "Lightweight concrete masonry blocks",
    },
  ];

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    // Add to search history
    setSearchHistory((prev) => [
      { query: searchQuery, timestamp: "Just now" },
      ...prev.slice(0, 4),
    ]);

    setMessages((prev) => [...prev, { role: "user", content: searchQuery }]);
    setIsSearching(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, is_plain_english: isPlainEnglish }),
      });
      if (!res.ok) throw new Error("API Error");
      const data = await res.json();
      
      const isEmpty = !data.standards || data.standards.length === 0;
      const fallbackText = "No matching BIS standard was found in our indexed database for this specific query. Due to our strict anti-hallucination protocols, we will not generate an unverified IS Code. Please verify your material description or consult the full BIS portal.";
      
      setMessages((prev) => [
        ...prev, 
        { 
          role: "assistant", 
          content: isEmpty ? fallbackText : data.answer, 
          standards: data.standards,
          isZeroResults: isEmpty
        }
      ]);
      
      if (!isEmpty) {
        setSelectedEvidence(data.standards[0]);
      } else {
        setSelectedEvidence(null);
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error connecting to the backend server. Make sure `server.py` is running on port 8000." }]);
    } finally {
      setIsSearching(false);
      setSearchQuery("");
    }
  };

  const handleExampleClick = (example: { category: string; title: string }) => {
    setSearchQuery(example.title);
  };

  return (
    <div className="h-screen bg-[#0f0f0f] text-white flex flex-col overflow-hidden relative">
      {/* Unified Header with Stats */}
      <header className="relative z-10 bg-black border-b border-[#3a3a3a]">
        {/* Main Header Row with Tech Stack and Stats */}
        <div className="flex items-center justify-between px-12 py-2">
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
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* LEFT SIDEBAR - Slim */}
        <aside className="w-60 flex-shrink-0 border-r border-[#3a3a3a] bg-[#1a1a1a] p-6 flex flex-col relative z-10">
          <div className="text-xs text-[#e8d5c4] mb-6 font-medium">AI Standard Discovery Engine</div>

          <nav className="space-y-2">
            <Link to="/" className="w-full flex items-center gap-3 px-3 py-2.5 text-[#e8d5c4] hover:bg-[#0f0f0f] hover:text-white transition-colors text-sm rounded-lg">
              <Home size={16} />
              <span>Home</span>
            </Link>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 bg-[#ff8c42] text-black text-sm rounded-lg shadow-sm font-medium">
              <Search size={16} />
              <span>Search</span>
            </button>
          </nav>

          <div className="mt-auto">
            <div className="text-xs text-[#e8d5c4] mb-3 font-medium">Search History</div>
            <div className="space-y-2">
              {searchHistory.slice(0, 5).map((item, idx) => (
                <div
                  key={idx}
                  onClick={() => setSearchQuery(item.query)}
                  className="flex items-center gap-2 text-xs text-[#e8d5c4] hover:text-[#ff8c42] cursor-pointer transition-colors"
                >
                  <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full" />
                  <span className="truncate">{item.query}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* MIDDLE COLUMN - MASSIVE and Dominant */}
        <main className="flex-1 flex flex-col overflow-hidden relative z-10">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center px-12 overflow-y-auto">
            <div className="w-full max-w-5xl">
              <div className="text-center mb-12">
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#3a3a3a] rounded-full text-xs text-[#ff8c42] font-medium mb-8">
                  <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full animate-pulse" />
                  pipeline.search()
                </div>

                <h1 className="text-6xl font-bold mb-6 leading-tight min-h-[80px]" style={{ fontFamily: "'VT323', monospace" }}>
                  <span className="text-white">{displayedText}</span>
                  <span className="text-[#ff8c42] animate-pulse">|</span>
                </h1>

                <p className="text-[#e8d5c4] text-base mb-10 max-w-2xl mx-auto leading-relaxed">
                  Describe your MSE product or material. We'll find the exact BIS standards you need.
                </p>

                <div className="relative max-w-3xl mx-auto mb-3">
                  <input
                    type="text"
                    placeholder="Describe your product or paste a compliance question..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    className="w-full px-5 py-4 bg-[#1a1a1a] border-2 border-[#3a3a3a] rounded-xl text-white text-sm placeholder-[#6a6a6a] focus:outline-none focus:border-[#ff8c42] transition-colors"
                  />
                  <button
                    onClick={handleSearch}
                    className="absolute right-2 top-1/2 -translate-y-1/2 px-5 py-2 bg-[#ff8c42] hover:bg-[#d85d20] text-black text-sm rounded-lg transition-colors flex items-center gap-2 font-medium"
                  >
                    <Search size={16} />
                  </button>
                </div>

                <div className="text-xs text-[#e8d5c4] mt-3">↵ Enter to search</div>
              </div>

              {/* Recent Searches */}
              {searchHistory.length > 0 && (
                <div className="mb-8">
                  <div className="text-xs text-[#6a6a6a] mb-3 font-medium">Recents</div>
                  <div className="space-y-1">
                    {searchHistory.slice(0, 5).map((item, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSearchQuery(item.query)}
                        className="w-full text-left px-0 py-1 text-sm text-[#e8d5c4] hover:text-white transition-colors"
                      >
                        {item.query}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mb-8">
                <div className="text-xs text-[#ff8c42] mb-4 font-semibold">Try an example</div>

                <div className="grid grid-cols-3 gap-4">
                  {examples.map((example, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleExampleClick(example)}
                      className="p-4 bg-[#1a1a1a] border-2 border-[#3a3a3a] rounded-xl text-left hover:border-[#ff8c42] transition-all group"
                    >
                      <div className="text-xs text-[#ff8c42] mb-2 font-semibold">{example.category}</div>
                      <div className="text-sm text-[#e8d5c4] group-hover:text-white transition-colors leading-relaxed">
                        {example.title}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto px-12 py-8">
              <div className="w-full max-w-5xl mx-auto flex justify-between items-center mb-8">
                <div className="text-xs text-[#e8d5c4] font-medium">Chat Session</div>
                {/* MSME Mode Toggle */}
                <div className="flex items-center bg-[#1a1a1a] p-1 rounded-lg border border-[#3a3a3a]">
                  <button 
                    onClick={() => setIsPlainEnglish(false)}
                    className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${!isPlainEnglish ? 'bg-[#ff8c42] text-black shadow-sm' : 'text-[#6a6a6a] hover:text-[#e8d5c4]'}`}
                  >
                    Engineering Mode
                  </button>
                  <button 
                    onClick={() => setIsPlainEnglish(true)}
                    className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${isPlainEnglish ? 'bg-[#ff8c42] text-black shadow-sm' : 'text-[#6a6a6a] hover:text-[#e8d5c4]'}`}
                  >
                    Plain English Mode
                  </button>
                </div>
              </div>
              
              <div className="w-full max-w-5xl mx-auto space-y-6">
                {messages.map((message, idx) => (
                  <div key={idx} className={message.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className={`max-w-3xl p-4 rounded-xl ${
                        message.role === "user"
                          ? "bg-[#ff8c42] text-black"
                          : "bg-[#1a1a1a] border-2 border-[#3a3a3a] text-[#e8d5c4]"
                      }`}
                    >
                      <div className={`text-xs mb-2 font-semibold ${message.role === "user" ? "text-black/70" : "text-[#ff8c42]"}`}>
                        {message.role === "user" ? "You" : "BIS-RAG"}
                      </div>
                      <div className="text-sm leading-relaxed markdown-content break-words whitespace-normal w-full overflow-hidden">
                        {message.isZeroResults ? (
                          <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg text-red-200">
                            <div className="flex items-center gap-2 font-bold mb-2 text-red-400 uppercase tracking-wider text-xs">
                              <Zap size={14} />
                              Compliance Safety Alert
                            </div>
                            {message.content}
                          </div>
                        ) : message.role === "assistant" ? (
                          <ReactMarkdown
                            components={{
                              p: ({ node, ...props }) => <p className="mb-4 last:mb-0" {...props} />,
                              strong: ({ node, ...props }) => <strong className="text-white font-semibold" {...props} />,
                              ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4 space-y-1" {...props} />,
                              li: ({ node, ...props }) => <li {...props} />,
                            }}
                          >
                            {message.content.replace(/([^\n])\n([ \t]*[\*\-] )/g, "$1\n\n$2")}
                          </ReactMarkdown>
                        ) : (
                          <span className="whitespace-pre-wrap">{message.content}</span>
                        )}
                      </div>
                      
                      {/* Citation Pills */}
                      {message.role === "assistant" && message.standards && message.standards.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-[#3a3a3a]">
                          {message.standards.map((std: any, i: number) => (
                            <button
                              key={i}
                              onClick={() => setSelectedEvidence(std)}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                                selectedEvidence?.code === std.code
                                  ? "bg-[#ff8c42] text-black border-[#ff8c42] shadow-[0_0_10px_rgba(255,140,66,0.3)]"
                                  : "bg-[#0f0f0f] text-[#e8d5c4] border-[#3a3a3a] hover:border-[#ff8c42]"
                              }`}
                            >
                              {std.code}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isSearching && (
                  <div className="flex justify-start">
                    <div className="p-4 bg-[#1a1a1a] border-2 border-[#3a3a3a] rounded-xl">
                      <div className="text-xs mb-2 font-semibold text-[#ff8c42]">BIS-RAG</div>
                      <div className="text-sm text-[#e8d5c4] flex items-center gap-2">
                        <div className="flex gap-1">
                          <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="w-1.5 h-1.5 bg-[#ff8c42] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                        Searching standards...
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="border-t-2 border-[#3a3a3a] bg-[#1a1a1a] p-6">
              <div className="max-w-5xl mx-auto">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Ask a follow-up question..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    className="w-full px-5 py-4 bg-[#0f0f0f] border-2 border-[#3a3a3a] rounded-xl text-white text-sm placeholder-[#6a6a6a] focus:outline-none focus:border-[#ff8c42] transition-colors pr-12"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={isSearching}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-[#ff8c42] hover:text-[#d85d20] transition-colors disabled:opacity-50"
                  >
                    <Send size={18} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        </main>

        {/* RIGHT PANEL - Compact */}
        {/* RIGHT PANEL - Forensic Audit Trail */}
        <aside className="w-[368px] flex-shrink-0 border-l border-[#3a3a3a] bg-[#1a1a1a] p-6 overflow-y-auto relative z-10 flex flex-col gap-6">
          
          {/* Header & Match Confidence */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#e8d5c4] font-semibold uppercase tracking-wider">Forensic Context</span>
            {selectedEvidence && (
              <span className="text-xs text-[#00e676] flex items-center gap-1.5 font-medium px-2 py-1 bg-[#00e676]/10 border border-[#00e676]/20 rounded-full">
                <span className="w-1.5 h-1.5 bg-[#00e676] rounded-full animate-pulse" />
                {selectedEvidence.confidence_score || 98}% Match Confidence
              </span>
            )}
          </div>

          {selectedEvidence ? (
            <div className="flex flex-col gap-5">
              {/* Context Details */}
              <div className="p-4 bg-[#0f0f0f] border border-[#3a3a3a] rounded-xl flex flex-col gap-3">
                <div className="text-2xl font-bold text-white mb-1" style={{ fontFamily: "'VT323', monospace" }}>{selectedEvidence.code}</div>
                
                <div>
                  <div className="text-[10px] text-[#ff8c42] font-bold uppercase tracking-wider mb-1">Standard Title</div>
                  <div className="text-sm text-[#e8d5c4] leading-snug">{selectedEvidence.title || "Standard Documentation"}</div>
                </div>
                
                <div className="mt-2">
                  <div className="text-[10px] text-[#ff8c42] font-bold uppercase tracking-wider mb-2">
                    Extracted from Source (Page {selectedEvidence.page_number})
                  </div>
                  <div className="text-xs text-[#a0a0a0] leading-relaxed pl-3 border-l-2 border-[#ff8c42] bg-[#1a1a1a] p-3 rounded-r-lg whitespace-pre-wrap font-mono">
                    {selectedEvidence.evidence_snippet}
                  </div>
                </div>
                
                {selectedEvidence.rationale && (
                  <div className="mt-2">
                    <div className="text-[10px] text-[#ff8c42] font-bold uppercase tracking-wider mb-1">LLM Rationale</div>
                    <div className="text-xs text-[#e8d5c4] italic">"{selectedEvidence.rationale}"</div>
                  </div>
                )}
                
                {/* Export Audit Button */}
                <button
                  onClick={() => {
                    const text = `BIS-RAG Pro Forensic Audit\n\nStandard: ${selectedEvidence.code}\nTitle: ${selectedEvidence.title}\n\nExtracted Evidence:\n${selectedEvidence.evidence_snippet}\n\nRationale:\n${selectedEvidence.rationale || ""}`;
                    navigator.clipboard.writeText(text);
                    alert("Audit report copied to clipboard!");
                  }}
                  className="w-full mt-2 py-2 bg-[#1a1a1a] hover:bg-[#3a3a3a] border border-[#3a3a3a] rounded-lg text-xs font-semibold text-white transition-colors"
                >
                  Copy Report to Clipboard
                </button>
              </div>
              
              {/* The "One More" UI Flex - Estimated Time Saved */}
              <div className="p-5 bg-[#ff8c42]/10 border border-[#ff8c42]/30 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-20"><Zap size={40} /></div>
                <div className="text-xs font-bold text-[#ff8c42] uppercase tracking-wider">Business Impact</div>
                <div className="text-sm font-medium text-white mt-2">Estimated Time Saved:</div>
                <div className="text-4xl font-bold text-white mt-1 shadow-sm" style={{ fontFamily: "'VT323', monospace" }}>14 hours</div>
                <div className="text-xs text-[#e8d5c4] mt-2 opacity-80">of manual reading & document searching bypassed via Agentic RAG.</div>
              </div>
            </div>
          ) : (
            <div className="p-5 bg-[#0f0f0f] border border-[#3a3a3a] rounded-xl text-sm text-[#e8d5c4] leading-relaxed text-center flex flex-col items-center gap-3">
              <Search size={24} className="text-[#3a3a3a]" />
              No standard selected. Ask a question and click a citation pill to view the full forensic audit trail.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
