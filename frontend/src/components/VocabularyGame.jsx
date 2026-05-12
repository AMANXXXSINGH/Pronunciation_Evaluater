import React, { useEffect, useMemo } from "react";

export default function VocabularyGame({
  score,
  setScore,
  attempts,
  setAttempts,
  shuffledVocab,
  setShuffledVocab,
  currentIndex,
  setCurrentIndex,
  selectedAnswer,
  setSelectedAnswer,
  isCorrect,
  setIsCorrect,
  shuffle,
  vocabulary,
}) {
  const currentWord = shuffledVocab[currentIndex];

  const options = useMemo(() => {
    const allOtherDefinitions = shuffledVocab
      .filter((_, index) => index !== currentIndex)
      .map((item) => item.definition);

    const uniqueDistractors = [...new Set(allOtherDefinitions)].filter(
      (definition) => definition !== currentWord.definition,
    );

    // Randomly select 3 unique distractors without replacement
    const selectedDistractors = [];
    const available = [...uniqueDistractors];
    while (selectedDistractors.length < 3 && available.length > 0) {
      const randomIndex = Math.floor(Math.random() * available.length);
      selectedDistractors.push(available.splice(randomIndex, 1)[0]);
    }

    const choices = shuffle([currentWord.definition, ...selectedDistractors]);
    return choices;
  }, [currentIndex, currentWord.definition, shuffledVocab]);

  useEffect(() => {
    setSelectedAnswer(null);
    setIsCorrect(false);
  }, [currentIndex]);

  function handleAnswer(choice) {
    if (selectedAnswer !== null) return;
    setSelectedAnswer(choice);
    const correct = choice === currentWord.definition;
    setIsCorrect(correct);
    setAttempts((prev) => prev + 1);
    if (correct) {
      setScore((prev) => prev + 1);
    }
  }

  function handleNext() {
    setCurrentIndex((prev) => (prev + 1) % shuffledVocab.length);
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div>
          <div className="meta">Vocabulary game</div>
          <div className="meta" style={{ marginTop: 4 }}>
            Select the definition that best matches the word.
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <div className="meta">
            Score: {score}/{attempts}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="meta">Word</div>
        <div style={{ marginTop: 10, fontSize: 28, fontWeight: 700 }}>
          {currentWord.word}
        </div>
      </div>

      <div className="card">
        <div className="meta">Pick the correct meaning</div>
        <div className="words" style={{ marginTop: 12 }}>
          {options.map((option, idx) => {
            const selected = selectedAnswer === option;
            const correctAnswer = option === currentWord.definition;
            const className = `word ${
              selected ? (isCorrect ? "ok" : "bad") : ""
            }`;
            return (
              <button
                key={idx}
                type="button"
                className={className}
                onClick={() => handleAnswer(option)}
                disabled={selectedAnswer !== null}
                style={{
                  flex: "1 1 100%",
                  textAlign: "left",
                  minWidth: 0,
                  whiteSpace: "normal",
                  overflowWrap: "break-word",
                }}
              >
                {option}
              </button>
            );
          })}
        </div>

        {selectedAnswer !== null ? (
          <div className="status" style={{ marginTop: 16 }}>
            {isCorrect ? (
              <div style={{ color: "#1d7a3f" }}>Correct! Nice work.</div>
            ) : (
              <div style={{ color: "#c5392a" }}>
                Incorrect. The right answer is:
                <strong> {currentWord.definition}</strong>
              </div>
            )}
          </div>
        ) : null}

        <div
          style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}
        >
          <button
            type="button"
            className="primary"
            onClick={handleNext}
            disabled={selectedAnswer === null}
          >
            Next word
          </button>
          <button
            type="button"
            onClick={() => {
              setShuffledVocab(shuffle([...vocabulary]));
              setCurrentIndex(0);
              setScore(0);
              setAttempts(0);
              setSelectedAnswer(null);
              setIsCorrect(false);
            }}
            disabled={attempts === 0}
          >
            Restart game
          </button>
        </div>
      </div>
    </div>
  );
}
