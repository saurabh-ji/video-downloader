async function downloadVideo() {
  const url = document.getElementById("urlInput").value;
  const status = document.getElementById("status");

  if (!url) {
    status.textContent = "⚠️ Please enter a video link!";
    return;
  }

  status.textContent = "⏳ Downloading...";

  try {
    const response = await fetch("http://localhost:8000/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      const error = await response.json();
      status.textContent = "❌ Error: " + error.error;
      return;
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = "video.mp4";
    document.body.appendChild(a);
    a.click();
    a.remove();

    status.textContent = "✅ Download complete!";
  } catch (err) {
    status.textContent = "❌ Failed: " + err.message;
  }
}

