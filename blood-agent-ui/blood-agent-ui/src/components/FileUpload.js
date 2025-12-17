import React from "react";

function FileUpload({ onFileSelect }) {
    return (
        <div style={{
            border: "2px dashed #999",
            padding: "20px",
            borderRadius: "10px",
            textAlign: "center",
            cursor: "pointer"
        }}>
            <input
                type="file"
                style={{ display: "none" }}
                id="fileInput"
                onChange={(e) => onFileSelect(e.target.files[0])}
            />

            <label htmlFor="fileInput" style={{ cursor: "pointer" }}>
                <strong>Click to upload file</strong>
                <br />
                (PDF, JSON, TXT, Image)
            </label>
        </div>
    );
}

export default FileUpload;
