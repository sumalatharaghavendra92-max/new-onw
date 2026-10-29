import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './operations.css';

// Free public OpenStreetMap tiles, no API key. operations.css tones them down
// slightly so the green routes and pins stand out.
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors';

const SIGN_GREEN = '#1b6a45';
const ALTERNATIVE_GREY = '#7d8a83';

// Brand markers drawn with CSS (classes live in operations.css).
const originIcon = L.divIcon({ className: '', html: '<div class="gg-origin"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
const destinationIcon = L.divIcon({ className: '', html: '<div class="gg-milestone"></div>', iconSize: [22, 28], iconAnchor: [11, 28] });
const vehicleIcon = L.divIcon({ className: '', html: '<div class="gg-vehicle"></div>', iconSize: [16, 16], iconAnchor: [8, 8] });

// Stable empty defaults so the drawing effect does not rerun on every render.
const NONE = [];

function popupText(text) {
  const span = document.createElement('span');
  span.textContent = text;
  return span;
}

/** A route drawn as a white casing under a coloured line, so it reads on any tile. */
function drawRoute(points, layerGroup, { color, weight, dashed = false }) {
  if (!dashed) {
    L.polyline(points, { color: '#ffffff', weight: weight + 4, opacity: 0.95, lineJoin: 'round', lineCap: 'round' }).addTo(layerGroup);
  }
  return L.polyline(points, {
    color,
    weight,
    opacity: dashed ? 0.75 : 1,
    dashArray: dashed ? '6 8' : null,
    lineJoin: 'round',
    lineCap: 'round',
  }).addTo(layerGroup);
}

export default function MapView({
  routes = NONE,
  selectedRouteId,
  origin,
  destination,
  currentLocation = null, // [lat, lng] last GPS position
  autoCenterOnGps = false,
  fitOnUpdate = true,
  markers = NONE, // [{ lat, lng, label, title, className }] numbered pins (round planner)
  lines = NONE, // [{ points, color }] extra polylines drawn in order
  onMapClick = null, // (lat, lng) => void
  dots = NONE, // [{ lat, lng, color, radius, title }] small circles, e.g. simulated trucks
}) {
  const mapRef = useRef(null);
  const leafletMapRef = useRef(null);
  const layersGroupRef = useRef(null);
  const fittedRef = useRef(false);

  // Create the map once.
  useEffect(() => {
    if (!mapRef.current) return;
    if (!leafletMapRef.current) {
      const map = L.map(mapRef.current, { zoomControl: true, scrollWheelZoom: true }).setView([12.9716, 77.5946], 10);
      L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);
      layersGroupRef.current = L.layerGroup().addTo(map);
      leafletMapRef.current = map;
    }
    const timer = setTimeout(() => leafletMapRef.current?.invalidateSize(), 250);
    return () => {
      clearTimeout(timer);
      if (leafletMapRef.current) {
        leafletMapRef.current.remove();
        leafletMapRef.current = null;
        fittedRef.current = false;
      }
    };
  }, []);

  // Optional click handler (used to place depot and stops).
  useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !onMapClick) return;
    const handleClick = (event) => onMapClick(event.latlng.lat, event.latlng.lng);
    map.on('click', handleClick);
    return () => map.off('click', handleClick);
  }, [onMapClick]);

  // Redraw routes, pins and the GPS position whenever the data changes.
  useEffect(() => {
    const map = leafletMapRef.current;
    const layerGroup = layersGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();
    const bounds = L.latLngBounds([]);

    // Extra polylines, e.g. an optimised multi-stop round.
    lines.forEach((line) => {
      if (!line.points || line.points.length < 2) return;
      const polyline = drawRoute(line.points, layerGroup, { color: line.color || SIGN_GREEN, weight: 5 });
      bounds.extend(polyline.getBounds());
    });

    // Small circles drawn first so real pins and routes sit on top.
    dots.forEach((dot) => {
      const circle = L.circleMarker([dot.lat, dot.lng], {
        radius: dot.radius || 5,
        color: '#ffffff',
        weight: 1,
        fillColor: dot.color || SIGN_GREEN,
        fillOpacity: 0.9,
      }).addTo(layerGroup);
      if (dot.title) circle.bindTooltip(popupText(dot.title));
      bounds.extend([dot.lat, dot.lng]);
    });

    // Numbered pins.
    markers.forEach((marker) => {
      const icon = L.divIcon({
        className: `op-pin ${marker.className || ''}`,
        html: `<span>${marker.label}</span>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      const pin = L.marker([marker.lat, marker.lng], { icon }).addTo(layerGroup);
      if (marker.title) pin.bindPopup(popupText(marker.title));
      bounds.extend([marker.lat, marker.lng]);
    });

    // Alternatives first (grey, dashed) so the selected route sits on top.
    routes.forEach((route) => {
      const points = route.pathPoints || route.coordinates || [];
      if (route.id === selectedRouteId || points.length < 2) return;
      const polyline = drawRoute(points, layerGroup, { color: ALTERNATIVE_GREY, weight: 4, dashed: true });
      bounds.extend(polyline.getBounds());
    });

    const selectedRoute = routes.find((route) => route.id === selectedRouteId) || routes[0];
    const selectedPoints = selectedRoute ? selectedRoute.pathPoints || selectedRoute.coordinates || [] : [];
    if (selectedPoints.length > 1) {
      const polyline = drawRoute(selectedPoints, layerGroup, { color: SIGN_GREEN, weight: 5 });
      bounds.extend(polyline.getBounds());
      L.marker(selectedPoints[0], { icon: originIcon })
        .bindPopup(popupText(`Origin: ${origin || 'start'}`))
        .addTo(layerGroup);
      L.marker(selectedPoints[selectedPoints.length - 1], { icon: destinationIcon })
        .bindPopup(popupText(`Destination: ${destination || 'end'}`))
        .addTo(layerGroup);
    }

    // Last known vehicle position.
    if (Array.isArray(currentLocation) && currentLocation.length === 2) {
      L.marker(currentLocation, { icon: vehicleIcon, zIndexOffset: 1000 })
        .bindPopup(popupText('Last received driver position'))
        .addTo(layerGroup);
      bounds.extend(currentLocation);
      if (autoCenterOnGps) map.panTo(currentLocation, { animate: true });
    }

    if (bounds.isValid() && !autoCenterOnGps && (fitOnUpdate || !fittedRef.current)) {
      map.fitBounds(bounds, { padding: [50, 50] });
      fittedRef.current = true;
    }
    map.invalidateSize();
  }, [routes, selectedRouteId, origin, destination, currentLocation, autoCenterOnGps, fitOnUpdate, markers, lines, dots]);

  return (
    <div className="relative w-full h-full overflow-hidden">
      <div ref={mapRef} className="w-full h-full z-0" />
    </div>
  );
}
