import React, { useEffect, useMemo, useRef, useState } from "react";
import Recorder from "./components/Recorder.jsx";
import WordHighlighter from "./components/WordHighlighter.jsx";
import VocabularyGame from "./components/VocabularyGame.jsx";
import {
  evaluateAudio,
  deleteHistory,
  deleteHistoryItem,
  fetchHistory,
} from "./api.js";

const DEFAULT_EXPECTED = "She sells sea shells by the sea shore";

const SAMPLE_TEXT = {
  "": DEFAULT_EXPECTED,
  en: "She sells sea shells by the sea shore",
  hi: "वो समुंदर किनारे सीखा सीपियाँ बेचती है",
  es: "Ella vende conchas marinas en la orilla del mar",
  fr: "Elle vend des coquillages au bord de la mer",
};

const LANGUAGE_OPTIONS = [
  { value: "", label: "Auto detect" },
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
];

function shuffle(array) {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function formatDateTime(date) {
  return new Date(date).toLocaleString();
}

const playTTS = (text, lang) => {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  // Default to US English if auto-detect or unknown
  utterance.lang = lang === "en" || !lang ? "en-US" : lang;
  window.speechSynthesis.speak(utterance);
};

const VOCABULARY = [
  {
    word: "Resilient",
    definition: "Able to recover quickly from difficulties.",
  },
  {
    word: "Eloquent",
    definition: "Expressive and persuasive in speaking or writing.",
  },
  {
    word: "Curious",
    definition: "Eager to know or learn something.",
  },
  {
    word: "Venture",
    definition: "A risky or daring journey or undertaking.",
  },
  {
    word: "Adapt",
    definition: "To adjust to new conditions.",
  },
  {
    word: "Insight",
    definition: "A deep understanding of a person or thing.",
  },
  {
    word: "Harmonious",
    definition: "Forming a pleasing or consistent whole.",
  },
  {
    word: "Precise",
    definition: "Marked by exactness and accuracy of expression.",
  },
  {
    word: "Subtle",
    definition:
      "So delicate or precise as to be difficult to analyze or describe.",
  },
  {
    word: "Genuine",
    definition: "Real, sincere, and authentic.",
  },
  {
    word: "Fragile",
    definition: "Easily broken or damaged.",
  },
  {
    word: "Emerge",
    definition: "To come into view or become known.",
  },
  {
    word: "Weary",
    definition: "Feeling very tired from work or effort.",
  },
  {
    word: "Mellow",
    definition: "Soft, smooth, and pleasant in tone or flavor.",
  },
  {
    word: "Origin",
    definition: "The beginning or source of something.",
  },
  {
    word: "Serene",
    definition: "Calm, peaceful, and untroubled.",
  },
  {
    word: "Thrive",
    definition: "To grow, develop, or be successful.",
  },
  {
    word: "Luminous",
    definition: "Emitting or reflecting light; bright.",
  },
  {
    word: "Ponder",
    definition: "To think carefully about something.",
  },
  {
    word: "Swift",
    definition: "Moving or capable of moving at high speed.",
  },
  {
    word: "Nimble",
    definition: "Quick and light in movement or action.",
  },
  {
    word: "Robust",
    definition: "Strong and healthy; vigorous.",
  },
  {
    word: "Meek",
    definition: "Quiet, gentle, and easily imposed on.",
  },
  {
    word: "Classic",
    definition: "Judged over a period of time to be of the highest quality.",
  },
  {
    word: "Ambitious",
    definition: "Having a strong desire to achieve something.",
  },
  {
    word: "Brisk",
    definition: "Quick and energetic in movement or action.",
  },
  {
    word: "Loyal",
    definition: "Showing firm and constant support.",
  },
  {
    word: "Tranquil",
    definition: "Free from disturbance; calm.",
  },
];

export default function App() {
  const [isBooting, setIsBooting] = useState(true);
  const [expectedText, setExpectedText] = useState("");
  const [language, setLanguage] = useState("en");
  const [modelName, setModelName] = useState("small");
  const [freeMode, setFreeMode] = useState(true);
  const languageRef = useRef(language);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [selectedWordIndex, setSelectedWordIndex] = useState(null);
  const [view, setView] = useState("pronunciation");

  // Vocabulary game state
  const [vocabScore, setVocabScore] = useState(0);
  const [vocabAttempts, setVocabAttempts] = useState(0);
  const [vocabShuffledVocab, setVocabShuffledVocab] = useState(() =>
    shuffle([...VOCABULARY]),
  );
  const [vocabCurrentIndex, setVocabCurrentIndex] = useState(0);
  const [vocabSelectedAnswer, setVocabSelectedAnswer] = useState(null);
  const [vocabIsCorrect, setVocabIsCorrect] = useState(false);

  const mispronouncedCount = result?.mispronounced_words?.length || 0;

  useEffect(() => {
    if (freeMode) return;
    
    if (languageRef.current === language) {
      languageRef.current = language;
      return;
    }

    const prevSample = SAMPLE_TEXT[languageRef.current] ?? DEFAULT_EXPECTED;
    const currentText = expectedText.trim();
    const nextSample = SAMPLE_TEXT[language] ?? DEFAULT_EXPECTED;

    if (
      currentText === prevSample ||
      currentText === DEFAULT_EXPECTED ||
      currentText === nextSample
    ) {
      setExpectedText(nextSample);
    }

    if (language === "hi" && (modelName === "tiny" || modelName === "base")) {
      setModelName("small");
    }

    languageRef.current = language;
  }, [language, expectedText, modelName]);

  async function loadHistory() {
    const data = await fetchHistory({ limit: 15 });
    setHistory(data.items || []);
  }

  async function onDeleteHistory() {
    try {
      await deleteHistory();
      setHistory([]);
    } catch (e) {
      setError(e?.message || String(e));
    }
  }

  async function onDeleteHistoryItem(attemptId) {
    try {
      await deleteHistoryItem({ attemptId });
      setHistory((current) =>
        current.filter((item) => item.attempt_id !== attemptId),
      );
    } catch (e) {
      setError(e?.message || String(e));
    }
  }

  useEffect(() => {
    loadHistory().catch(() => {});
    
    // Simulate booting up animation
    const timer = setTimeout(() => {
      setIsBooting(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const canEvaluate = useMemo(() => !loading, [loading]);

  async function onRecordingStop(audioBlob) {
    setError("");
    setLoading(true);
    setSelectedWordIndex(null);
    try {
      const res = await evaluateAudio({
        audioBlob,
        expectedText: freeMode ? "" : expectedText.trim(),
        language,
        modelName,
      });
      setResult(res);
      await loadHistory();
    } catch (e) {
      console.error("Evaluation error:", e);
      const msg = e?.message || String(e);
      // Clean up common error messages for the user
      if (msg.includes("400")) {
        setError("No speech detected. Please try again and speak clearly.");
      } else {
        setError(msg);
      }
      setResult(null); // Clear previous results on error
    } finally {
      setLoading(false);
    }
  }

  const selectedWord = useMemo(() => {
    if (!result || selectedWordIndex === null) return null;
    return result.words?.find((w) => w.index === selectedWordIndex) || null;
  }, [result, selectedWordIndex]);

  if (isBooting) {
    return (
      <div className="boot-screen">
        <div className="boot-logo">🎙️</div>
        <div className="boot-loader">
          <div className="boot-progress"></div>
        </div>
        <div className="boot-text">System Booting Up...</div>
      </div>
    );
  }

  return (
    <div className="container">
      
      <div className="page-title">
        <div className="page-title-badge">UCCHARAN</div>
      </div>
      <div
        className="status"
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 20,
          justifyContent: "center",
        }}
      >
        <button
          type="button"
          className={view === "pronunciation" ? "primary" : ""}
          onClick={() => setView("pronunciation")}
        >
          Pronunciation Practice
        </button>
        <button
          type="button"
          className={view === "vocabulary" ? "primary" : ""}
          onClick={() => setView("vocabulary")}
        >
          Vocabulary Game
        </button>
      </div>
      {view === "pronunciation" ? (
        <div className="row">
          <div className="card" style={{ flex: "1 1 420px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                marginBottom: 12,
              }}
            >
              <div>
                <div className="meta"></div>
                <div
                  className="meta"
                  style={{ fontSize: 12, marginTop: 4, color: "#6d7395" }}
                >
                  {freeMode
                    ? "Speech-only mode: transcribed text will appear here after recording."
                    : "Type the sentence you want to practice."}
                </div>
              </div>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={freeMode}
                  onChange={(e) => {
                    const isFree = e.target.checked;
                    setFreeMode(isFree);
                    if (isFree) {
                      setExpectedText("");
                      setResult(null);
                    } else {
                      setExpectedText(SAMPLE_TEXT[language] || DEFAULT_EXPECTED);
                    }
                  }}
                />
                <span style={{ fontSize: 14, color: "#4f5b8f" }}>
                  Free pronunciation mode
                </span>
              </label>
            </div>
            {!freeMode && (
              <>
                <textarea
                  value={expectedText}
                  onChange={(e) => setExpectedText(e.target.value)}
                  placeholder="Type the sentence you want to practice"
                  disabled={loading}
                />
                <div style={{ marginTop: 8 }}>
                  <button 
                    type="button" 
                    onClick={() => playTTS(expectedText, language)}
                    style={{ fontSize: 13, padding: "8px 14px" }}
                  >
                    🔊 Listen to Pronunciation
                  </button>
                </div>
              </>
            )}
            {freeMode && (
              <textarea
                value={expectedText}
                readOnly
                placeholder="Speak into the mic and view your transcription here"
                disabled={loading}
              />
            )}

            <div style={{ marginTop: 12 }}>
              <div className="meta" style={{ marginBottom: 6 }}></div>
              <div className="row" style={{ gap: 10 }}>
                <label
                  style={{ display: "flex", flexDirection: "column", gap: 4 }}
                >
                  <span className="meta">Language</span>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    disabled={loading}
                    style={{
                      padding: 10,
                      borderRadius: 8,
                      border: "1px solid #ddd",
                    }}
                  >
                    {LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label
                  style={{ display: "flex", flexDirection: "column", gap: 4 }}
                >
                  <span className="meta">Model</span>
                  <select
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    disabled={loading}
                    style={{
                      padding: 10,
                      borderRadius: 8,
                      border: "1px solid #ddd",
                    }}
                  >
                    <option value="tiny">tiny</option>
                    <option value="base">base</option>
                    <option value="small">small</option>
                    <option value="medium">medium</option>
                  </select>
                  <div
                    className="meta"
                    style={{ fontSize: 12, marginTop: 4, color: "#6d7395" }}
                  >
                    Use a larger model like small or medium for better
                    transcription accuracy.
                  </div>
                </label>
              </div>
            </div>

            <Recorder
              onStop={onRecordingStop}
              onStart={() => {
                if (freeMode) {
                  setExpectedText("");
                }
              }}
              disabled={!canEvaluate}
            />

            {error ? (
              <div style={{ marginTop: 10, color: "#ea4335" }}>{error}</div>
            ) : null}

            {result?.ai_feedback && (
              <div className="card" style={{ marginTop: 20, background: "rgba(167, 139, 250, 0.08)", border: "1px solid rgba(167, 139, 250, 0.25)", padding: "20px" }}>
                <div className="meta" style={{ color: "#c4b5fd", display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                  <span style={{ fontSize: "18px" }}>🤖</span>AI Pronunciation Coach
                </div>
                <div style={{ lineHeight: "1.8", color: "#e2e8f0", whiteSpace: "pre-wrap", fontSize: "15px" }}>
                  {result.ai_feedback}
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ flex: "1 1 420px" }}>
            <h2>Results</h2>
            {result ? (
              <>
                <div className="results-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "12px", marginBottom: "20px" }}>
                  <div className="result-card" style={{ background: "rgba(99, 102, 241, 0.1)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(99, 102, 241, 0.2)" }}>
                    <div className="meta" style={{ color: "#a5b4fc", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Accuracy</div>
                    <div style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>
                      {Math.round(result.accuracy_score)}%
                    </div>
                  </div>
                  <div className="result-card" style={{ background: "rgba(139, 92, 246, 0.1)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(139, 92, 246, 0.2)" }}>
                    <div className="meta" style={{ color: "#c4b5fd", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>WER</div>
                    <div style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>
                      {result.wer.toFixed(2)}
                    </div>
                  </div>
                  <div className="result-card" style={{ background: "rgba(59, 130, 246, 0.1)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(59, 130, 246, 0.2)" }}>
                    <div className="meta" style={{ color: "#93c5fd", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Similarity</div>
                    <div style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>
                      {Math.round(result.levenshtein_similarity * 100)}%
                    </div>
                  </div>
                  {result.wpm && (
                    <div className="result-card" style={{ background: "rgba(167, 139, 250, 0.1)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(167, 139, 250, 0.2)" }}>
                      <div className="meta" style={{ color: "#c4b5fd", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Speaking Rate</div>
                      <div style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>{Math.round(result.wpm)} <span style={{ fontSize: "12px", fontWeight: "400", opacity: 0.7 }}>WPM</span></div>
                    </div>
                  )}
                  <div className="result-card" style={{ background: "rgba(239, 68, 68, 0.1)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
                    <div className="meta" style={{ color: "#fca5a5", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Errors</div>
                    <div style={{ fontSize: "20px", fontWeight: "700", color: "#fff" }}>
                      {mispronouncedCount}
                    </div>
                  </div>
                </div>

                {!result.has_expected && (
                  <div className="card" style={{ marginBottom: "20px", background: "rgba(255, 255, 255, 0.02)", border: "1px dashed rgba(255, 255, 255, 0.1)", textAlign: "center", padding: "20px" }}>
                    <div style={{ fontSize: "24px", marginBottom: "8px" }}>📢</div>
                    <div className="meta" style={{ color: "#94a3b8" }}>
                      Free Speech Mode Active. I've transcribed your words below.
                      To get accuracy scores and pronunciation tips, switch to "Practice Mode".
                    </div>
                  </div>
                )}

                {result.feedback && (
                  <div className="card" style={{ marginTop: 20, background: "rgba(59, 130, 246, 0.05)", border: "1px solid rgba(59, 130, 246, 0.2)" }}>
                    <div className="meta" style={{ color: "#93c5fd", display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                      <span style={{ fontSize: "18px" }}></span>Feedback
                    </div>
                    <div style={{ lineHeight: "1.8", color: "#e2e8f0", whiteSpace: "pre-wrap" }}>
                      {result.feedback}
                    </div>
                  </div>
                )}



                {result.suggestions?.length ? (
                  <div className="status" style={{ marginTop: 14 }}>
                    <div className="meta">
                      {result.has_expected
                        ? "Improvement suggestions"
                        : "Pronunciation guides"}
                    </div>
                    <div className="list" style={{ marginTop: 10 }}>
                      {result.suggestions.map((suggestion, idx) => (
                        <div
                          key={idx}
                          className="history-item"
                          style={{ padding: 12 }}
                        >
                          {suggestion}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {result.grammar_issues ? (
                  <div className="status" style={{ marginTop: 20 }}>
                    <div className="meta" style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                      <span style={{ fontSize: "18px" }}>✍️</span> Grammar Analysis
                    </div>
                    <div className="list">
                      {result.grammar_issues.length ? (
                        <>
                          {result.grammar_issues.map((issue, idx) => (
                            <div
                              key={idx}
                              className="history-item"
                              style={{
                                padding: "12px 16px",
                                background: "rgba(239, 68, 68, 0.1)",
                                color: "#fca5a5",
                                border: "1px solid rgba(239, 68, 68, 0.2)",
                                borderRadius: "12px",
                                marginTop: idx > 0 ? 8 : 0,
                                fontSize: "14px"
                              }}
                            >
                              {issue}
                            </div>
                          ))}
                          {result.corrected_text && (
                            <div
                              className="history-item"
                              style={{
                                padding: "12px 16px",
                                background: "rgba(16, 185, 129, 0.1)",
                                color: "#6ee7b7",
                                border: "1px solid rgba(16, 185, 129, 0.2)",
                                borderRadius: "12px",
                                marginTop: 12,
                                fontSize: "14px"
                              }}
                            >
                              <div style={{ fontWeight: "700", marginBottom: "4px", color: "#34d399" }}>Corrected sentence:</div>
                              {result.corrected_text}
                            </div>
                          )}
                        </>
                      ) : (
                        <div
                          className="history-item"
                          style={{
                            padding: "12px 16px",
                            background: "rgba(16, 185, 129, 0.1)",
                            color: "#6ee7b7",
                            border: "1px solid rgba(16, 185, 129, 0.2)",
                            borderRadius: "12px",
                            fontSize: "14px"
                          }}
                        >
                          ✨ No grammar issues detected. Your sentence structure is correct!
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}

                <div className="status" style={{ marginTop: 14 }}>
                  <div className="meta">
                    {result.has_expected ? "Expected" : "Transcribed"}
                  </div>
                  <div>{result.expected_text || result.transcribed_text}</div>
                </div>

                {result.has_expected && (
                  <div className="status" style={{ marginTop: 10 }}>
                    <div className="meta">Transcribed (Whisper)</div>
                    <div className="mono">{result.transcribed_text}</div>
                  </div>
                )}

                <div style={{ marginTop: 14 }}>
                  <div className="meta">Word-level highlight</div>
                  <WordHighlighter
                    words={result.words || []}
                    selectedIndex={selectedWordIndex}
                    onSelect={(idx) => setSelectedWordIndex(idx)}
                  />

                  {selectedWord ? (
                    <div className="card" style={{ marginTop: 20, background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                        <div>
                          <div className="meta" style={{ marginBottom: "4px" }}>Selected Word</div>
                          <div style={{ fontSize: "24px", fontWeight: "700", color: "#fff" }}>{selectedWord.expected}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <div className="meta" style={{ marginBottom: "4px" }}>Similarity</div>
                          <div style={{ 
                            fontSize: "20px", 
                            fontWeight: "700", 
                            color: selectedWord.ok ? "#34d399" : "#f87171" 
                          }}>
                            {selectedWord.phoneme_similarity !== null ? `${Math.round(selectedWord.phoneme_similarity * 100)}%` : "N/A"}
                          </div>
                        </div>
                      </div>
                      
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                        <div style={{ padding: "10px", background: "rgba(255, 255, 255, 0.05)", borderRadius: "8px" }}>
                          <div className="meta" style={{ fontSize: "10px", marginBottom: "4px" }}>Heard As</div>
                          <div style={{ color: "#e2e8f0" }}>{selectedWord.recognized || "—"}</div>
                        </div>
                        <div style={{ padding: "10px", background: "rgba(255, 255, 255, 0.05)", borderRadius: "8px" }}>
                          <div className="meta" style={{ fontSize: "10px", marginBottom: "4px" }}>Status</div>
                          <div style={{ color: selectedWord.ok ? "#34d399" : "#f87171" }}>
                            {selectedWord.ok ? "Correct" : "Needs Practice"}
                          </div>
                        </div>
                      </div>

                      {selectedWord.feedback && (
                        <div style={{ marginBottom: "12px" }}>
                          <div className="meta" style={{ fontSize: "11px", marginBottom: "4px", color: "#94a3b8" }}>Observation</div>
                          <div style={{ color: "#cbd5e1", fontSize: "14px" }}>{selectedWord.feedback}</div>
                        </div>
                      )}
                      
                      {selectedWord.suggestion && (
                        <div style={{ padding: "12px", background: "rgba(52, 211, 153, 0.1)", border: "1px solid rgba(52, 211, 153, 0.2)", borderRadius: "8px" }}>
                          <div className="meta" style={{ fontSize: "11px", marginBottom: "4px", color: "#34d399" }}>Pro Tip</div>
                          <div style={{ color: "#ecfdf5", fontSize: "14px", fontWeight: "500" }}>{selectedWord.suggestion}</div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="card" style={{ marginTop: 20, textAlign: "center", padding: "30px", background: "rgba(255, 255, 255, 0.02)", border: "1px dashed rgba(255, 255, 255, 0.1)" }}>
                      <div style={{ fontSize: "24px", marginBottom: "10px" }}>👆</div>
                      <div className="meta">Tap any highlighted word above to get specific pronunciation tips and details.</div>
                    </div>
                  )}
                </div>

                {result.mispronounced_words?.length ? (
                  <div style={{ marginTop: 14 }}>
                    <div className="meta">Pronunciation feedback</div>
                    <div className="list">
                      {result.mispronounced_words.map((w) => (
                        <div
                          key={w.index}
                          className="history-item"
                          style={{
                            borderTop: "1px solid #eee",
                            cursor: "pointer",
                          }}
                          onClick={() => setSelectedWordIndex(w.index)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="left">
                            <div>
                              <b>{w.expected}</b> →{" "}
                              <span>{w.recognized ?? "—"}</span>
                            </div>
                            <div className="meta" style={{ marginTop: 4 }}>
                              {w.feedback || "Check phoneme similarity."}
                            </div>
                            {w.suggestion ? (
                              <div
                                className="meta"
                                style={{ marginTop: 4, color: "#2b3676" }}
                              >
                                Suggestion: {w.suggestion}
                              </div>
                            ) : null}
                          </div>
                          <div className="score">
                            {w.phoneme_similarity !== null &&
                            w.phoneme_similarity !== undefined
                              ? `${Math.round(w.phoneme_similarity * 100)}%`
                              : ""}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="meta">Record your voice to see results.</div>
            )}
          </div>
        </div>
      ) : (
        <VocabularyGame
          score={vocabScore}
          setScore={setVocabScore}
          attempts={vocabAttempts}
          setAttempts={setVocabAttempts}
          shuffledVocab={vocabShuffledVocab}
          setShuffledVocab={setVocabShuffledVocab}
          currentIndex={vocabCurrentIndex}
          setCurrentIndex={setVocabCurrentIndex}
          selectedAnswer={vocabSelectedAnswer}
          setSelectedAnswer={setVocabSelectedAnswer}
          isCorrect={vocabIsCorrect}
          setIsCorrect={setVocabIsCorrect}
          shuffle={shuffle}
          vocabulary={VOCABULARY}
        />
      )}

      {view === "pronunciation" && history.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <h2 style={{ margin: 0 }}>Recent History</h2>
            <button
              type="button"
              className="primary"
              onClick={onDeleteHistory}
              disabled={loading}
              style={{ padding: "8px 12px", fontSize: 14 }}
            >
              Clear history
            </button>
          </div>
          <div className="list" style={{ marginTop: 16, gap: 14 }}>
            {history.map((item) => (
              <div
                key={item.attempt_id}
                className="history-item"
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 16,
                }}
              >
                <div className="left">
                  <div>
                    <b>Expected:</b>{" "}
                    {item.expected_text || (
                      <span style={{ color: "#6d7395" }}>Free mode</span>
                    )}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <b>Transcribed:</b> {item.transcribed_text}
                  </div>
                  <div className="meta" style={{ marginTop: 4 }}>
                    {item.expected_text ? (
                      <>
                        Accuracy: {Math.round(item.accuracy_score)}% | WER:{" "}
                        {item.wer.toFixed(3)} |{" "}
                      </>
                    ) : null}
                    {item.wpm && (
                      <>
                        Rate: {Math.round(item.wpm)} WPM |{" "}
                      </>
                    )}
                    {formatDateTime(item.created_at)}
                  </div>
                  {item.feedback && (
                    <div className="meta" style={{ marginTop: 8, fontStyle: "italic", borderLeft: "2px solid #60a5fa", paddingLeft: "10px" }}>
                      Feedback: {item.feedback}
                    </div>
                  )}
                  {item.audio_url && (
                    <div style={{ marginTop: 12 }}>
                      <audio controls src={`http://127.0.0.1:8000${item.audio_url}`} />
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => onDeleteHistoryItem(item.attempt_id)}
                  disabled={loading}
                  style={{ height: 32 }}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
