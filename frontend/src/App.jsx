import React, { useState } from 'react';
import Header from './components/Header';
import MetricCard from './components/MetricCard';
import ESGMap from './components/ESGMap';
import { Leaf, Droplets, ThermometerSun, MapPin, RefreshCw, HelpCircle } from 'lucide-react';
import MethodologyModal from './components/MethodologyModal';

const DEMO_LOCATIONS = [
  { name: "Amazon Rainforest", lat: -3.4653, lng: -62.2159, type: 'Deforestation Focus' },
  { name: "Aral Sea", lat: 45.1481, lng: 59.5756, type: 'Water Stress Focus' },
  { name: "Tokyo City", lat: 35.6762, lng: 139.6503, type: 'UHI Focus' }
];

function App() {
  const [activeLocation, setActiveLocation] = useState(DEMO_LOCATIONS[0]);
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [isExplainModalOpen, setIsExplainModalOpen] = useState(false);

  const analyzeLocation = async (loc, forceRecalculate = false) => {
    setActiveLocation(loc);
    setIsLoading(true);
    setError(null);
    setMetrics(null);

    try {
      // Fetch from FastAPI backend
      const baseUrl = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
      const url = `${baseUrl}/api/v1/facility/analyze?latitude=${loc.lat}&longitude=${loc.lng}&radius_km=5.0${forceRecalculate ? '&recalculate=true' : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      setMetrics(data);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch ESG data. Ensure the backend is running.");
      // Fallback for UI demonstration if backend isn't up
      setTimeout(() => {
        setMetrics({
          deforestation_risk: Math.random() * 40,
          water_stress_proxy: Math.random() * 60,
          heat_island_index: Math.random() * 8
        });
        setIsLoading(false);
        setError(null);
      }, 1000);
    } finally {
      if (!error) setIsLoading(false);
    }
  };

  // Initial load
  React.useEffect(() => {
    analyzeLocation(DEMO_LOCATIONS[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <Header activeLocation={activeLocation} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Top Controls */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Facility Intelligence</h1>
            <p className="text-sm text-slate-500 mt-1">Satellite-derived ESG indicators and compliance monitoring</p>
          </div>

          <div className="flex gap-4 items-center flex-wrap">
            <button 
              onClick={() => setIsExplainModalOpen(true)} 
              className="flex items-center gap-1.5 text-sm text-blue-600 bg-blue-50 px-3 py-1.5 rounded-md hover:bg-blue-100 hover:text-blue-700 font-medium transition"
            >
              <HelpCircle className="w-4 h-4" /> Explain Calculation
            </button>
            
            <button 
              onClick={() => analyzeLocation(activeLocation, true)} 
              disabled={isLoading} 
              className="flex items-center gap-1.5 text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-md font-medium disabled:opacity-50 transition"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin opacity-50' : ''}`} /> 
              {isLoading ? 'Recalculating...' : 'Recalculate'}
            </button>

            <div className="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm overflow-x-auto max-w-full">
              {DEMO_LOCATIONS.map(loc => (
                <button
                  key={loc.name}
                  onClick={() => analyzeLocation(loc)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${activeLocation.name === loc.name
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                >
                  <MapPin className="w-4 h-4" />
                  {loc.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
            {error}
          </div>
        )}

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Left Column: Map */}
          <div className="lg:col-span-2 h-[500px] bg-white rounded-xl shadow-sm border border-slate-200">
            <ESGMap location={activeLocation} radiusKm={5} metrics={metrics} />
          </div>

          {/* Right Column: Metrics */}
          <div className="flex flex-col gap-6">
            <MetricCard
              title="Deforestation Risk"
              value={metrics ? metrics.deforestation_risk.toFixed(1) : '---'}
              unit="Score"
              status={metrics?.deforestation_risk > 50 ? 'high-risk' : metrics?.deforestation_risk > 20 ? 'medium-risk' : 'good'}
              icon={Leaf}
              isLoading={isLoading}
            />

            <MetricCard
              title="Water Stress Proxy"
              value={metrics ? metrics.water_stress_proxy.toFixed(1) : '---'}
              unit="Score"
              status={metrics?.water_stress_proxy > 60 ? 'high-risk' : metrics?.water_stress_proxy > 30 ? 'medium-risk' : 'good'}
              icon={Droplets}
              isLoading={isLoading}
            />

            <MetricCard
              title="UHI Intensity"
              value={metrics ? metrics.heat_island_index.toFixed(1) : '---'}
              unit="°C Δ"
              status={metrics?.heat_island_index > 5 ? 'high-risk' : metrics?.heat_island_index > 2 ? 'medium-risk' : 'good'}
              icon={ThermometerSun}
              isLoading={isLoading}
            />
          </div>

        </div>
      </main>

      <MethodologyModal 
        isOpen={isExplainModalOpen} 
        onClose={() => setIsExplainModalOpen(false)} 
      />
    </div>
  );
}

export default App;
