// blood-agent-ui/src/components/JsonTableEditor.js
import React, { useMemo, useState } from "react";
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Button,
  Stack,
  Typography,
  CircularProgress,
  Tooltip,
} from "@mui/material";
import SaveIcon from "@mui/icons-material/Save";

export default function JsonTableEditor({ apiBase, docId, rows, setRows, onSaved }) {
  const [savingRow, setSavingRow] = useState(null);

  const safeRows = useMemo(() => (Array.isArray(rows) ? rows : []), [rows]);

  const onCellChange = (idx, key, value) => {
    const next = [...safeRows];
    next[idx] = { ...(next[idx] || {}), [key]: value };
    setRows(next);
  };

  const saveRow = async (idx) => {
    if (!docId) return;

    const r = safeRows[idx] || {};
    const payload = {
      parameter: r.parameter ?? null,
      value: r.value ?? null,
      unit: r.unit ?? null,
      loinc_code: r.loinc_code ?? null,
      reference_min: r.reference_min ?? null,
      reference_max: r.reference_max ?? null,
      loinc_display: r.loinc_display ?? null,
    };

    setSavingRow(idx);
    try {
      const res = await fetch(`${apiBase}/docs/${docId}/rows/${idx}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }

      await onSaved?.();
    } catch (e) {
      alert(`Row save failed: ${e.message}`);
    } finally {
      setSavingRow(null);
    }
  };

  return (
    <Box sx={{ width: "100%" }}>
      <Typography sx={{ fontSize: 12.5, color: "rgba(229,231,235,0.70)", mb: 1 }}>
        Edit any cell and click <b>Save</b> on that row to persist it to the database.
      </Typography>

      <Box
        sx={{
          border: "1px solid rgba(148,163,184,0.14)",
          borderRadius: "16px",
          overflow: "hidden",
          bgcolor: "rgba(2,6,23,0.35)",
        }}
      >
        <Table size="small" sx={{ "& td, & th": { borderColor: "rgba(148,163,184,0.10)" } }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 64, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>#</TableCell>
              <TableCell sx={{ fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>Parameter</TableCell>
              <TableCell sx={{ width: 170, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>Value</TableCell>
              <TableCell sx={{ width: 120, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>Unit</TableCell>
              <TableCell sx={{ width: 140, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>LOINC</TableCell>
              <TableCell sx={{ width: 140, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>Ref min</TableCell>
              <TableCell sx={{ width: 140, fontWeight: 950, color: "rgba(229,231,235,0.9)" }}>Ref max</TableCell>
              <TableCell sx={{ width: 130 }} />
            </TableRow>
          </TableHead>

          <TableBody>
            {safeRows.map((r, idx) => (
              <TableRow key={idx} hover>
                <TableCell sx={{ color: "rgba(229,231,235,0.75)", fontFamily: "ui-monospace, Menlo, monospace" }}>
                  {idx}
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.parameter ?? ""}
                    onChange={(e) => onCellChange(idx, "parameter", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="e.g. Hemoglobin"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.value ?? ""}
                    onChange={(e) => onCellChange(idx, "value", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="e.g. 13.6"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.unit ?? ""}
                    onChange={(e) => onCellChange(idx, "unit", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="g/dL"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.loinc_code ?? ""}
                    onChange={(e) => onCellChange(idx, "loinc_code", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="718-7"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.reference_min ?? ""}
                    onChange={(e) => onCellChange(idx, "reference_min", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="min"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <TextField
                    value={r.reference_max ?? ""}
                    onChange={(e) => onCellChange(idx, "reference_max", e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="max"
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        bgcolor: "rgba(255,255,255,0.03)",
                        borderRadius: "12px",
                        "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      },
                      input: { color: "rgba(229,231,235,0.90)" },
                    }}
                  />
                </TableCell>

                <TableCell>
                  <Stack direction="row" justifyContent="flex-end">
                    <Tooltip title="Save this row to database">
                      <span>
                        <Button
                          onClick={() => saveRow(idx)}
                          disabled={savingRow === idx}
                          size="small"
                          variant="contained"
                          startIcon={savingRow === idx ? <CircularProgress size={14} sx={{ color: "white" }} /> : <SaveIcon />}
                          sx={{
                            borderRadius: "12px",
                            fontWeight: 950,
                            backgroundImage:
                              "linear-gradient(135deg, rgba(124,92,255,0.95), rgba(124,92,255,0.55))",
                            border: "1px solid rgba(124,92,255,0.55)",
                            boxShadow: "0 18px 55px rgba(124,92,255,0.18)",
                          }}
                        >
                          {savingRow === idx ? "Saving" : "Save"}
                        </Button>
                      </span>
                    </Tooltip>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}

            {safeRows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} sx={{ py: 2 }}>
                  <Typography sx={{ fontSize: 12.5, color: "rgba(229,231,235,0.65)" }}>
                    No rows yet. Click <b>Regenerate</b> to populate the table from JSON.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Box>
    </Box>
  );
}