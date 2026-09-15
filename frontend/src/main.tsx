import { FormEvent, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type HlsType from "hls.js";
import "./styles.css";

const API_URL = "http://localhost:8000";
type Video = {
  id: string;
  title: string;
  description: string | null;
  status: string;
  duration_seconds: number | null;
};
type Playback = { manifest: string; thumbnail_url: string; expires_in: number };

function VideoPlayer({ playback, title }: { playback: Playback; title: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const player = videoRef.current;
    if (!player) return;
    const manifestUrl = URL.createObjectURL(new Blob([playback.manifest], { type: "application/vnd.apple.mpegurl" }));
    let hls: HlsType | null = null;
    let disposed = false;
    if (player.canPlayType("application/vnd.apple.mpegurl")) {
      player.src = manifestUrl;
    } else {
      void import("hls.js").then(({ default: Hls }) => {
        if (disposed || !Hls.isSupported()) return;
        hls = new Hls();
        hls.loadSource(manifestUrl);
        hls.attachMedia(player);
      });
    }
    return () => {
      disposed = true;
      hls?.destroy();
      URL.revokeObjectURL(manifestUrl);
    };
  }, [playback]);

  return <video ref={videoRef} controls poster={playback.thumbnail_url} aria-label={`Playing ${title}`} />;
}

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [videos, setVideos] = useState<Video[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<{ video: Video; playback: Playback } | null>(null);

  async function loadVideos(accessToken = token) {
    const response = await fetch(`${API_URL}/videos`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (response.ok) setVideos(await response.json());
  }

  async function authenticate(event: FormEvent) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      setError("Login failed. Register through the API docs first.");
      return;
    }
    const data = await response.json();
    setToken(data.access_token);
    await loadVideos(data.access_token);
  }

  async function uploadVideo(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !file) return;
    setBusy(true);
    setError("");
    try {
      const requested = await fetch(`${API_URL}/videos/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title, filename: file.name, content_type: file.type, file_size: file.size }),
      });
      if (!requested.ok) throw new Error((await requested.json()).detail ?? "Could not prepare upload");
      const prepared = await requested.json();

      const formData = new FormData();
      Object.entries(prepared.upload.fields as Record<string, string>).forEach(([key, value]) => formData.append(key, value));
      formData.append("file", file);
      const uploaded = await fetch(prepared.upload.url, { method: "POST", body: formData });
      if (!uploaded.ok) throw new Error("The video could not be uploaded to storage");

      const completed = await fetch(`${API_URL}/videos/${prepared.video.id}/complete-upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!completed.ok) throw new Error((await completed.json()).detail ?? "Could not confirm upload");
      setTitle("");
      setFile(null);
      await loadVideos();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function playVideo(video: Video) {
    setError("");
    const response = await fetch(`${API_URL}/videos/${video.id}/playback`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      setError((await response.json()).detail ?? "Could not prepare playback");
      return;
    }
    setSelected({ video, playback: await response.json() });
  }

  useEffect(() => {
    if (!token || !videos.some((video) => ["QUEUED", "PROCESSING"].includes(video.status))) return;
    const timer = window.setInterval(() => void loadVideos(), 3000);
    return () => window.clearInterval(timer);
  }, [token, videos]);

  if (!token) {
    return (
      <main>
        <h1>StreamMind</h1>
        <p>Your video knowledge library, starting with a secure foundation.</p>
        <form onSubmit={authenticate}>
          <input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          <button>Log in</button>
        </form>
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  return (
    <main>
      <h1>Your video library</h1>
      <form onSubmit={uploadVideo}>
        <input placeholder="Video title" value={title} onChange={(event) => setTitle(event.target.value)} required />
        <input type="file" accept="video/mp4,video/quicktime,video/webm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
        <button disabled={busy}>{busy ? "Uploading…" : "Upload video"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {selected && (
        <section className="player-card">
          <VideoPlayer playback={selected.playback} title={selected.video.title} />
          <div><strong>{selected.video.title}</strong><button className="quiet" onClick={() => setSelected(null)}>Close</button></div>
        </section>
      )}
      <ul>
        {videos.map((video) => (
          <li key={video.id}>
            <div><strong>{video.title}</strong><span>{video.status.replaceAll("_", " ")}</span></div>
            {video.status === "STREAM_READY" && <button onClick={() => void playVideo(video)}>Play</button>}
          </li>
        ))}
      </ul>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
