import React from "react";

function formatPct(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "";
  return `${Math.round(x * 100)}%`;
}

export default function WordHighlighter({ words, selectedIndex, onSelect }) {
  return (
    <div className="words">
      {words.map((w) => {
        const clsBase = w.ok ? "word ok" : "word bad";
        const isSelected = selectedIndex === w.index;
        const cls = isSelected ? `${clsBase} selected` : clsBase;

        const phon =
          w.phoneme_similarity !== null && w.phoneme_similarity !== undefined
            ? formatPct(w.phoneme_similarity)
            : "";

        const recognized = w.recognized ?? "—";
        const tooltip = w.ok
          ? `Expected: ${w.expected}\nRecognized: ${recognized}`
          : `Expected: ${w.expected}\nRecognized: ${recognized}\n${w.feedback ?? ""}${
              phon ? `\nPhoneme similarity: ${phon}` : ""
            }`;

        return (
          <button
            key={w.index}
            type="button"
            className={cls}
            title={tooltip}
            onClick={() => onSelect?.(w.index)}
          >
            <span className="w-main">{w.expected}</span>
            <span className="w-sub">→ {recognized}</span>
          </button>
        );
      })}
    </div>
  );
}

