import React from "react";
import "../App.css";

function FileUpload({ files, setFiles }) {
  const handleChange = (e) => {
    const selected = Array.from(e.target.files);


    setFiles(prev => [...prev, ...selected]);
    e.target.value = "";
  };

  return (
    <>
      <input
        type="file"
        id="fileInput"
        style={{ display: "none" }}
        multiple
        onChange={handleChange}
      />
    </>
  );
}

export default FileUpload;
