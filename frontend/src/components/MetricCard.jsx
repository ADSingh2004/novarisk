import React from 'react';
import { Leaf, Droplets, ThermometerSun, AlertTriangle, CheckCircle } from 'lucide-react';

const MetricCard = ({ title, value, unit, status, icon: Icon, isLoading }) => {
    const getStatusColor = () => {
        switch (status) {
            case 'high-risk': return 'text-red-500 bg-red-50';
            case 'medium-risk': return 'text-yellow-500 bg-yellow-50';
            case 'good': return 'text-emerald-500 bg-emerald-50';
            default: return 'text-blue-500 bg-blue-50';
        }
    };

    const getStatusIcon = () => {
        if (status === 'high-risk' || status === 'medium-risk') {
            return <AlertTriangle className="w-4 h-4 ml-2" />;
        }
        if (status === 'good') {
            return <CheckCircle className="w-4 h-4 ml-2" />;
        }
        return null;
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex flex-col transition-all hover:shadow-md">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-slate-500">{title}</h3>
                <div className={`p-2 rounded-lg ${getStatusColor()}`}>
                    <Icon className="w-5 h-5" />
                </div>
            </div>

            <div className="flex items-baseline mb-1">
                {isLoading ? (
                    <div className="animate-pulse h-8 bg-slate-200 rounded w-16"></div>
                ) : (
                    <>
                        <span className="text-3xl font-bold text-slate-800">{value}</span>
                        <span className="text-sm font-medium text-slate-500 ml-1">{unit}</span>
                        <span className={`flex items-center ${getStatusColor().split(' ')[0]}`}>
                            {getStatusIcon()}
                        </span>
                    </>
                )}
            </div>
        </div>
    );
};

export default MetricCard;
