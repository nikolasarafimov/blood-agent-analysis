import React, { useEffect, useRef } from "react";
import "../App.css";

function ChatWindow({ messages }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const downloadJson = (obj, filename = "results.json") => {
    const blob = new Blob([JSON.stringify(obj, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="chat-window">
      {messages.map((msg, index) => (
        <div key={index} className={`message ${msg.sender}`}>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
            {msg.text}
          </pre>

          {msg.rawJson && (
            <button
              className="send-button"
              style={{ marginTop: "6px" }}
              onClick={() =>
                downloadJson(msg.rawJson, `lab-results-${msg.docId || index}.json`)
              }
            >
              Download JSON
            </button>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatWindow;
