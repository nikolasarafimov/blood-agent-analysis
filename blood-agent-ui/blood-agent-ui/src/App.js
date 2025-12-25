import React, { useState } from "react";
import "./App.css";
import FileUpload from "./components/FileUpload";
import PromptInput from "./components/PromptInput";
import ChatWindow from "./components/ChatWindow";

function App() {
    const [file, setFile] = useState(null);
    const [prompt, setPrompt] = useState("");
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async () => {
        if (!file) {
            alert("Please upload a file first!");
            return;
        }

        setMessages(prev => [...prev, { sender: "user", text: prompt }]);
        setLoading(true);

        const formData = new FormData();
        formData.append("file", file);
        formData.append("prompt", prompt);

        try {
            const response = await fetch("http://localhost:8000/run-agent", {
    method: "POST",
    body: formData
});

if (!response.ok) {
    throw new Error("Server error");
}

const data = await response.json();

const agentOutput = JSON.stringify(data, null, 2);


            setMessages(prev => [...prev, {
                sender: "agent",
                text: agentOutput
            }]);
        } catch (error) {
            setMessages(prev => [...prev, {
                sender: "agent",
                text: "❌ Error: " + error.message
            }]);
        }

        setLoading(false);
        setPrompt("");
        setFile(null);
    };

    return (
        <div style={{ width: "600px", margin: "40px auto" }}>
            <h1>Blood Agent UI</h1>

            <FileUpload onFileSelect={setFile} />

            <PromptInput
                prompt={prompt}
                setPrompt={setPrompt}
                onSubmit={handleSubmit}
            />

            {loading && <p>Processing... please wait.</p>}

            <ChatWindow messages={messages} />
        </div>
    );
}

export default App;