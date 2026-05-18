/**
 * User location detection via IP geolocation.
 * Provides context for weather, laws, timezone, currency, etc.
 */

interface LocationInfo {
  city: string;
  region: string;
  country: string;
  countryCode: string;
  timezone: string;
  lat: number;
  lon: number;
  zip: string;
  formatted: string;
}

let cachedLocation: LocationInfo | null = null;

export async function getUserLocation(): Promise<LocationInfo> {
  if (cachedLocation) return cachedLocation;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);

    const res = await fetch(
      'http://ip-api.com/json/?fields=status,city,regionName,country,countryCode,timezone,lat,lon,zip',
      { signal: controller.signal }
    );
    clearTimeout(timeout);

    const data = (await res.json()) as Record<string, unknown>;

    if (data.status === 'success') {
      const parts = [data.city, data.regionName, data.country].filter(Boolean) as string[];
      cachedLocation = {
        city: (data.city as string) || '',
        region: (data.regionName as string) || '',
        country: (data.country as string) || '',
        countryCode: (data.countryCode as string) || '',
        timezone: (data.timezone as string) || 'desconocida',
        lat: (data.lat as number) || 0,
        lon: (data.lon as number) || 0,
        zip: (data.zip as string) || '',
        formatted: [
          `Ubicación: ${parts.join(', ') || 'desconocida'}`,
          data.countryCode ? `Código de país: ${data.countryCode}` : '',
          `Zona horaria: ${data.timezone || 'desconocida'}`,
          data.zip ? `Código postal: ${data.zip}` : '',
          `Coordenadas: ${data.lat}, ${data.lon}`,
        ].filter(Boolean).join(' | '),
      };
      return cachedLocation;
    }
  } catch {
    // Silently fail — location is optional context
  }

  cachedLocation = {
    city: '',
    region: '',
    country: '',
    countryCode: '',
    timezone: 'desconocida',
    lat: 0,
    lon: 0,
    zip: '',
    formatted: 'desconocida (no pude conectarme al servicio de geolocalización)',
  };
  return cachedLocation;
}

/**
 * Build location context string for system prompt.
 */
export async function buildLocationContext(): Promise<string> {
  const loc = await getUserLocation();
  return (
    `[CONTEXTO DE UBICACIÓN DEL USUARIO]\n` +
    `- ${loc.formatted}\n` +
    `- Usa esta ubicación para responder sobre: clima local, leyes y regulaciones, ` +
    `horarios, moneda, cultura, festividades y cualquier consulta geográfica.\n` +
    `[FIN CONTEXTO DE UBICACIÓN]`
  );
}
