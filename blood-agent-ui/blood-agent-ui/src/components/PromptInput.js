import React from "react";

function PromptInput({ prompt, setPrompt, onSubmit }) {
    return (
        <div style={{ marginTop: "20px" }}>
            <textarea
                placeholder="Write instructions for the agent..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                style={{
                    width: "100%",
                    height: "100px",
                    padding: "10px"
                }}
            />

            <button
                onClick={onSubmit}
                style={{
                    marginTop: "10px",
                    padding: "10px 20px",
                    cursor: "pointer"
                }}
            >
                Run Agent
            </button>
        </div>
    );
}

export default PromptInput;
