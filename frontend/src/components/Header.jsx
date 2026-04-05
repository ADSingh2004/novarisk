import React, { useState } from 'react';
import { Globe2, Download, Search, Loader2 } from 'lucide-react';

const Header = ({ activeLocation }) => {
    const [isExporting, setIsExporting] = useState(false);

    const handleExport = async () => {
        if (!activeLocation) return;
        setIsExporting(true);

        try {

            const baseUrl = import.meta.env.VITE_API_URL;
            const response = await fetch(`${baseUrl}/facility/analyze?latitude=${activeLocation.lat}&longitude=${activeLocation.lng}`)

            if (!response.ok) throw new Error("Failed to generate report");

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `NovaRisk_ESG_Report_${activeLocation.name.replace(/\s+/g, '_')}.pdf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (err) {
            console.error("Export failed:", err);
            alert("Failed to export report. Ensure backend is running.");
        } finally {
            setIsExporting(false);
        }
    };

    return (
        <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    <div className="flex items-center gap-2">
                        <div className="bg-emerald-600 p-2 rounded-lg">
                            <Globe2 className="w-6 h-6 text-white" />
                        </div>
                        <span className="text-xl font-bold text-slate-800">NovaRisk <span className="text-emerald-600">ESG</span></span>
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleExport}
                            disabled={isExporting || !activeLocation}
                            className="flex items-center gap-2 text-sm font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 px-4 py-2 rounded-lg transition-colors border border-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                            {isExporting ? 'Generating...' : 'Export PDF'}
                        </button>
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Header;
