import React from "react";
import "../App.css";
function ChatWindow({ messages }) {
    return (
        <div className="chat-window">
            {messages.map((msg, index) => (
                <div
                    key={index}
                    style={{
                        marginBottom: "15px",
                        textAlign: msg.sender === "user" ? "right" : "left"
                    }}
                >
                    <div className={`message ${msg.sender}`}>
  {msg.text}
</div>
                </div>
            ))}
        </div>
    );
}

export default ChatWindow;
