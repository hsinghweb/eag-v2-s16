
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Cpu, Search, Code, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const AgentNode = ({ data }) => {
    const { agent, status, label } = data;

    const getIcon = () => {
        switch (agent) {
            case 'PlannerAgent': return <Cpu className="text-blue-500" size={16} />;
            case 'RetrieverAgent': return <Search className="text-green-500" size={16} />;
            case 'BrowserAgent': return <Globe className="text-cyan-500" size={16} />;
            case 'CoderAgent': return <Code className="text-purple-500" size={16} />;
            case 'FormatterAgent': return <Layout className="text-indigo-500" size={16} />;
            default: return <Cpu className="text-slate-400" size={16} />;
        }
    };

    const getStatusStyle = () => {
        switch (status) {
            case 'running': return 'border-amber-400 bg-amber-50/50 shadow-[0_0_15px_rgba(251,191,36,0.1)]';
            case 'completed': return 'border-green-400 bg-green-50/20';
            case 'failed': return 'border-red-400 bg-red-50/20';
            default: return 'border-slate-200 bg-white';
        }
    };

    return (
        <div className={`px-4 py-3 rounded-xl border-2 transition-all min-w-[180px] ${getStatusStyle()}`}>
            <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-slate-300 border-none" />

            <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${status === 'running' ? 'bg-amber-100' :
                        status === 'completed' ? 'bg-green-100' :
                            'bg-slate-100'
                    }`}>
                    {status === 'running' ? <Loader2 size={16} className="text-amber-600 animate-spin" /> : getIcon()}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest leading-none mb-1">
                        {agent}
                    </div>
                    <div className="text-xs font-bold text-slate-700 truncate">
                        {label || agent}
                    </div>
                </div>

                {status === 'completed' && <CheckCircle2 size={14} className="text-green-500 shrink-0" />}
                {status === 'failed' && <AlertCircle size={14} className="text-red-500 shrink-0" />}
            </div>

            <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-slate-300 border-none" />
        </div>
    );
};

export default memo(AgentNode);

const Globe = ({ size, className }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>;
const Layout = ({ size, className }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>;
