import React from "react";
import "../App.css";

function FileUpload({ onFileSelect }) {
    return (
        <div className="file-upload">
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
