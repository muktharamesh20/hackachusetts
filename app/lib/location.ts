import * as Location from "expo-location";
import { useEffect, useState } from "react";

export type LatLng = { lat: number; lng: number };

/** The device's position (if permitted), or null. */
export function useUserLocation(): LatLng | null {
  const [pos, setPos] = useState<LatLng | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") return;
      const p = await Location.getLastKnownPositionAsync() ?? await Location.getCurrentPositionAsync({});
      if (!cancelled && p) setPos({ lat: p.coords.latitude, lng: p.coords.longitude });
    })().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return pos;
}

/** Address or zip -> coordinates (Apple geocoder on iOS). */
export async function geocode(query: string): Promise<LatLng | null> {
  const results = await Location.geocodeAsync(query);
  return results[0] ? { lat: results[0].latitude, lng: results[0].longitude } : null;
}
