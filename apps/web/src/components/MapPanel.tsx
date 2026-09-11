import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Globe2, Plus } from "lucide-react";
import { api, GeoObservation } from "../api";

export default function MapPanel({
  caseId,
  points,
  onRefresh
}: {
  caseId: string;
  points: GeoObservation[];
  onRefresh: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [label, setLabel] = useState("");
  const [city, setCity] = useState("");
  const [region, setRegion] = useState("");
  const [country, setCountry] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);

  const center = useMemo<[number, number]>(() => {
    if (!points.length) return [0, 0];
    const latitude = points.reduce((acc, p) => acc + p.latitude, 0) / points.length;
    const longitude = points.reduce((acc, p) => acc + p.longitude, 0) / points.length;
    return [latitude, longitude];
  }, [points]);

  async function add() {
    const latitude = Number(lat);
    const longitude = Number(lon);
    if (!label || Number.isNaN(latitude) || Number.isNaN(longitude)) return;
    setBusy(true);
    try {
      await api.addGeo(caseId, {
        label,
        city,
        region,
        country,
        latitude,
        longitude,
        source_url: sourceUrl || undefined,
        category: "public-context"
      });
      setLabel("");
      setCity("");
      setRegion("");
      setCountry("");
      setLat("");
      setLon("");
      setSourceUrl("");
      setShowForm(false);
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">geospatial context</span>
          <h2>Map</h2>
          <p>
            Somente contexto público em precisão de cidade/infrastructure. O backend arredonda
            coordenadas para evitar uso como rastreamento preciso.
          </p>
        </div>
        <button className="secondary" onClick={() => setShowForm(!showForm)}>
          <Plus size={14} /> contexto
        </button>
      </div>

      {showForm && (
        <div className="inline-form geo-form">
          <input placeholder="Label" value={label} onChange={(e) => setLabel(e.target.value)} />
          <input placeholder="Cidade" value={city} onChange={(e) => setCity(e.target.value)} />
          <input placeholder="Região" value={region} onChange={(e) => setRegion(e.target.value)} />
          <input placeholder="País" value={country} onChange={(e) => setCountry(e.target.value)} />
          <input placeholder="Latitude" inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} />
          <input placeholder="Longitude" inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} />
          <input placeholder="URL pública da fonte" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
          <button className="primary" onClick={add} disabled={!label || !lat || !lon || busy}>salvar</button>
        </div>
      )}

      <div className="map-shell">
        <MapContainer center={center} zoom={points.length ? 5 : 2} scrollWheelZoom className="leaflet-map">
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {points.map((point) => (
            <CircleMarker
              key={point.id}
              center={[point.latitude, point.longitude]}
              radius={8}
              pathOptions={{ weight: 2 }}
            >
              <Popup>
                <strong>{point.label}</strong><br />
                {[point.city, point.region, point.country].filter(Boolean).join(", ")}
                {point.source_url && (
                  <>
                    <br />
                    <a href={point.source_url} target="_blank" rel="noreferrer">fonte pública</a>
                  </>
                )}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {!points.length && (
          <div className="map-empty">
            <Globe2 size={24} />
            <b>Nenhum contexto geográfico</b>
            <span>Adicione apenas localizações públicas/coarse relevantes ao case.</span>
          </div>
        )}
      </div>

      <div className="geo-list">
        {points.map((point) => (
          <article key={point.id}>
            <span className="geo-pulse" />
            <div>
              <b>{point.label}</b>
              <small>{[point.city, point.region, point.country].filter(Boolean).join(", ") || "contexto público"}</small>
            </div>
            <code>{point.latitude.toFixed(2)}, {point.longitude.toFixed(2)}</code>
          </article>
        ))}
      </div>
    </div>
  );
}
