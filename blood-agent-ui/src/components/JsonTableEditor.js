import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box, Button, Chip, CircularProgress, MenuItem, Stack, Table,
  TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography
} from "@mui/material";
import SaveIcon from "@mui/icons-material/Save";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";

const NUMBER_PATTERN = "[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?";
const NUMERIC_RE = new RegExp(`^${NUMBER_PATTERN}$`);
const PREFIX_FLAG_RE = new RegExp(`^([LH])\\s*:?\\s*(${NUMBER_PATTERN})$`, "i");
const SUFFIX_FLAG_RE = new RegExp(`^(${NUMBER_PATTERN})\\s*([LH])$`, "i");
const NON_FINITE_RE = /^(?:[LH]\s*:?\s*)?[+-]?(?:nan|inf|infinity)(?:\s*[LH])?$/i;
const DECIMAL_COMMA_RE = /^[+-]?\d+,\d+$/;

function nullableText(value) {
  if (value === null || value === undefined) return null;

  const text = String(value).trim();
  return text === "" ? null : text;
}

function nullableNumber(value, fieldName) {
  if (
    value === null ||
    value === undefined ||
    String(value).trim() === ""
  ) {
    return null;
  }

  if (typeof value === "boolean") {
    throw new Error(`${fieldName} must be a number`);
  }

  const text = String(value).trim();

  if (!NUMERIC_RE.test(text)) {
    throw new Error(
      `${fieldName} must be a number using '.' as the decimal separator`
    );
  }

  const number = Number(text);

  if (!Number.isFinite(number)) {
    throw new Error(`${fieldName} must be a finite number`);
  }

  return number;
}

function normalizeFlag(value) {
  if (
    value === null ||
    value === undefined ||
    String(value).trim() === ""
  ) {
    return null;
  }

  const flag = String(value).trim().toLowerCase();

  if (flag === "low" || flag === "l") return "low";
  if (flag === "high" || flag === "h") return "high";

  throw new Error(
    "Abnormal flag must be Low, High, or Not specified"
  );
}

function normalizeResultValue(value, abnormalFlag) {
  const explicitFlag = normalizeFlag(abnormalFlag);

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new Error("Laboratory result must be finite");
    }

    return {
      value,
      abnormal_flag: explicitFlag
    };
  }

  if (typeof value !== "string" || !value.trim()) {
    throw new Error("Laboratory result value cannot be empty");
  }

  const text = value.trim();

  if (NON_FINITE_RE.test(text)) {
    throw new Error(
      "NaN and Infinity are not valid laboratory results"
    );
  }

  if (DECIMAL_COMMA_RE.test(text)) {
    throw new Error(
      "Use '.' instead of ',' as the decimal separator"
    );
  }

  const prefix = PREFIX_FLAG_RE.exec(text);
  const suffix = prefix ? null : SUFFIX_FLAG_RE.exec(text);

  const letter = prefix?.[1] || suffix?.[2];
  const numericText = prefix?.[2] || suffix?.[1];

  if (letter && numericText) {
    const detectedFlag =
      letter.toUpperCase() === "L" ? "low" : "high";

    if (explicitFlag && explicitFlag !== detectedFlag) {
      throw new Error(
        "The Low/High flag conflicts with the result value"
      );
    }

    const number = Number(numericText);

    if (!Number.isFinite(number)) {
      throw new Error("Laboratory result must be finite");
    }

    return {
      value: number,
      abnormal_flag: detectedFlag
    };
  }

  if (NUMERIC_RE.test(text)) {
    const number = Number(text);

    if (!Number.isFinite(number)) {
      throw new Error("Laboratory result must be finite");
    }

    return {
      value: number,
      abnormal_flag: explicitFlag
    };
  }

  return {
    value: text,
    abnormal_flag: explicitFlag
  };
}

function buildRowPayload(row) {
  const parameter = nullableText(row?.parameter);

  if (!parameter) {
    throw new Error("Parameter name cannot be empty");
  }

  const measurement = normalizeResultValue(
    row?.value,
    row?.abnormal_flag
  );

  const referenceMin = nullableNumber(
    row?.reference_min,
    "Reference minimum"
  );

  const referenceMax = nullableNumber(
    row?.reference_max,
    "Reference maximum"
  );

  if (
    referenceMin !== null &&
    referenceMax !== null &&
    referenceMin > referenceMax
  ) {
    throw new Error(
      "Reference minimum cannot be greater than reference maximum"
    );
  }

  return {
    parameter,
    value: measurement.value,
    abnormal_flag: measurement.abnormal_flag,
    unit: nullableText(row?.unit),
    loinc_code: nullableText(row?.loinc_code),
    loinc_display: nullableText(row?.loinc_display),
    reference_min: referenceMin,
    reference_max: referenceMax
  };
}

function errorMessage(payload, fallback) {
  const detail = payload?.detail || payload?.error;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg)
      .filter(Boolean);

    if (messages.length) {
      return messages.join("; ");
    }
  }

  return fallback;
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

const fieldStyles = {
  minWidth: 0,
  "& .MuiOutlinedInput-root": {
    minHeight: 40,
    bgcolor: "rgba(13,20,39,0.85)",
    borderRadius: "11px",
    transition: "background 200ms ease, box-shadow 200ms ease",
    "& fieldset": {
      borderColor: "rgba(157,174,212,0.16)"
    },
    "&:hover fieldset": {
      borderColor: "rgba(177,155,255,0.36)"
    },
    "&.Mui-focused fieldset": {
      borderColor: "rgba(168,139,255,0.72)"
    }
  },
  "& .MuiInputBase-input, & .MuiSelect-select": {
    color: "#e7edff",
    fontSize: 12.3,
    fontWeight: 560,
    py: 1.05
  },
  "& .MuiSelect-icon": {
    color: "#9a9fc1"
  },
  "& .MuiInputBase-input::placeholder": {
    color: "rgba(171,185,215,0.48)",
    opacity: 1
  }
};

const headStyle = {
  bgcolor: "#161c33",
  color: "#c5cde6",
  fontWeight: 850,
  letterSpacing: "0.035em",
  fontSize: 11,
  whiteSpace: "nowrap",
  py: 1.6,
  borderBottom: "1px solid rgba(169,145,255,0.24)"
};

const cellStyle = {
  py: 0.9,
  px: 1,
  borderBottom: "1px solid rgba(160,176,212,0.09)"
};

const saveButtonStyles = {
  minWidth: 94,
  minHeight: 36,
  borderRadius: "11px",
  fontSize: 12,
  fontWeight: 800,
  background: "linear-gradient(120deg, #9575ff 0%, #7051dc 100%)",
  border: "1px solid rgba(205,187,255,0.28)",
  boxShadow: "0 8px 18px rgba(101,72,200,0.18)",
  "&:hover": {
    boxShadow: "0 12px 28px rgba(101,72,200,0.3)"
  }
};

const flagColors = {
  low: {
    color: "#ffb3ac",
    bgcolor: "rgba(251,113,133,0.09)"
  },
  high: {
    color: "#ffd08d",
    bgcolor: "rgba(245,158,11,0.09)"
  }
};

export default function JsonTableEditor({
  apiBase,
  docId,
  rows,
  setRows,
  onSaved,
  onToast
}) {
  const [savingRow, setSavingRow] = useState(null);
  const [dirtyRows, setDirtyRows] = useState(() => new Set());
  const [lastSavedRow, setLastSavedRow] = useState(null);

  const savingRef = useRef(false);

  const safeRows = useMemo(
    () => (Array.isArray(rows) ? rows : []),
    [rows]
  );

  useEffect(() => {
    setDirtyRows(new Set());
    setLastSavedRow(null);
  }, [docId]);

  const toast = useCallback(
    (message, type = "info") => {
      onToast?.(message, type);
    },
    [onToast]
  );

  const onCellChange = useCallback(
    (index, key, value) => {
      if (savingRef.current) return;

      setRows((currentRows) => {
        const current = Array.isArray(currentRows)
          ? currentRows
          : [];

        if (index < 0 || index >= current.length) {
          return current;
        }

        const next = [...current];

        next[index] = {
          ...(next[index] || {}),
          [key]: value
        };

        return next;
      });

      setDirtyRows((current) => new Set(current).add(index));
      setLastSavedRow(null);
    },
    [setRows]
  );

  const saveRow = useCallback(
    async (index) => {
      if (savingRef.current) return;

      if (!docId) {
        toast(
          "Cannot save row because the document ID is missing.",
          "error"
        );
        return;
      }

      const row = safeRows[index];

      if (!row) {
        toast(
          "The selected row no longer exists.",
          "error"
        );
        return;
      }

      let payload;

      try {
        payload = buildRowPayload(row);
      } catch (error) {
        toast(error.message, "error");
        return;
      }

      const otherRowDrafts = safeRows.map(
        (item) => ({ ...(item || {}) })
      );

      savingRef.current = true;
      setSavingRow(index);

      try {
        const response = await fetch(
          `${apiBase}/docs/${encodeURIComponent(docId)}/rows/${index}`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(payload),
            cache: "no-store"
          }
        );

        if (!response.ok) {
          throw new Error(
            errorMessage(
              await safeJson(response),
              response.statusText || "Row save failed"
            )
          );
        }

        setRows((current) => {
          if (
            !Array.isArray(current) ||
            !current[index]
          ) {
            return current;
          }

          return current.map((item, i) =>
            i === index
              ? {
                  ...item,
                  ...payload
                }
              : item
          );
        });

        if (typeof onSaved === "function") {
          try {
            await onSaved(index);

            setRows((current) => {
              if (!Array.isArray(current)) {
                return current;
              }

              return current.map((item, i) =>
                i === index
                  ? item
                  : (otherRowDrafts[i] ?? item)
              );
            });
          } catch {
            toast(
              "Row was saved, but refreshing the results failed.",
              "warning"
            );
          }
        } else {
          toast(
            "Row saved successfully.",
            "success"
          );
        }

        setDirtyRows((current) => {
          const next = new Set(current);
          next.delete(index);
          return next;
        });

        setLastSavedRow(index);
      } catch (error) {
        toast(
          `Row save failed: ${error.message}`,
          "error"
        );
      } finally {
        savingRef.current = false;
        setSavingRow(null);
      }
    },
    [
      apiBase,
      docId,
      onSaved,
      safeRows,
      setRows,
      toast
    ]
  );

  return (
    <Box
      className="ba-table-editor"
      sx={{
        width: "100%",
        minWidth: 0,
        maxWidth: "100%"
      }}
    >
      <Stack
        direction={{ xs: "column", sm: "row" }}
        alignItems={{ sm: "center" }}
        justifyContent="space-between"
        spacing={1.3}
        sx={{ mb: 1.6 }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontSize: 12.3,
              color: "#bdc8e2",
              lineHeight: 1.75
            }}
          >
            Edit a result, then save that row to the database.
            Low and High flags must reflect the original report,
            not an interpretation of its reference range.
          </Typography>

          <Typography
            sx={{
              fontSize: 11.5,
              color: "#8190b4",
              mt: 0.4
            }}
          >
            Qualitative values such as negative and &lt;5
            are supported. LOINC entries require
            independent verification.
          </Typography>
        </Box>

        <Stack
          direction="row"
          useFlexGap
          flexWrap="wrap"
          spacing={0.8}
          sx={{ flexShrink: 0 }}
        >
          <Chip
            size="small"
            label={`${safeRows.length} rows`}
            sx={{
              fontSize: 10.5,
              fontWeight: 800,
              color: "#c3b4ff",
              bgcolor: "rgba(149,117,255,0.1)",
              border: "1px solid rgba(149,117,255,0.27)"
            }}
          />

          {dirtyRows.size > 0 && (
            <Chip
              size="small"
              icon={<EditOutlinedIcon />}
              label={`${dirtyRows.size} unsaved`}
              sx={{
                fontSize: 10.5,
                fontWeight: 800,
                color: "#ffd099",
                bgcolor: "rgba(245,158,11,0.09)",
                border: "1px solid rgba(245,158,11,0.26)",
                "& .MuiChip-icon": {
                  color: "#ffd099"
                }
              }}
            />
          )}
        </Stack>
      </Stack>

      <Box
        className="ba-table-scroll"
        role="region"
        aria-label="Editable laboratory results"
        tabIndex={0}
        sx={{
          width: "100%",
          maxWidth: "100%",
          minWidth: 0,
          maxHeight: 660,
          border: "1px solid rgba(156,170,208,0.14)",
          borderRadius: "15px",
          overflowX: "auto",
          overflowY: "auto",
          overscrollBehaviorX: "contain",
          bgcolor: "rgba(5,10,25,0.45)"
        }}
      >
        <Table
          stickyHeader
          size="small"
          aria-label="Laboratory results editor"
          sx={{
            minWidth: 1540,
            tableLayout: "fixed",
            "& td, & th": {
              borderColor: "rgba(160,176,212,0.10)"
            }
          }}
        >
          <TableHead>
            <TableRow>
              <TableCell sx={{ ...headStyle, width: 64 }}>
                #
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 235 }}>
                Parameter
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 145 }}>
                Value
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 155 }}>
                Flag
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 135 }}>
                Unit
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 140 }}>
                LOINC
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 245 }}>
                LOINC display
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 125 }}>
                Ref min
              </TableCell>

              <TableCell sx={{ ...headStyle, width: 125 }}>
                Ref max
              </TableCell>

              <TableCell
                align="center"
                sx={{ ...headStyle, width: 150 }}
              >
                Action
              </TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {safeRows.map((row, index) => {
              const rawFlag = String(
                row?.abnormal_flag ?? ""
              ).toLowerCase();

              const flag =
                rawFlag === "low" || rawFlag === "l"
                  ? "low"
                  : rawFlag === "high" || rawFlag === "h"
                    ? "high"
                    : "";

              const isDirty = dirtyRows.has(index);
              const isSaving = savingRow === index;
              const isSaved =
                lastSavedRow === index && !isDirty;

              const disabled = savingRow !== null;

              const editField = (key) => (event) =>
                onCellChange(index, key, event.target.value);

              const label = (name) =>
                `${name} for row ${index + 1}`;

              return (
                <TableRow
                  className="ba-result-row"
                  key={`${docId}_${index}`}
                  hover
                  sx={{
                    bgcolor: isDirty
                      ? "rgba(149,117,255,0.055)"
                      : "transparent",
                    "& td:first-of-type": {
                      borderLeft: isDirty
                        ? "2px solid #a38aff"
                        : "2px solid transparent"
                    }
                  }}
                >
                  <TableCell
                    sx={{
                      ...cellStyle,
                      pl: 1.4
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={0.8}
                      alignItems="center"
                    >
                      <Typography
                        sx={{
                          fontSize: 12,
                          fontWeight: 750,
                          fontFamily:
                            "ui-monospace, SFMono-Regular, Menlo, monospace",
                          color: isDirty
                            ? "#c2b3ff"
                            : "#91a0c2"
                        }}
                      >
                        {String(index + 1).padStart(2, "0")}
                      </Typography>

                      {isDirty && (
                        <Tooltip title="Unsaved changes">
                          <Box
                            component="span"
                            sx={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              bgcolor: "#baa4ff",
                              boxShadow:
                                "0 0 10px rgba(186,164,255,0.65)"
                            }}
                          />
                        </Tooltip>
                      )}
                    </Stack>
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.parameter ?? ""}
                      onChange={editField("parameter")}
                      size="small"
                      fullWidth
                      placeholder="Hemoglobin"
                      disabled={disabled}
                      aria-label={label("Parameter")}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.value ?? ""}
                      onChange={editField("value")}
                      size="small"
                      fullWidth
                      placeholder="13.6 or negative"
                      disabled={disabled}
                      aria-label={label("Value")}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      select
                      value={flag}
                      size="small"
                      fullWidth
                      disabled={disabled}
                      onChange={(event) =>
                        onCellChange(
                          index,
                          "abnormal_flag",
                          event.target.value || null
                        )
                      }
                      aria-label={label("Abnormal flag")}
                      sx={{
                        ...fieldStyles,
                        ...(flag
                          ? {
                              "& .MuiOutlinedInput-root": {
                                ...fieldStyles[
                                  "& .MuiOutlinedInput-root"
                                ],
                                bgcolor: flagColors[flag].bgcolor,
                                "& .MuiSelect-select": {
                                  color: flagColors[flag].color,
                                  fontWeight: 800
                                }
                              }
                            }
                          : {})
                      }}
                    >
                      <MenuItem value="">
                        Not specified
                      </MenuItem>

                      <MenuItem value="low">
                        Low (L)
                      </MenuItem>

                      <MenuItem value="high">
                        High (H)
                      </MenuItem>
                    </TextField>
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.unit ?? ""}
                      onChange={editField("unit")}
                      size="small"
                      fullWidth
                      placeholder="g/dL"
                      disabled={disabled}
                      aria-label={label("Unit")}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.loinc_code ?? ""}
                      onChange={editField("loinc_code")}
                      size="small"
                      fullWidth
                      placeholder="Unmapped"
                      disabled={disabled}
                      aria-label={label("LOINC code")}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.loinc_display ?? ""}
                      onChange={editField("loinc_display")}
                      size="small"
                      fullWidth
                      placeholder="Unmapped"
                      disabled={disabled}
                      aria-label={label("LOINC display")}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.reference_min ?? ""}
                      onChange={editField("reference_min")}
                      size="small"
                      fullWidth
                      placeholder="Min"
                      disabled={disabled}
                      aria-label={label("Reference minimum")}
                      slotProps={{
                        htmlInput: {
                          inputMode: "decimal"
                        }
                      }}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell sx={cellStyle}>
                    <TextField
                      value={row?.reference_max ?? ""}
                      onChange={editField("reference_max")}
                      size="small"
                      fullWidth
                      placeholder="Max"
                      disabled={disabled}
                      aria-label={label("Reference maximum")}
                      slotProps={{
                        htmlInput: {
                          inputMode: "decimal"
                        }
                      }}
                      sx={fieldStyles}
                    />
                  </TableCell>

                  <TableCell
                    align="center"
                    sx={{
                      ...cellStyle,
                      pr: 1.4
                    }}
                  >
                    <Tooltip
                      title={
                        isSaved
                          ? "Last saved row"
                          : "Save this row to SQLite"
                      }
                    >
                      <span>
                        <Button
                          type="button"
                          size="small"
                          variant="contained"
                          className="ba-primary-action"
                          onClick={() => saveRow(index)}
                          disabled={disabled}
                          sx={saveButtonStyles}
                          startIcon={
                            isSaving ? (
                              <CircularProgress
                                size={14}
                                sx={{ color: "white" }}
                              />
                            ) : isSaved ? (
                              <CheckCircleOutlineRoundedIcon />
                            ) : (
                              <SaveIcon />
                            )
                          }
                        >
                          {isSaving
                            ? "Saving"
                            : isSaved
                              ? "Saved"
                              : "Save"}
                        </Button>
                      </span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}

            {safeRows.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={10}
                  sx={{
                    py: 5,
                    textAlign: "center",
                    borderBottom: 0
                  }}
                >
                  <Typography
                    sx={{
                      color: "#aab7d6",
                      fontSize: 13,
                      fontWeight: 750
                    }}
                  >
                    No structured results yet
                  </Typography>

                  <Typography
                    sx={{
                      color: "#8190b4",
                      fontSize: 12,
                      mt: 0.8
                    }}
                  >
                    Regenerate JSON after anonymized text
                    is available to populate this table.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Box>

      {safeRows.length > 0 && (
        <Typography
          sx={{
            mt: 1,
            fontSize: 11,
            color: "#8493b7",
            textAlign: "right"
          }}
        >
          Scroll horizontally to edit all fields.
          Each Save action stores one row only.
        </Typography>
      )}
    </Box>
  );
}