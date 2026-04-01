import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix Leaflet marker icon issue in React by importing local assets
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
});

// Component to dynamically update map center
const MapUpdater = ({ center, zoom }) => {
    const map = useMap();
    useEffect(() => {
        map.flyTo(center, zoom);
    }, [center, zoom, map]);
    return null;
};

const ESGMap = ({ location, radiusKm, metrics }) => {
    const center = [location.lat, location.lng];

    // Map metric risks to circle colors
    const getRiskColor = () => {
        if (!metrics) return '#3b82f6'; // Default Blue
        const maxRisk = Math.max(
            metrics.deforestation_risk,
            metrics.water_stress_proxy,
            metrics.heat_island_index * 10
        );
        if (maxRisk > 50) return '#ef4444'; // Red
        if (maxRisk > 20) return '#eab308'; // Yellow
        return '#10b981'; // Green
    };

    return (
        <div className="h-full w-full rounded-xl overflow-hidden shadow-sm border border-slate-200 relative z-0">
            <MapContainer center={center} zoom={13} className="h-full w-full">
                {/* Modern Map Tile Layer (CartoDB Positron for clean data viz) */}
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                />
                <MapUpdater center={center} zoom={13} />

                <Marker position={center}>
                    <Popup>
                        <div className="font-semibold">{location.name}</div>
                        <div className="text-xs text-slate-500 mt-1">
                            Lat: {location.lat.toFixed(4)}, Lng: {location.lng.toFixed(4)}
                        </div>
                    </Popup>
                </Marker>

                <Circle
                    center={center}
                    radius={radiusKm * 1000} // Leaflet uses meters
                    pathOptions={{
                        color: getRiskColor(),
                        fillColor: getRiskColor(),
                        fillOpacity: 0.2,
                        weight: 2
                    }}
                />
            </MapContainer>
        </div>
    );
};

export default ESGMap;
