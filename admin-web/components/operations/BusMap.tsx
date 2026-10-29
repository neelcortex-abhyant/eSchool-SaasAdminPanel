"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, Marker } from "leaflet";
import { ageLabel, freshness, SCHOOL_POSITION } from "@/lib/operations/tracking";
import type { VehicleLocation } from "@/lib/operations/types";

const COLORS = { live: "#059669", stale: "#d97706", offline: "#6b7280" } as const;

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] as string);
}

/**
 * OpenStreetMap with one marker per bus, coloured by how fresh its last GPS fix is. Leaflet
 * touches `window`, so it's loaded only in the browser. Selecting a bus pans to it.
 */
export function BusMap({ locations, selected, onSelect }: { locations: VehicleLocation[]; selected: number | null; onSelect: (vehicleId: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const markers = useRef(new Map<number, Marker>());
  const leaflet = useRef<typeof import("leaflet") | null>(null);
  const fitted = useRef(false);
  const [ready, setReady] = useState(false);
  const select = useRef(onSelect);
  select.current = onSelect;

  useEffect(() => {
    let cancelled = false;
    void import("leaflet").then((L) => {
      if (cancelled || !box.current || map.current) return;
      leaflet.current = L;
      map.current = L.map(box.current, { zoomControl: true, attributionControl: true }).setView([SCHOOL_POSITION.latitude, SCHOOL_POSITION.longitude], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map.current);
      L.marker([SCHOOL_POSITION.latitude, SCHOOL_POSITION.longitude], {
        icon: L.divIcon({ className: "bus-school-pin", html: "🏫", iconSize: [28, 28] }),
        title: "School",
      }).addTo(map.current);
      setTimeout(() => map.current?.invalidateSize(), 0);
      setReady(true);
    });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
      markers.current.clear();
    };
  }, []);

  useEffect(() => {
    const L = leaflet.current;
    const target = map.current;
    if (!ready || !L || !target) return;
    const seen = new Set<number>();
    for (const location of locations) {
      seen.add(location.vehicle_id);
      const state = freshness(location.recorded_at);
      const html = `<span class="bus-pin is-${state}${selected === location.vehicle_id ? " is-selected" : ""}" style="--pin:${COLORS[state]}">🚌</span>`;
      const icon = L.divIcon({ className: "bus-pin-wrap", html, iconSize: [34, 34], iconAnchor: [17, 17] });
      const popup = `<strong>${escapeHtml(location.registration_no)}</strong><br>${escapeHtml(location.route_name ?? "No route")}<br>${escapeHtml(location.driver_name ?? "No driver")}<br><small>${ageLabel(location.recorded_at)}</small>`;
      const existing = markers.current.get(location.vehicle_id);
      if (existing) {
        existing.setLatLng([location.latitude, location.longitude]).setIcon(icon).setPopupContent(popup);
      } else {
        const marker = L.marker([location.latitude, location.longitude], { icon, title: location.registration_no, keyboard: true }).bindPopup(popup).addTo(target);
        marker.on("click", () => select.current(location.vehicle_id));
        markers.current.set(location.vehicle_id, marker);
      }
    }
    for (const [id, marker] of markers.current) {
      if (!seen.has(id)) {
        marker.remove();
        markers.current.delete(id);
      }
    }
    if (!fitted.current && locations.length) {
      fitted.current = true;
      target.fitBounds(L.latLngBounds(locations.map((row) => [row.latitude, row.longitude] as [number, number])).pad(0.3), { maxZoom: 15 });
    }
  }, [locations, selected, ready]);

  useEffect(() => {
    if (selected === null || !map.current) return;
    const marker = markers.current.get(selected);
    if (marker) {
      map.current.panTo(marker.getLatLng());
      marker.openPopup();
    }
  }, [selected]);

  return <div ref={box} className="bus-map" role="region" aria-label="Map of school buses" />;
}
