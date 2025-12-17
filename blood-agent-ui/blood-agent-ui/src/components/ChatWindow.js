import React from "react";

function ChatWindow({ messages }) {
    return (
        <div style={{
            border: "1px solid #ddd",
            borderRadius: "10px",
            padding: "10px",
            minHeight: "200px",
            marginTop: "20px",
            backgroundColor: "#fafafa"
        }}>
            {messages.map((msg, index) => (
                <div
                    key={index}
                    style={{
                        marginBottom: "15px",
                        textAlign: msg.sender === "user" ? "right" : "left"
                    }}
                >
                    <div
                        style={{
                            display: "inline-block",
                            padding: "10px",
                            borderRadius: "10px",
                            backgroundColor:
                                msg.sender === "user" ? "#dff8d8" : "#eeeeee"
                        }}
                    >
                        {msg.text}
                    </div>
                </div>
            ))}
        </div>
    );
}

export default ChatWindow;
