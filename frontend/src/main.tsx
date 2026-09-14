import { FormEvent, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = "http://localhost:8000";
type Video = { id: string; title: string; description: string | null; status: string };

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [videos, setVideos] = useState<Video[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
      <ul>
        {videos.map((video) => <li key={video.id}><strong>{video.title}</strong><span>{video.status}</span></li>)}
      </ul>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
