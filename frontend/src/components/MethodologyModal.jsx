import React from 'react';
import { X, Leaf, Droplets, ThermometerSun } from 'lucide-react';

const MethodologyModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 sticky top-0 bg-white">
          <h2 className="text-xl font-semibold text-slate-800">How We Calculate ESG Metrics</h2>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-8 text-slate-600">
          <section>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                <Leaf className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-medium text-slate-900">Deforestation Risk</h3>
            </div>
            <p className="leading-relaxed">
              We monitor the health and density of vegetation surrounding the facility using <strong>Sentinel-2 optical satellites</strong>. 
              By comparing recent images to a historical baseline from a year ago, we measure how much the vegetation has dropped.
              A significant drop indicates recent logging or clearing, resulting in a higher risk score.
            </p>
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-sky-50 text-sky-600 rounded-lg">
                <Droplets className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-medium text-slate-900">Water Stress Proxy</h3>
            </div>
            <p className="leading-relaxed">
              We detect the amount of surface water (lakes, rivers, reservoirs) within the area. Because clouds can block standard optical satellites, 
              we combine optical data with <strong>Sentinel-1 radar sensors</strong>, which can "see" through clouds and weather. We compare the current 
              water footprint against historical levels. If the water area shrinks significantly, the stress score increases, signaling drought or over-extraction.
            </p>
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-orange-50 text-orange-600 rounded-lg">
                <ThermometerSun className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-medium text-slate-900">Urban Heat Island (UHI)</h3>
            </div>
            <p className="leading-relaxed">
              Large industrial facilities often absorb and trap more heat than their natural surroundings. Using <strong>Landsat thermal imaging</strong>, 
              we scan the land's surface temperature directly above the facility (within 1km). We then compare this to the cooler, rural regional average (within 10km). 
              The temperature difference (Δ Celsius) is our UHI intensity score.
            </p>
          </section>
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end rounded-b-xl">
          <button 
            onClick={onClose}
            className="px-6 py-2 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-700 transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};

export default MethodologyModal;
