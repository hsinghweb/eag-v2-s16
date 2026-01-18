
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';
import {
  Play,
  Activity,
  Database,
  Settings,
  Cpu,
  MessageSquare,
  Terminal,
  Clock,
  Send,
  Loader2,
  Trash2,
  DollarSign,
  FileText
} from 'lucide-react';


import AgentNode from './components/AgentNode';

const nodeTypes = {
  agent: AgentNode,
};

const SamyakAgentUI = () => {
  const [activeTab, setActiveTab] = useState('runs');
  const [status, setStatus] = useState('idle');
  const [logs, setLogs] = useState([]);
  const [input, setInput] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const API_BASE = "http://localhost:8000";
  const WS_URL = "ws://localhost:8000/ws/events";


  // Initial Load
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/api/sessions`);
      setSessions(resp.data);
      if (resp.data.length > 0 && !currentSessionId) {
        handleSwitchSession(resp.data[0].id);
      } else if (resp.data.length === 0) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  };

  const handleSwitchSession = async (sid) => {
    try {
      const resp = await axios.get(`${API_BASE}/api/sessions/${sid}`);
      const session = resp.data;
      setCurrentSessionId(sid);
      setMessages(session.messages || []);
      if (session.graph_data) {
        updateGraph(session.graph_data);
      } else {
        setNodes([]);
        setEdges([]);
      }
      setLogs([]); // Clear logs for new session
      setSelectedNode(null);
    } catch (err) {
      console.error("Failed to switch session:", err);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setNodes([]);
    setEdges([]);
    setLogs([]);
    setSelectedNode(null);
    setActiveTab('runs');
  };

  const handleDeleteSession = async (e, sid) => {
    e.stopPropagation();
    try {
      await axios.delete(`${API_BASE}/api/sessions/${sid}`);
      if (currentSessionId === sid) {
        handleNewChat();
      }
      loadSessions();
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  // WebSocket Connection
  useEffect(() => {
    let ws = new WebSocket(WS_URL);

    ws.onopen = () => console.log("Connected to SamyakAgent WebSocket");

    ws.onmessage = (event) => {
      const { type, data } = JSON.parse(event.data);

      // Filter events by current session if relevant
      if (data.session_id && currentSessionId && data.session_id !== currentSessionId) {
        // Optional: If it's a finish event for another session, we might want to update the sessions list
        if (type === 'finish') loadSessions();
        return;
      }

      switch (type) {
        case 'status':
          setStatus(data.status);
          if (data.session_id && !currentSessionId) {
            setCurrentSessionId(data.session_id);
            loadSessions();
          }
          break;
        case 'log':
          setLogs(prev => [...prev, data]);
          break;
        case 'graph_update':
          updateGraph(data);
          break;
        case 'finish':
          loadSessions();
          if (data.messages) setMessages(data.messages);
          if (!data.success) {
            setLogs(prev => [...prev, { title: "Error", payload: data.error, symbol: "❌" }]);
          }
          break;
        case 'error':
          setLogs(prev => [...prev, { title: "System Error", payload: data.message, symbol: "🚫" }]);
          break;
      }
    };

    ws.onclose = () => {
      console.log("Disconnected. Retrying in 3s...");
      setTimeout(() => {
        // Simple retry logic
      }, 3000);
    };

    return () => ws.close();
  }, []);

  const updateGraph = useCallback((graphData) => {
    if (!graphData || !graphData.nodes) return;

    const newNodes = graphData.nodes.map((node, index) => ({
      id: node.id,
      type: 'agent',
      data: {
        agent: node.agent,
        status: node.status,
        label: node.id,
        description: node.description,
        output: node.output,
        reads: node.reads,
        writes: node.writes,
        cost: node.cost,
        duration: node.execution_time
      },
      position: node.position || { x: index * 250, y: (index % 3) * 150 },
    }));

    const newEdges = graphData.links.map(link => ({
      id: `e-${link.source}-${link.target}`,
      source: link.source,
      target: link.target,
      animated: true,
      style: { stroke: '#94a3b8', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#94a3b8',
      },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  }, [setNodes, setEdges]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || status === 'running') return;

    setLogs([]);
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);

    // Optimistically add user message if we want, but backend does it too
    setMessages(prev => [...prev, { role: 'user', content: input, timestamp: new Date().toISOString() }]);

    try {
      const resp = await axios.post(`${API_BASE}/api/chat`, {
        message: input,
        session_id: currentSessionId
      });
      if (resp.data.session_id && !currentSessionId) {
        setCurrentSessionId(resp.data.session_id);
        loadSessions();
      }
      setInput('');
    } catch (err) {
      console.error("Failed to start agent:", err);
    }
  };


  const currentDetails = useMemo(() => {
    if (selectedNode) return selectedNode.data;
    // Fallback to the latest active/running node if none selected?
    return nodes.find(n => n.data.status === 'running')?.data || nodes[nodes.length - 1]?.data;
  }, [selectedNode, nodes]);

  return (
    <div className="flex h-screen w-full bg-[#f8f9fc] text-slate-800 overflow-hidden font-sans">
      {/* Mini Sidebar */}
      <aside className="w-16 border-r border-slate-200 bg-white flex flex-col items-center py-4 gap-6 shrink-0 z-20">
        <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white mb-2 shadow-lg shadow-blue-200">
          <Cpu size={22} fill="white" />
        </div>

        <nav className="flex flex-col gap-4 flex-1">
          <SidebarIcon icon={<Activity size={20} />} active={activeTab === 'runs'} onClick={() => setActiveTab('runs')} label="Runs" />
          <SidebarIcon icon={<Database size={20} />} active={activeTab === 'rag'} onClick={() => setActiveTab('rag')} label="RAG" />
          <SidebarIcon icon={<LayoutIcon size={20} />} active={activeTab === 'mcp'} onClick={() => setActiveTab('mcp')} label="MCP" />
          <SidebarIcon icon={<FileText size={20} />} active={activeTab === 'explorer'} onClick={() => setActiveTab('explorer')} label="Files" />
        </nav>

        <div className="mt-auto flex flex-col gap-4">
          <SidebarIcon icon={<Plus size={20} />} label="New Chat" onClick={handleNewChat} />
          <SidebarIcon icon={<Settings size={20} />} label="Settings" />
        </div>
      </aside>

      {/* Sessions Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0 overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-xs font-extrabold text-slate-400 tracking-widest uppercase">Chat History</h2>
          <button onClick={handleNewChat} className="p-1 hover:bg-slate-50 rounded text-blue-600 transition-colors">
            <Plus size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1 custom-scrollbar">
          {sessions.map(s => (
            <div
              key={s.id}
              onClick={() => handleSwitchSession(s.id)}
              className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all ${currentSessionId === s.id ? 'bg-blue-50 text-blue-600 shadow-sm border border-blue-100' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700 border border-transparent'
                }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <MessageSquare size={16} className={currentSessionId === s.id ? 'text-blue-500' : 'text-slate-400'} />
                <span className="text-xs font-bold truncate pr-2">{s.title || "Untitled Chat"}</span>
              </div>
              <button
                onClick={(e) => handleDeleteSession(e, s.id)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 hover:text-red-500 rounded transition-all"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className="p-8 text-center text-slate-400 italic text-[10px]">
              No sessions found
            </div>
          )}
        </div>
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-slate-500 font-bold text-xs uppercase">
              H
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] font-extrabold truncate uppercase">Himanshu</div>
              <div className="text-[9px] text-slate-400 truncate tracking-tighter">Pro Developer</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Header */}
        <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6 shrink-0 z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <span className="text-blue-600">Samyak</span>Agent
            </h1>
            <div className="h-4 w-[1px] bg-slate-200"></div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="font-medium text-slate-700 uppercase text-[10px] tracking-widest">Execution Mode</span>
              <span className="text-blue-500 font-bold text-[10px]">NETWORKX v2</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className={`px-3 py-1.5 rounded-full text-[10px] font-bold flex items-center gap-2 transition-colors ${status === 'running' ? 'bg-amber-50 text-amber-600 border border-amber-100' : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${status === 'running' ? 'bg-amber-400 animate-pulse' : 'bg-slate-400'}`}></div>
              {status.toUpperCase()}
            </div>
            <div className="h-4 w-[1px] bg-slate-200"></div>
            <div className="flex items-center gap-2 text-xs font-bold text-slate-600">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
              OLLAMA: READY
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex overflow-hidden">
          {/* Central Workspace */}
          <div className="flex-1 relative bg-[#fcfdfe] overflow-hidden flex flex-col">

            {/* React Flow Graph */}
            <div className={`flex-1 transition-all duration-500 ${activeTab === 'runs' ? 'visible relative' : 'hidden md:block absolute inset-0 opacity-0 pointer-events-none'}`}>
              {nodes.length > 0 ? (
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  onNodeClick={(e, node) => setSelectedNode(node)}
                  fitView
                >
                  <Background color="#f1f5f9" gap={20} />
                  <Controls className="!bg-white !border-slate-200 !shadow-sm" />
                </ReactFlow>
              ) : (
                <div className="flex-1 flex items-center justify-center h-full">
                  <div className="text-center animate-in fade-in zoom-in duration-500">
                    <div className="w-20 h-20 bg-slate-50 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-slate-100 shadow-sm">
                      <Cpu size={40} className="text-slate-300" />
                    </div>
                    <p className="text-slate-500 font-bold text-lg tracking-tight">System Idle</p>
                    <p className="text-slate-400 text-sm mt-1">Enter a query below to generate a new execution plan</p>
                  </div>
                </div>
              )}
            </div>

            {/* Chat History View (Always visible if messages exist) */}
            <div className={`flex-1 flex flex-col overflow-hidden transition-all duration-500 ${activeTab === 'chat' ? 'visible relative' : 'absolute bottom-24 right-8 w-80 h-96 bg-white border border-slate-200 rounded-2xl shadow-2xl z-20 pointer-events-auto overflow-hidden opacity-100'}`}>
              <div className="p-4 border-b border-slate-100 bg-white/80 backdrop-blur shrink-0 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare size={14} className="text-blue-500" />
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-slate-500">Conversation</span>
                </div>
                <button onClick={() => setActiveTab(activeTab === 'chat' ? 'runs' : 'chat')} className="p-1 hover:bg-slate-100 rounded">
                  {activeTab === 'chat' ? <LayoutIcon size={14} /> : <Activity size={14} />}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 custom-scrollbar">
                {messages.map((m, i) => (
                  <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`max-w-[85%] px-4 py-3 rounded-2xl text-xs font-medium leading-relaxed shadow-sm prose-slim ${m.role === 'user'
                        ? 'bg-blue-600 text-white rounded-tr-none'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-tl-none'
                        }`}
                      dangerouslySetInnerHTML={{
                        __html: typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2)
                      }}
                    />
                    <span className="text-[9px] text-slate-400 mt-1 font-bold">
                      {m.role?.toUpperCase()} • {m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                ))}

                {status === 'running' && (
                  <div className="flex flex-col items-start translate-y-1">
                    <div className="bg-slate-50 border border-slate-100 px-4 py-3 rounded-2xl rounded-tl-none flex items-center gap-2 shadow-sm">
                      <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce delay-0"></div>
                        <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce delay-150"></div>
                        <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce delay-300"></div>
                      </div>
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">Analyzing...</span>
                    </div>
                  </div>
                )}
                {messages.length === 0 && (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-300 py-12">
                    <MessageSquare size={32} className="mb-2 opacity-50" />
                    <p className="text-[10px] font-bold uppercase tracking-widest">No messages yet</p>
                  </div>
                )}
              </div>
            </div>


            {/* Floating Chat Input */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4 z-10">
              <form
                onSubmit={handleSubmit}
                className="bg-white p-1.5 pr-2 rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-200 flex items-center gap-2 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-50 transition-all"
              >
                <div className="w-10 h-10 flex items-center justify-center text-slate-400">
                  <MessageSquare size={20} />
                </div>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="What would you like the agent to do?"
                  className="flex-1 bg-transparent border-none outline-none text-sm font-medium placeholder:text-slate-400 h-10"
                  disabled={status === 'running'}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || status === 'running'}
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${!input.trim() || status === 'running'
                    ? 'bg-slate-100 text-slate-300'
                    : 'bg-blue-600 text-white shadow-lg shadow-blue-200 hover:scale-105 active:scale-95'
                    }`}
                >
                  {status === 'running' ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                </button>
              </form>
            </div>
          </div>

          {/* Right Panel (Execution Details) */}
          <aside className="w-96 border-l border-slate-200 bg-white flex flex-col shrink-0 overflow-hidden shadow-[-4px_0_15px_rgba(0,0,0,0.02)] z-10">
            <div className="h-12 border-b border-slate-100 flex items-center px-4 justify-between shrink-0 bg-slate-50/50">
              <div className="flex gap-4 h-full">
                <PanelTab label="OVERVIEW" active />
                <PanelTab label="CODE" />
                <PanelTab label="WEB" />
                <PanelTab label="STATS" />
              </div>
              <button className="text-slate-400 hover:text-slate-600 transition-colors"><Trash2 size={16} onClick={() => setLogs([])} /></button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-8 custom-scrollbar">
              {currentDetails ? (
                <>
                  <section>
                    <DetailLabel icon={<MessageSquare size={12} />} label="AGENT TASK" />
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs leading-relaxed text-slate-700 font-medium">
                      {currentDetails.description || "No task description available."}
                    </div>
                  </section>

                  <div className="grid grid-cols-2 gap-4">
                    <section>
                      <DetailLabel label="INPUTS" />
                      <div className="flex gap-1.5 flex-wrap">
                        {currentDetails.reads?.map(r => (
                          <span key={r} className="bg-blue-50 text-blue-600 text-[9px] px-2 py-1 rounded font-bold border border-blue-100">{r}</span>
                        )) || <span className="text-[10px] text-slate-400 italic">None</span>}
                      </div>
                    </section>
                    <section>
                      <DetailLabel label="OUTPUTS" />
                      <div className="flex gap-1.5 flex-wrap">
                        {currentDetails.writes?.map(w => (
                          <span key={w} className="bg-green-50 text-green-600 text-[9px] px-2 py-1 rounded font-bold border border-green-100">{w}</span>
                        )) || <span className="text-[10px] text-slate-400 italic">None</span>}
                      </div>
                    </section>
                  </div>

                  <section className="flex items-center justify-between py-4 border-y border-slate-100">
                    <div className="flex items-center gap-2 text-slate-400 text-xs font-bold">
                      <Clock size={14} className="text-slate-300" /> DURATION <span className="text-slate-900 ml-1">{currentDetails.duration?.toFixed(2) || "0.00"}s</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-400 text-xs font-bold">
                      <DollarSign size={14} className="text-slate-300" /> COST <span className="text-green-600 ml-1 font-mono">${currentDetails.cost?.toFixed(6) || "0.000000"}</span>
                    </div>
                  </section>
                </>
              ) : (
                <section className="text-center py-12">
                  <Activity size={32} className="mx-auto text-slate-200 mb-4" />
                  <p className="text-slate-400 text-xs font-bold">SELECT A NODE TO VIEW DETAILS</p>
                </section>
              )}

              <section className="flex-1 min-h-0 flex flex-col">
                <DetailLabel icon={<Terminal size={12} />} label="LIVE EXECUTION LOGS" />
                <div className="flex-1 bg-[#0f172a] rounded-xl p-4 font-mono text-[11px] text-slate-400 overflow-y-auto shadow-inner border border-slate-800">
                  {logs.length > 0 ? (
                    logs.map((log, i) => (
                      <div key={i} className="mb-2 animate-in slide-in-from-left-2 duration-300">
                        <span className="text-slate-600 mr-2">[{new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}]</span>
                        <span className="text-blue-400 font-bold mr-2">{log.symbol}</span>
                        <span className="text-slate-200">{log.title}</span>
                        {log.payload && (
                          <pre className="mt-1 text-slate-500 pl-4 border-l border-slate-800 overflow-x-auto">
                            {typeof log.payload === 'object' ? JSON.stringify(log.payload, null, 2) : log.payload}
                          </pre>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-600 italic">Waiting for execution logs...</div>
                  )}
                </div>
              </section>
            </div>
          </aside>
        </main>
      </div>
    </div>
  );
};

const SidebarIcon = ({ icon, active = false, onClick = null, label = "" }) => (
  <button
    onClick={onClick}
    className={`p-3 rounded-xl transition-all relative group ${active
      ? 'bg-blue-50 text-blue-600'
      : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'
      }`}
    title={label}
  >
    {icon}
    {active && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-600 rounded-r-full"></div>}
    {!active && (
      <div className="absolute left-14 bg-slate-800 text-white text-[10px] font-bold px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
        {label}
      </div>
    )}
  </button>
);

const PanelTab = ({ label, active = false }) => (
  <button className={`text-[10px] font-extrabold tracking-widest h-full px-1 border-b-2 transition-all ${active ? 'text-blue-600 border-blue-600' : 'text-slate-400 border-transparent hover:text-slate-500'
    }`}>
    {label}
  </button>
);

const DetailLabel = ({ icon, label }) => (
  <div className="flex items-center gap-2 text-[10px] font-extrabold text-slate-400 tracking-[0.15em] mb-3 uppercase">
    {icon} {label}
  </div>
);

const Plus = ({ size }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>;
const LayoutIcon = ({ size }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>;


export default SamyakAgentUI;
