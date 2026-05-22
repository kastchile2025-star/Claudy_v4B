import "./chunk-3RG5ZIWI.js";

// src/location.ts
var cachedLocation = null;
async function getUserLocation() {
  if (cachedLocation) return cachedLocation;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4e3);
    const res = await fetch(
      "http://ip-api.com/json/?fields=status,city,regionName,country,countryCode,timezone,lat,lon,zip",
      { signal: controller.signal }
    );
    clearTimeout(timeout);
    const data = await res.json();
    if (data.status === "success") {
      const parts = [data.city, data.regionName, data.country].filter(Boolean);
      cachedLocation = {
        city: data.city || "",
        region: data.regionName || "",
        country: data.country || "",
        countryCode: data.countryCode || "",
        timezone: data.timezone || "desconocida",
        lat: data.lat || 0,
        lon: data.lon || 0,
        zip: data.zip || "",
        formatted: [
          `Ubicaci\xF3n: ${parts.join(", ") || "desconocida"}`,
          data.countryCode ? `C\xF3digo de pa\xEDs: ${data.countryCode}` : "",
          `Zona horaria: ${data.timezone || "desconocida"}`,
          data.zip ? `C\xF3digo postal: ${data.zip}` : "",
          `Coordenadas: ${data.lat}, ${data.lon}`
        ].filter(Boolean).join(" | ")
      };
      return cachedLocation;
    }
  } catch {
  }
  cachedLocation = {
    city: "",
    region: "",
    country: "",
    countryCode: "",
    timezone: "desconocida",
    lat: 0,
    lon: 0,
    zip: "",
    formatted: "desconocida (no pude conectarme al servicio de geolocalizaci\xF3n)"
  };
  return cachedLocation;
}
async function buildLocationContext() {
  const loc = await getUserLocation();
  return `[CONTEXTO DE UBICACI\xD3N DEL USUARIO]
- ${loc.formatted}
- Usa esta ubicaci\xF3n para responder sobre: clima local, leyes y regulaciones, horarios, moneda, cultura, festividades y cualquier consulta geogr\xE1fica.
[FIN CONTEXTO DE UBICACI\xD3N]`;
}
export {
  buildLocationContext,
  getUserLocation
};
