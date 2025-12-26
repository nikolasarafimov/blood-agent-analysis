import React, { useState } from "react";
import "./App.css";
import FileUpload from "./components/FileUpload";
import PromptInput from "./components/PromptInput";
import ChatWindow from "./components/ChatWindow";

function App() {
  const [files, setFiles] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);


  const handleSubmit = async () => {
  if (!prompt.trim() && files.length === 0) return;

  const hasText = !!prompt.trim();
  const hasFiles = files.length > 0;

  const textPart = hasText ? prompt.trim() : "[no text]";

  const filePart = hasFiles
    ? "\n\nAttached files:\n" + files.map(f => `- ${f.name}`).join("\n")
    : "";

  const userText = textPart + filePart;

  setMessages(prev => [
    ...prev,
    { sender: "user", text: userText }
  ]);

  setLoading(true);

  const formData = new FormData();
  files.forEach(f => formData.append("files", f));
  formData.append("prompt", prompt);

  try {
    const response = await fetch("http://localhost:8000/run-agent", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error("Server error");

    const data = await response.json();

    const messagesToAdd = [];
    for (const res of data) {
      const docId = res.doc_id;
      if (!docId) continue;

      const jsonRes = await fetch(`http://localhost:8000/results/${docId}`);
      const jsonData = await jsonRes.json();
      const pretty = JSON.stringify(jsonData, null, 2);

      messagesToAdd.push({
        sender: "agent",
        text: pretty,
        rawJson: jsonData,
        docId,
      });
    }

    setMessages(prev => [...prev, ...messagesToAdd]);
  } catch (error) {
    setMessages(prev => [
      ...prev,
      { sender: "agent", text: "❌ Error: " + error.message }
    ]);
  }

  setLoading(false);
  setPrompt("");
  setFiles([]);
};

  return (
    <div className="gpt-shell">
      <div className="gpt-main">
        <div className="gpt-center-column">
          <ChatWindow messages={messages} />
          <FileUpload files={files} setFiles={setFiles} />
          <PromptInput
            prompt={prompt}
            setPrompt={setPrompt}
            onSubmit={handleSubmit}
            loading={loading}
            files={files}
            setFiles={setFiles}
          />

          {files.length > 0 && (
            <div className="file-list">
              {files.map((f, i) => (
                <span key={i} className="file-pill">
                  {f.name}
                  <button
                    type="button"
                    className="file-pill-x"
                    onClick={() =>
                      setFiles(prev => prev.filter((_, idx) => idx !== i))
                    }
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          {loading && (
            <div style={{ marginTop: "6px", fontSize: "12px", color: "#9ca3af" }}>
              Processing...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;