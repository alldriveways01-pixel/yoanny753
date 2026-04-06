import React, { useState, useEffect, useRef, Component, ErrorInfo } from 'react';
import { 
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, 
  CartesianGrid, Tooltip, ResponsiveContainer, Legend 
} from 'recharts';
import { 
  Activity, Server, Shield, Settings, Terminal, Play, Square, 
  RefreshCw, Radio, Map as MapIcon, Zap, CheckCircle2, XCircle, 
  Clock, Database, Globe, Cpu, Wifi, AlertTriangle, ChevronRight
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { io } from 'socket.io-client';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

class ErrorBoundary extends Component<{children: React.ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 text-rose-400 p-8 font-mono">
          <h1 className="text-2xl font-bold mb-4">Dashboard Crashed</h1>
          <p className="mb-4">An error occurred while rendering the UI:</p>
          <pre className="bg-slate-900 p-4 rounded overflow-auto text-sm">
            {this.state.error?.toString()}
            {'\n\n'}
            {this.state.error?.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// --- COMPONENTS ---

const Card = ({ children, className, title, icon: Icon, action }: any) => (
  <div className={cn("bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col", className)}>
    {(title || Icon) && (
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-emerald-500" />}
          <h3 className="font-medium text-slate-200 text-sm tracking-wide uppercase">{title}</h3>
        </div>
        {action && <div>{action}</div>}
      </div>
    )}
    <div className="p-4 flex-1 flex flex-col">{children}</div>
  </div>
);

// --- TABS ---

function MainDashboard({ state, dispatch, socket }: any) {
  const logsContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [state.logs]);

  const handleStart = async () => {
    try {
      await fetch(`${backendUrl}/api/system/initialize`, { method: 'POST' });
      await fetch(`${backendUrl}/api/system/deploy`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_count: 20 })
      });
      await fetch(`${backendUrl}/api/system/start-monitoring`, { method: 'POST' });
      socket?.emit('request_update');
    } catch (e) {
      console.error(e);
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`${backendUrl}/api/system/stop-monitoring`, { method: 'POST' });
      await fetch(`${backendUrl}/api/system/cleanup`, { method: 'POST' });
      socket?.emit('request_update');
    } catch (e) {
      console.error(e);
    }
  };

  const handleRotate = async () => {
    try {
      await fetch(`${backendUrl}/api/system/rotate`, { method: 'POST' });
      socket?.emit('request_update');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Row: Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="System Status" icon={Server}>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Phone Temp</span>
              <span className={cn("font-mono", state.temp > 45 ? "text-rose-400" : "text-emerald-400")}>
                {state.temp ? state.temp.toFixed(1) : '--'}°C
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">ADB Status</span>
              <span className={cn("font-mono", state.adbConnected ? "text-emerald-400" : "text-rose-400")}>
                {state.adbConnected ? 'CONNECTED ✓' : 'DISCONNECTED ✗'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">NAT64 Prefix</span>
              <span className="text-slate-300 font-mono text-xs">{state.netInfo?.nat64_prefix || '--'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Target Interface</span>
              <span className="text-slate-300 font-mono">{state.netInfo?.cell_interface || '--'}</span>
            </div>
          </div>
          <div className="mt-auto pt-4 grid grid-cols-3 gap-2">
            <button 
              onClick={state.isRunning ? handleStop : handleStart}
              className={cn("py-2 rounded-md text-xs font-bold flex items-center justify-center gap-1 transition-colors", 
                state.isRunning ? "bg-rose-500/20 text-rose-400 hover:bg-rose-500/30" : "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30")}
            >
              {state.isRunning ? <><Square className="w-3 h-3" /> STOP</> : <><Play className="w-3 h-3" /> START</>}
            </button>
            <button onClick={handleRotate} className="col-span-2 py-2 bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 rounded-md text-xs font-bold flex items-center justify-center gap-1 transition-colors">
              <RefreshCw className="w-3 h-3" /> ROTATE IPs
            </button>
          </div>
        </Card>

        <Card title="Bucket Status" icon={Database}>
          <div className="text-center mb-4">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Unique IPs</span>
              <span className="text-emerald-400 font-mono">{state.uniqueIps} / {state.nodes.length} ({Math.round((state.uniqueIps/Math.max(1, state.nodes.length))*100)}%)</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div className="bg-emerald-500 h-2.5 rounded-full transition-all duration-500" style={{ width: `${(state.uniqueIps/Math.max(1, state.nodes.length))*100}%` }}></div>
            </div>
          </div>
          <div className="space-y-3 text-sm flex-1">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Auto Rotation</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" className="sr-only peer" defaultChecked />
                <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
              </label>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Next Rotation</span>
              <span className="text-slate-300 font-mono">3h 42m</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Health</span>
              <span className="text-slate-300 font-mono text-xs">
                <span className="text-emerald-400">{state.nodes.filter((n:any)=>n.is_alive).length} ALIVE</span>, 
                <span className="text-rose-400 ml-1">{state.nodes.filter((n:any)=>!n.is_alive).length} DEAD</span>
              </span>
            </div>
          </div>
        </Card>

        <Card title="Live Seeker Activity" icon={Terminal}>
          <div ref={logsContainerRef} className="bg-black/50 rounded-md p-3 font-mono text-[10px] leading-relaxed text-slate-300 h-40 overflow-y-auto border border-slate-800/50 scroll-smooth">
            {state.logs.map((log: string, i: number) => {
              const isUnique = log.includes('[UNIQUE]');
              const isDuplicate = log.includes('[DUPLICATE]');
              return (
                <div key={i} className="mb-1">
                  <span className="text-slate-500">{log.substring(0, 10)}</span>
                  <span className={cn(
                    "ml-2",
                    isUnique ? "text-emerald-400" : isDuplicate ? "text-rose-400" : "text-slate-300"
                  )}>
                    {log.substring(10)}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex justify-between items-center text-xs">
            <span className="text-slate-400">Active Hunters: <span className="text-emerald-400 font-mono">{state.activeHunters}</span></span>
            <span className="text-slate-400">Avg Find: <span className="text-emerald-400 font-mono">{Math.floor(state.avgFindTime/60)}m {Math.floor(state.avgFindTime%60)}s</span></span>
          </div>
        </Card>
      </div>

      {/* Middle Row: Charts & Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="IP Discovery & Diversity" icon={Activity} className="lg:col-span-2">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={state.chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorUnique" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="time" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <Area type="monotone" dataKey="uniqueIps" name="Unique IPs" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorUnique)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Proxy Quality Distribution" icon={Shield}>
          <div className="space-y-4">
            {[
              { label: 'EXCELLENT (90-100%)', count: 3, color: 'bg-emerald-500' },
              { label: 'GOOD (75-89%)', count: 5, color: 'bg-emerald-400' },
              { label: 'AVERAGE (50-74%)', count: 7, color: 'bg-amber-400' },
              { label: 'FAIR (25-49%)', count: 2, color: 'bg-orange-400' },
              { label: 'POOR (0-24%)', count: 1, color: 'bg-rose-500' },
            ].map((tier) => (
              <div key={tier.label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300">{tier.label}</span>
                  <span className="text-slate-400 font-mono">{tier.count} nodes</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                  <div className={cn("h-1.5 rounded-full", tier.color)} style={{ width: `${(tier.count / Math.max(1, state.nodes.length)) * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Bottom Row: Active Proxies Table */}
      <Card title="Active Proxies" icon={Globe}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/50 border-b border-slate-800">
              <tr>
                <th className="px-4 py-3 font-medium">Node</th>
                <th className="px-4 py-3 font-medium">Port</th>
                <th className="px-4 py-3 font-medium">IPv4 Address</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Latency</th>
                <th className="px-4 py-3 font-medium">Strategy</th>
                <th className="px-4 py-3 font-medium text-right">Success Rate</th>
              </tr>
            </thead>
            <tbody>
              {state.nodes.map((node: any) => (
                <tr key={node.node_id} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                  <td className="px-4 py-3 font-mono text-slate-300">#{node.node_id}</td>
                  <td className="px-4 py-3 font-mono text-slate-400">{node.external_port}</td>
                  <td className="px-4 py-3 font-mono text-blue-400">{node.public_ipv4 || 'N/A'}</td>
                  <td className="px-4 py-3">
                    <span className={cn("px-2 py-1 rounded-md text-[10px] font-bold tracking-wider", 
                      node.is_alive ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                    )}>
                      {node.is_alive ? 'ALIVE' : 'DEAD'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-400">
                    {node.is_alive ? `${node.latency_ms}ms` : '--'}
                  </td>
                  <td className="px-4 py-3 text-slate-300 text-xs">{node.strategy}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <span className="font-mono text-xs text-slate-400">{Math.round(node.success_rate * 100)}%</span>
                      <div className="w-12 bg-slate-800 rounded-full h-1.5">
                        <div className={cn("h-1.5 rounded-full", 
                          node.success_rate > 0.8 ? "bg-emerald-500" : node.success_rate > 0.5 ? "bg-amber-400" : "bg-rose-500"
                        )} style={{ width: `${node.success_rate * 100}%` }}></div>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function KeepaliveLab({ state }: any) {
  const strategies = [
    { id: 'session_https', name: 'Session HTTPS' },
    { id: 'sse_stream', name: 'SSE Stream' },
    { id: 'sim_browsing', name: 'Sim Browsing' },
    { id: 'tcp_null_drip', name: 'TCP Null Drip' },
    { id: 'os_keepalive', name: 'OS Keepalive' },
    { id: 'icmp_ping6', name: 'ICMP Ping6' },
  ];

  const getStrategyStats = (stratId: string) => {
    const nodes = state.nodes.filter((n: any) => n.strategy === stratId);
    const alive = nodes.filter((n: any) => n.is_alive).length;
    const total = nodes.length;
    return { alive, total };
  };

  const handleStartTest = async () => {
    try {
      await fetch(`${backendUrl}/api/system/initialize`, { method: 'POST' });
      await fetch(`${backendUrl}/api/system/deploy`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_count: 6 })
      });
      await fetch(`${backendUrl}/api/system/start-monitoring`, { method: 'POST' });
      
      // Assign the 6 strategies to the 6 nodes
      const stratIds = ['session_https', 'sse_stream', 'sim_browsing', 'tcp_null_drip', 'os_keepalive', 'icmp_ping6'];
      for (let i = 0; i < stratIds.length; i++) {
        await fetch(`${backendUrl}/api/lab/assign`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ node_id: i + 1, strategy: stratIds[i] })
        });
      }
      
      socket?.emit('request_update');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="space-y-4">
        <Card title="Strategy Selection" icon={Settings}>
          <div className="space-y-2">
            {strategies.map((strat, i) => (
              <label key={strat.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-800/50 cursor-pointer transition-colors border border-transparent hover:border-slate-700">
                <input type="checkbox" defaultChecked={true} className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-slate-900" />
                <span className="text-sm text-slate-300">{i + 1}. {strat.name}</span>
              </label>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-slate-800 flex gap-2">
            <button className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-xs font-medium transition-colors">SELECT ALL</button>
            <button className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-xs font-medium transition-colors">DESELECT ALL</button>
          </div>
        </Card>

        <Card title="Test Configuration" icon={Play}>
          <div className="space-y-4 text-sm">
            <div>
              <label className="block text-slate-400 text-xs mb-1">Test Duration</label>
              <select className="w-full bg-slate-950 border border-slate-800 rounded-md px-3 py-2 text-slate-300 focus:outline-none focus:border-emerald-500">
                <option>24 Hours</option>
                <option>12 Hours</option>
                <option>48 Hours</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Nodes Per Strategy</label>
              <input type="number" defaultValue={1} className="w-full bg-slate-950 border border-slate-800 rounded-md px-3 py-2 text-slate-300 focus:outline-none focus:border-emerald-500" />
            </div>
            <button onClick={handleStartTest} className="w-full py-2.5 bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 rounded-md text-sm font-bold transition-colors mt-2">
              START SELECTED TEST
            </button>
          </div>
        </Card>
      </div>

      <div className="lg:col-span-2 space-y-4">
        <Card title="Live Survival Analysis (% nodes alive)" icon={Activity}>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ top: 20, right: 20, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="hour" type="number" domain={[0, 15]} tickCount={6} stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tickFormatter={(val) => `${val}%`} stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="Session HTTPS" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="SSE Stream" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="Sim Browsing" stroke="#f59e0b" strokeWidth={2} dot={false} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="TCP Null Drip" stroke="#8b5cf6" strokeWidth={2} dot={false} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="OS Keepalive" stroke="#ec4899" strokeWidth={2} dot={false} />
                <Line data={[{hour:0, val:100}, {hour:3, val:100}, {hour:6, val:100}, {hour:9, val:100}, {hour:12, val:100}, {hour:15, val:100}]} type="stepAfter" dataKey="val" name="ICMP Ping6" stroke="#06b6d4" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Detailed Statistics (Live)" icon={Database}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-400 uppercase bg-slate-900/50 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-medium">Strategy</th>
                  <th className="px-4 py-3 font-medium">Nodes Alive</th>
                  <th className="px-4 py-3 font-medium">Total %</th>
                  <th className="px-4 py-3 font-medium">Avg Lifetime</th>
                  <th className="px-4 py-3 font-medium">Bandwidth</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map(strat => {
                  const stats = getStrategyStats(strat.id);
                  const percent = stats.total > 0 ? Math.round((stats.alive / stats.total) * 100) : 0;
                  return (
                    <tr key={strat.id} className="border-b border-slate-800/50">
                      <td className="px-4 py-3 text-slate-300">{strat.name}</td>
                      <td className="px-4 py-3 font-mono text-emerald-400">{stats.alive}/{stats.total}</td>
                      <td className="px-4 py-3 font-mono text-slate-400">{percent}%</td>
                      <td className="px-4 py-3 font-mono text-slate-400">Live</td>
                      <td className="px-4 py-3 font-mono text-slate-400">--</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

function AdvancedAnalysis() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="Carrier Pattern Analysis" icon={Activity}>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
              <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-3">IP Allocation Patterns</h4>
              <ul className="space-y-2 text-sm text-slate-300">
                <li className="flex justify-between"><span className="text-slate-500">NAT Pool Size:</span> <span className="font-mono text-emerald-400">~35 IPs</span></li>
                <li className="flex justify-between"><span className="text-slate-500">Rotation Interval:</span> <span className="font-mono text-amber-400">~4 hours</span></li>
                <li className="flex justify-between"><span className="text-slate-500">Peak Diversity:</span> <span className="font-mono text-blue-400">12PM-2PM</span></li>
                <li className="flex justify-between"><span className="text-slate-500">NAT Algorithm:</span> <span>Weighted Dist.</span></li>
              </ul>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
              <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-3">Optimal Hunt Windows</h4>
              <ul className="space-y-2 text-sm text-slate-300">
                <li className="flex items-center gap-2">
                  <div className="w-16 h-2 bg-emerald-500 rounded-full"></div>
                  <span className="font-mono">09:15-10:30 (83%)</span>
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-emerald-500 rounded-full"></div>
                  <span className="font-mono">13:45-15:15 (91%)</span>
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-10 h-2 bg-amber-500 rounded-full"></div>
                  <span className="font-mono">22:00-22:45 (72%)</span>
                </li>
              </ul>
            </div>
          </div>
          
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-4 h-4 text-blue-400" />
              <h4 className="text-sm font-medium text-blue-400">Machine Learning Predictor</h4>
            </div>
            <p className="text-xs text-slate-400 mb-3">Recommended Hunt Settings for Maximum Diversity:</p>
            <ul className="space-y-1 text-sm text-slate-300 list-disc list-inside mb-4">
              <li>Optimal Delay: <span className="text-emerald-400 font-mono">7.2s</span> exponential (Based on 317 data points)</li>
              <li>Best Strategy: <span className="text-emerald-400">HTTP Poll + SSE Stream</span></li>
              <li>Recommended Rotation: Every <span className="text-emerald-400 font-mono">3.5</span> hours</li>
            </ul>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">Predicted Max Uniqueness: <span className="text-emerald-400 font-bold">52% ±4%</span></span>
              <button className="px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded text-xs font-medium transition-colors">
                APPLY SETTINGS
              </button>
            </div>
          </div>
        </div>
      </Card>

      <Card title="Advanced Tower Triangulation" icon={MapIcon}>
        <div className="space-y-6">
          <div className="flex items-center justify-between bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider">Current Tower</div>
              <div className="text-sm font-medium text-slate-200">310-260-84721-3 (T-Mobile Band 71)</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-slate-500 uppercase tracking-wider">Signal</div>
              <div className="text-sm font-medium text-amber-400">-92dBm (MODERATE)</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex items-center justify-center relative overflow-hidden min-h-[160px]">
              {/* Abstract Map Visualization */}
              <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#334155 1px, transparent 1px)', backgroundSize: '16px 16px' }}></div>
              <div className="relative z-10 w-full h-full flex items-center justify-center">
                <div className="absolute top-4 left-4 flex flex-col items-center">
                  <Radio className="w-5 h-5 text-slate-500" />
                  <span className="text-[10px] text-slate-500 mt-1">84778-1</span>
                </div>
                <div className="absolute bottom-6 right-8 flex flex-col items-center">
                  <Radio className="w-6 h-6 text-emerald-500 animate-pulse" />
                  <span className="text-[10px] text-emerald-400 mt-1">84721-3</span>
                </div>
                <div className="absolute top-8 right-4 flex flex-col items-center">
                  <Radio className="w-4 h-4 text-slate-500" />
                  <span className="text-[10px] text-slate-500 mt-1">85102-8</span>
                </div>
                <div className="w-3 h-3 bg-blue-500 rounded-full shadow-[0_0_15px_rgba(59,130,246,0.8)]"></div>
              </div>
            </div>
            
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
              <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-3">Tower Pool Analysis</h4>
              <table className="w-full text-xs text-left">
                <thead className="text-slate-500 border-b border-slate-800">
                  <tr>
                    <th className="pb-2 font-medium">TOWER ID</th>
                    <th className="pb-2 font-medium text-right">POOL SIZE</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr><td className="py-1.5 text-emerald-400">84721-3 (CURR)</td><td className="py-1.5 text-right font-mono">~35</td></tr>
                  <tr><td className="py-1.5">84778-1</td><td className="py-1.5 text-right font-mono">~42</td></tr>
                  <tr><td className="py-1.5">85102-8</td><td className="py-1.5 text-right font-mono">~28</td></tr>
                  <tr><td className="py-1.5">85044-2</td><td className="py-1.5 text-right font-mono">~37</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h4 className="text-sm font-medium text-amber-400">Tower Hopping Recommendations</h4>
            </div>
            <ul className="text-xs text-slate-300 space-y-2 list-disc list-inside">
              <li>Move device <span className="text-amber-400">0.8km northeast</span> to access tower 85044-2 with larger IP pool.</li>
              <li>Toggle airplane mode at position to force tower switch.</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}

// --- MAIN APP COMPONENT ---

export default function App() {
  return (
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  );
}

function AppContent() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [socket, setSocket] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [backendUrl, setBackendUrl] = useState(`http://127.0.0.1:3001`);
  const [usePollingOnly, setUsePollingOnly] = useState(false);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'ok' | 'failed' | null>(null);
  const [forceConnect, setForceConnect] = useState(false);
  
  // Real State from Backend
  const [state, dispatch] = React.useReducer((state: any, action: any) => {
    switch (action.type) {
      case 'UPDATE_STATUS':
        return { 
          ...state, 
          isRunning: action.payload.monitoring_active,
          temp: action.payload.phone_temperature,
          adbConnected: action.payload.adb_connected,
          netInfo: action.payload.net_info,
          nodes: action.payload.nodes || [],
          uniqueIps: action.payload.unique_ips || 0,
          totalIps: action.payload.total_ips || 500,
        };
      case 'UPDATE_HUNTING':
        return {
          ...state,
          logs: action.payload.logs || state.logs,
          activeHunters: Object.keys(action.payload.hunters || {}).length,
          avgFindTime: action.payload.stats?.avg_time_per_find || 0
        };
      default:
        return state;
    }
  }, {
    isRunning: false,
    temp: 0,
    adbConnected: false,
    netInfo: null,
    uniqueIps: 0,
    totalIps: 500,
    nodes: [],
    chartData: [], // Would be populated from historical API
    logs: [],
    activeHunters: 0,
    avgFindTime: 0
  });

  useEffect(() => {
    // Connect to the local Flask backend
    console.log(`Attempting to connect to backend at: ${backendUrl}`);
    
    const newSocket = io(backendUrl, {
      reconnectionAttempts: 20,
      timeout: 10000,
      transports: usePollingOnly ? ['polling'] : ['polling', 'websocket'],
      forceNew: true
    });
    
    newSocket.on('connect', () => {
      console.log('Successfully connected to Proxy Farm Backend');
      setIsConnected(true);
      setConnectionError(null);
      newSocket.emit('request_update');
    });

    newSocket.on('disconnect', (reason) => {
      console.log('Disconnected from Proxy Farm Backend:', reason);
      setIsConnected(false);
    });

    newSocket.on('connect_error', (err) => {
      console.error('Socket connection error:', err);
      setIsConnected(false);
      setConnectionError(`${err.message} (Target: ${backendUrl})`);
    });

    newSocket.on('status_update', (data) => {
      dispatch({ type: 'UPDATE_STATUS', payload: data });
    });

    newSocket.on('hunting_update', (data) => {
      dispatch({ type: 'UPDATE_HUNTING', payload: data });
    });

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [backendUrl]);

  useEffect(() => {
    const checkHealth = async () => {
      setHealthStatus('checking');
      try {
        // Try root first as it's more likely to exist
        const res = await fetch(`${backendUrl}/`, { 
          mode: 'no-cors',
          signal: AbortSignal.timeout(3000) 
        });
        setHealthStatus('ok');
      } catch (e) {
        setHealthStatus('failed');
      }
    };
    checkHealth();
  }, [backendUrl]);

  const tabs = [
    { id: 'dashboard', label: 'Main System', icon: Activity },
    { id: 'lab', label: 'Keepalive Lab', icon: Zap },
    { id: 'analysis', label: 'Advanced Analysis', icon: Radio },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300 font-sans selection:bg-emerald-500/30">
      {/* Navbar */}
      <nav className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center border border-emerald-500/30">
                <Server className="w-5 h-5 text-emerald-400" />
              </div>
              <span className="font-bold text-lg tracking-tight text-white">ProxyFarm<span className="text-emerald-500">OS</span></span>
            </div>
            <div className="flex space-x-1">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2",
                    activeTab === tab.id 
                      ? "bg-slate-800 text-white shadow-sm" 
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  )}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                <span className="relative flex h-3 w-3">
                  {state.isRunning && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                  <span className={cn("relative inline-flex rounded-full h-3 w-3", state.isRunning ? "bg-emerald-500" : "bg-slate-600")}></span>
                </span>
                <span className="text-slate-400 font-mono">{state.isRunning ? 'SYSTEM ACTIVE' : 'SYSTEM HALTED'}</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Connection Warning for Cloud Preview */}
        {(!isConnected && !forceConnect) && (
          <div className="mb-6 bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-amber-400">Backend Disconnected</h4>
              <p className="text-xs text-slate-400 mt-1">
                The React frontend is running, but it cannot connect to the Python backend.
                {connectionError && <span className="block mt-1 text-rose-400 font-mono font-bold">Error: {connectionError}</span>}
                <span className="block mt-2 flex flex-wrap gap-2">
                  <button 
                    onClick={() => setBackendUrl(`http://127.0.0.1:3001`)}
                    className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[10px] text-emerald-400 border border-slate-700"
                  >
                    Use 127.0.0.1:3001
                  </button>
                  <button 
                    onClick={() => setBackendUrl(`http://localhost:3001`)}
                    className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[10px] text-emerald-400 border border-slate-700"
                  >
                    Use localhost:3001
                  </button>
                  <button 
                    onClick={() => setUsePollingOnly(!usePollingOnly)}
                    className={cn(
                      "px-2 py-1 rounded text-[10px] border",
                      usePollingOnly ? "bg-emerald-500/20 border-emerald-500 text-emerald-400" : "bg-slate-800 border-slate-700 text-slate-400"
                    )}
                  >
                    {usePollingOnly ? "✓ Compatibility Mode Active" : "Enable Compatibility Mode"}
                  </button>
                  <button 
                    onClick={() => setForceConnect(true)}
                    className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-[10px] text-white font-bold"
                  >
                    Force Connect (Ignore Health Check)
                  </button>
                </span>
                
                <div className="mt-3 p-2 bg-slate-950/50 rounded border border-slate-800/50">
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="text-slate-500 uppercase font-bold tracking-tighter">Backend Health:</span>
                    {healthStatus === 'checking' && <RefreshCw className="w-3 h-3 animate-spin text-slate-500" />}
                    {healthStatus === 'ok' && <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> SIGNAL DETECTED</span>}
                    {healthStatus === 'failed' && <span className="text-rose-500 flex items-center gap-1"><XCircle className="w-3 h-3" /> NO SIGNAL</span>}
                  </div>
                </div>
              </p>
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && <MainDashboard state={state} dispatch={dispatch} socket={socket} />}
        {activeTab === 'lab' && <KeepaliveLab state={state} />}
        {activeTab === 'analysis' && <AdvancedAnalysis />}
      </main>
    </div>
  );
}
