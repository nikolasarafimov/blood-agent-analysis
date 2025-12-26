import React, { useRef, useEffect } from "react";
import "../App.css";

function PromptInput({ prompt, setPrompt, onSubmit, loading, files, setFiles }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = el.scrollHeight + "px";
  }, [prompt]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading) onSubmit();
    }
  };

  const handleAttachClick = () => {
    document.getElementById("fileInput").click();
  };

  return (
    <div className="prompt-wrapper">
      <button
        type="button"
        className="attach-button"
        onClick={handleAttachClick}
      >
        📎
      </button>

      <textarea
        ref={textareaRef}
        className="prompt-input"
        placeholder="Send a message..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
      />

      <button
        className="send-button"
        onClick={onSubmit}
        disabled={loading || (!prompt.trim() && files.length === 0)}
      >
        ▶
      </button>
    </div>
  );
}

export default PromptInput;