import React, { useEffect, useMemo, useState } from "react";

const WORDS_PER_ROUND = 10;

export default function VocabularyGame({ vocabulary, playTTS, shuffle }) {
  const [round, setRound] = useState(1);
  const [shuffledVocab, setShuffledVocab] = useState(() => shuffle([...vocabulary]));
  const [currentIndex, setCurrentIndex] = useState(0);
  
  const [score, setScore] = useState(0); // Score for this round
  const [totalScore, setTotalScore] = useState(0); // Total score across rounds
  const [streak, setStreak] = useState(0);
  const [longestStreak, setLongestStreak] = useState(0);
  
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [isCorrect, setIsCorrect] = useState(false);
  
  const [isRoundComplete, setIsRoundComplete] = useState(false);

  const currentWord = shuffledVocab[currentIndex] || {};

  // Generate options
  const options = useMemo(() => {
    if (isRoundComplete || !currentWord.definition) return [];
    
    const allOtherDefinitions = vocabulary
      .filter((v) => v.word !== currentWord.word)
      .map((item) => item.definition);

    const uniqueDistractors = [...new Set(allOtherDefinitions)];
    const selectedDistractors = [];
    const available = shuffle([...uniqueDistractors]);
    
    for (let i = 0; i < 3 && i < available.length; i++) {
      selectedDistractors.push(available[i]);
    }

    return shuffle([currentWord.definition, ...selectedDistractors]);
  }, [currentIndex, currentWord.definition, isRoundComplete, vocabulary, shuffle]);

  useEffect(() => {
    setSelectedAnswer(null);
    setIsCorrect(false);
  }, [currentIndex]);

  function handleAnswer(choice) {
    if (selectedAnswer !== null) return;
    
    setSelectedAnswer(choice);
    const correct = choice === currentWord.definition;
    setIsCorrect(correct);
    
    if (correct) {
      setScore((prev) => prev + 1);
      setTotalScore((prev) => prev + 1);
      setStreak((prev) => {
        const newStreak = prev + 1;
        if (newStreak > longestStreak) setLongestStreak(newStreak);
        return newStreak;
      });
    } else {
      setStreak(0);
    }
  }

  function handleNext() {
    if (currentIndex + 1 >= WORDS_PER_ROUND) {
      setIsRoundComplete(true);
    } else {
      setCurrentIndex((prev) => prev + 1);
    }
  }

  function startNextRound() {
    setShuffledVocab(shuffle([...vocabulary]));
    setCurrentIndex(0);
    setScore(0);
    setIsRoundComplete(false);
    setRound((prev) => prev + 1);
  }

  // Calculate dynamic colors based on streak
  const streakColor = streak >= 5 ? "#ef4444" : streak >= 3 ? "#f59e0b" : "#3b82f6";
  const progressPercent = ((currentIndex + (selectedAnswer ? 1 : 0)) / WORDS_PER_ROUND) * 100;

  if (isRoundComplete) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
        <div style={{ fontSize: "64px", marginBottom: "20px" }}>🎉</div>
        <h2>Round {round} Complete!</h2>
        <div style={{ display: "flex", justifyContent: "center", gap: "20px", marginTop: "30px", marginBottom: "40px" }}>
          <div className="details-box" style={{ flex: 1, margin: 0 }}>
            <div className="meta">Accuracy</div>
            <div style={{ fontSize: "32px", fontWeight: 800, color: "#34d399" }}>
              {Math.round((score / WORDS_PER_ROUND) * 100)}%
            </div>
            <div className="meta" style={{ marginTop: "4px" }}>{score} of {WORDS_PER_ROUND}</div>
          </div>
          <div className="details-box" style={{ flex: 1, margin: 0 }}>
            <div className="meta">Longest Streak</div>
            <div style={{ fontSize: "32px", fontWeight: 800, color: "#f59e0b" }}>
              {longestStreak} 🔥
            </div>
            <div className="meta" style={{ marginTop: "4px" }}>Total Score: {totalScore}</div>
          </div>
        </div>
        <button type="button" className="primary" onClick={startNextRound} style={{ fontSize: "18px", padding: "14px 32px" }}>
          Start Round {round + 1}
        </button>
      </div>
    );
  }

  return (
    <div className="vocab-game-container">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <div>
          <div className="meta">Round {round}</div>
          <div className="meta" style={{ marginTop: "4px" }}>Word {currentIndex + 1} of {WORDS_PER_ROUND}</div>
        </div>
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <div style={{ textAlign: "right" }}>
            <div className="meta" style={{ fontSize: "12px", textTransform: "uppercase" }}>Streak</div>
            <div style={{ fontSize: "20px", fontWeight: 800, color: streakColor, transition: "color 0.3s ease" }}>
              {streak} 🔥
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div style={{ width: "100%", height: "6px", background: "var(--card-bg-faint)", borderRadius: "3px", marginBottom: "30px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${progressPercent}%`, background: "linear-gradient(90deg, #3b82f6, #8b5cf6)", transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)", borderRadius: "3px" }} />
      </div>

      <div className="card" style={{ marginBottom: 24, textAlign: "center", padding: "40px 20px", position: "relative", overflow: "hidden" }}>
        {/* Decorative background based on streak */}
        {streak >= 3 && (
          <div style={{ position: "absolute", top: "-50px", right: "-50px", width: "150px", height: "150px", background: streakColor, filter: "blur(80px)", opacity: 0.2, borderRadius: "50%" }} />
        )}
        
        <div className="meta" style={{ marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.1em" }}>What does this mean?</div>
        
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "16px", flexWrap: "wrap" }}>
          <div style={{ fontSize: "42px", fontWeight: 800, letterSpacing: "-0.02em", color: "var(--text-heading)", textShadow: "0 2px 10px rgba(0,0,0,0.1)" }}>
            {currentWord.word}
          </div>
          <button 
            type="button" 
            onClick={() => playTTS(currentWord.word, "en")}
            style={{ borderRadius: "50%", width: "48px", height: "48px", padding: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.3)", color: "#3b82f6" }}
            title="Listen to pronunciation"
          >
            🔊
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
        {options.map((option, idx) => {
          const selected = selectedAnswer === option;
          const correctAnswer = option === currentWord.definition;
          
          let stateClass = "";
          if (selectedAnswer !== null) {
            if (correctAnswer) stateClass = "correct-anim";
            else if (selected) stateClass = "wrong-anim";
          }
          
          const isOk = selectedAnswer !== null && correctAnswer;
          const isBad = selectedAnswer !== null && selected && !correctAnswer;
          const dim = selectedAnswer !== null && !selected && !correctAnswer;

          return (
            <button
              key={idx}
              type="button"
              onClick={() => handleAnswer(option)}
              disabled={selectedAnswer !== null}
              className={`vocab-option ${stateClass}`}
              style={{
                textAlign: "left",
                padding: "24px",
                borderRadius: "16px",
                fontSize: "16px",
                lineHeight: "1.5",
                background: isOk ? "rgba(16, 185, 129, 0.15)" : isBad ? "rgba(239, 68, 68, 0.15)" : "var(--card-bg)",
                border: `2px solid ${isOk ? "#34d399" : isBad ? "#ef4444" : "var(--border-light)"}`,
                color: "var(--text-heading)",
                opacity: dim ? 0.5 : 1,
                transform: isOk ? "scale(1.02)" : "scale(1)",
                transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                boxShadow: isOk ? "0 10px 25px rgba(16, 185, 129, 0.2)" : "0 4px 6px rgba(0,0,0,0.05)",
                cursor: selectedAnswer !== null ? "default" : "pointer"
              }}
            >
              {option}
            </button>
          );
        })}
      </div>

      {selectedAnswer !== null && (
        <div style={{ marginTop: "32px", animation: "slideUp 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards" }}>
          <div className="card" style={{ background: isCorrect ? "rgba(16, 185, 129, 0.05)" : "rgba(239, 68, 68, 0.05)", border: `1px solid ${isCorrect ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ flex: 1, minWidth: "250px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <div style={{ fontSize: "24px" }}>{isCorrect ? "✅" : "❌"}</div>
                  <div style={{ fontSize: "18px", fontWeight: 700, color: isCorrect ? "#34d399" : "#ef4444" }}>
                    {isCorrect ? "Excellent!" : "Not quite."}
                  </div>
                </div>
                {!isCorrect && (
                  <div style={{ color: "var(--text-main)", marginBottom: "16px" }}>
                    The correct meaning is: <strong style={{ color: "var(--text-heading)" }}>{currentWord.definition}</strong>
                  </div>
                )}
                {currentWord.example && (
                  <div style={{ background: "var(--card-bg-faint)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-light)" }}>
                    <div className="meta" style={{ marginBottom: "6px", fontSize: "11px" }}>Example Sentence</div>
                    <div style={{ fontStyle: "italic", color: "var(--text-main)" }}>"{currentWord.example}"</div>
                  </div>
                )}
              </div>
              <button type="button" className="primary" onClick={handleNext} style={{ padding: "14px 32px", fontSize: "16px", alignSelf: "center", whiteSpace: "nowrap" }}>
                {currentIndex + 1 >= WORDS_PER_ROUND ? "Finish Round" : "Next Word ➔"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
